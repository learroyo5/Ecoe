"use client";

/**
 * Modo kiosco: tablet compartida instalada en una estación.
 *
 * El dispositivo se vincula una sola vez con un token de estación emitido
 * por coordinación; desde ahí queda en espera y muestra automáticamente el
 * formulario cuando el evaluador confirma el ingreso de un estudiante. El
 * estudiante nunca inicia sesión: su identidad viene del check-in activo.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, isAlreadySubmittedError } from "@/lib/api";
import { clockOffsetMs, parseServerUtc } from "@/lib/time";
import { useLiveTimer } from "@/lib/ws";
import { ConfirmDialog, TIMER_TONE_CLASSES, timerTone } from "@/components/confirm-dialog";

const TOKEN_STORAGE_KEY = "ecoe-kiosk-token";
const POLL_INTERVAL_MS = 3000;
// OPT-20 F2: autoguardado server-side del borrador — debounce por cambio de
// respuesta + un latido periódico para que el barrido siempre tenga algo que
// finalizar aunque la tablet se congele.
const DRAFT_DEBOUNCE_MS = 800;
const DRAFT_HEARTBEAT_MS = 10000;

type KioskQuestion = {
  label: string;
  type: "single_choice" | "multiple_choice" | "short_text";
  options?: string[];
};

type KioskMediaAsset = {
  id: number;
  original_name: string;
  content_type: string;
};

type ResolvedMediaAsset = KioskMediaAsset & { objectUrl: string };

type KioskActive = {
  checkin_id: number;
  student_id: number;
  student_name: string;
  student_ecoe_number: string;
  student_activity: string;
  pre_entry_instruction: string;
  student_station_instruction: string;
  student_form_definition: { questions?: KioskQuestion[] } | null;
  media_assets: KioskMediaAsset[];
  station_time_minutes: number;
  confirmed_at: string;
  // OPT-20 F2: `null` mientras el reloj central está en pausa.
  submission_deadline: string | null;
  student_response_exists: boolean;
};

type KioskContext = {
  station_id: number;
  station_number: number;
  station_name: string;
  ecoe_event_id: number;
  ecoe_name: string;
  ecoe_status: string;
  server_now: string;
  // OPT-20 F1: snapshot del reloj central para la pintura inicial y el
  // fallback sin WebSocket (el kiosco se entera de la pausa en el próximo poll).
  live_status: string | null;
  current_phase_ends_at: string | null;
  paused: boolean;
  active: KioskActive | null;
};

export default function KioskPage() {
  const [token, setToken] = useState<string | null>(null);
  const [tokenInput, setTokenInput] = useState("");
  const [linkError, setLinkError] = useState<string | null>(null);
  const [station, setStation] = useState<Omit<KioskContext, "active"> | null>(null);
  const [current, setCurrent] = useState<KioskActive | null>(null);
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showSubmitConfirm, setShowSubmitConfirm] = useState(false);
  const [draftSavedAt, setDraftSavedAt] = useState<Date | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [serverOffsetMs, setServerOffsetMs] = useState(0);
  const [resolvedMedia, setResolvedMedia] = useState<ResolvedMediaAsset[]>([]);
  const autoSubmitAttemptedRef = useRef(false);
  const answersRef = useRef(answers);
  const submittedRef = useRef(submitted);
  answersRef.current = answers;
  submittedRef.current = submitted;

  const draftKey = current ? `kiosk-draft-${current.checkin_id}` : "";

  // ── Reloj central (OPT-20 F1) ──────────────────────────────────────
  // El kiosco sigue el estado del cronómetro por WebSocket; el polling de 3 s
  // es el fallback (station.live_status / station.paused). En pausa: overlay,
  // contador congelado y autoenvío suspendido.
  const { snapshot: liveSnapshot, connected: wsConnected } = useLiveTimer(
    station?.ecoe_event_id ?? 0,
    {
      kioskToken: token ?? undefined,
      enabled: Boolean(token && station?.ecoe_event_id),
    },
  );
  const liveStatus = liveSnapshot?.status ?? station?.live_status ?? null;
  const livePaused = liveStatus === "paused" || (!wsConnected && Boolean(station?.paused));
  // Sólo suspendemos el autoenvío cuando SABEMOS que hay un reloj y no está
  // corriendo: si no hay LiveSession (pilotaje sin operador) el comportamiento
  // actual se mantiene. La semántica del deadline no cambia en F1.
  const autoSubmitAllowed = liveStatus == null || liveStatus === "running";

  // ── Vinculación del dispositivo ─────────────────────────────────────
  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get("token");
    if (fromUrl) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, fromUrl);
      window.history.replaceState({}, "", "/kiosk");
      setToken(fromUrl);
      return;
    }
    setToken(window.localStorage.getItem(TOKEN_STORAGE_KEY));
  }, []);

  const unlink = useCallback((notice: string | null) => {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    setToken(null);
    setStation(null);
    setCurrent(null);
    setLinkError(notice);
  }, []);

  const submitAnswers = useCallback(
    async (target: KioskActive, payload: Record<string, string | string[]>) => {
      if (!token) return;
      await api.kioskSubmit(token, { checkin_id: target.checkin_id, answers: payload });
      window.localStorage.removeItem(`kiosk-draft-${target.checkin_id}`);
    },
    [token],
  );

  // OPT-20 F2: cuando el barrido server-side ganó la carrera, el envío del
  // cliente falla con "ya fue enviada". Es un éxito: confirmamos contra el
  // servidor y mostramos la pantalla de respuesta enviada.
  const reloadContext = useCallback(async () => {
    if (!token) return;
    try {
      const data = (await api.kioskContext(token)) as unknown as KioskContext;
      if (data.active?.student_response_exists) {
        setSubmitted(true);
      }
    } catch {
      /* el polling de 3 s corregirá el estado */
    }
  }, [token]);

  // ── Polling del contexto de la estación ─────────────────────────────
  useEffect(() => {
    if (!token) return;
    let cancelled = false;

    const poll = async () => {
      try {
        const data = (await api.kioskContext(token)) as unknown as KioskContext;
        if (cancelled) return;
        const { active, ...base } = data;
        setStation(base);
        setServerOffsetMs(clockOffsetMs(base.server_now));
        setCurrent((existing) => {
          if (existing && active && active.checkin_id === existing.checkin_id) {
            if (active.student_response_exists && !submittedRef.current) {
              setSubmitted(true);
            }
            return existing;
          }
          if (existing && (!active || active.checkin_id !== existing.checkin_id)) {
            // Rotación: llegó otro estudiante (o se cerró el check-in) con
            // una respuesta a medio escribir. La enviamos sobre el check-in
            // original — el backend la acepta mientras su ventana siga
            // abierta y la identidad quedó fijada en ese check-in.
            const pending = answersRef.current;
            if (!submittedRef.current && Object.keys(pending).length > 0) {
              submitAnswers(existing, pending).catch(() => {
                /* ventana expirada: el registro queda para contingencia */
              });
            }
          }
          autoSubmitAttemptedRef.current = false;
          setSubmitted(Boolean(active?.student_response_exists));
          if (active) {
            const savedDraft = window.localStorage.getItem(`kiosk-draft-${active.checkin_id}`);
            setAnswers(savedDraft ? JSON.parse(savedDraft) : {});
          } else {
            setAnswers({});
          }
          return active;
        });
      } catch (error) {
        if (cancelled) return;
        const detail = error instanceof Error ? error.message : "";
        if (detail.includes("token del kiosco")) {
          unlink("El token de esta estación fue revocado o expiró. Solicita uno nuevo a coordinación.");
        }
      }
    };

    poll();
    const intervalId = window.setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [submitAnswers, token, unlink]);

  // ── Borrador local ───────────────────────────────────────────────────
  useEffect(() => {
    if (!draftKey || submitted) return;
    window.localStorage.setItem(draftKey, JSON.stringify(answers));
    if (Object.keys(answers).length > 0) {
      setDraftSavedAt(new Date());
    }
  }, [answers, draftKey, submitted]);

  // ── Borrador server-side (OPT-20 F2) ────────────────────────────────
  // Debounce por cada cambio de respuesta: le da al barrido server-side algo
  // que finalizar aunque la tablet se congele después. El localStorage de
  // arriba sigue siendo el respaldo local.
  useEffect(() => {
    if (!token || !current || submitted) return;
    const checkinId = current.checkin_id;
    const timeoutId = window.setTimeout(() => {
      api
        .kioskDraft(token, { checkin_id: checkinId, answers: answersRef.current })
        .catch(() => {
          /* mejor esfuerzo: el localStorage cubre el respaldo local */
        });
    }, DRAFT_DEBOUNCE_MS);
    return () => window.clearTimeout(timeoutId);
  }, [answers, current, submitted, token]);

  // Latido periódico: reenvía el borrador cada ~10 s mientras la estación
  // esté ocupada, incluso sin cambios recientes.
  useEffect(() => {
    if (!token || !current || submitted) return;
    const checkinId = current.checkin_id;
    const intervalId = window.setInterval(() => {
      api
        .kioskDraft(token, { checkin_id: checkinId, answers: answersRef.current })
        .catch(() => {});
    }, DRAFT_HEARTBEAT_MS);
    return () => window.clearInterval(intervalId);
  }, [current, submitted, token]);

  // ── Cronómetro (deadline autoritativo del servidor) ─────────────────
  // Se detiene al enviar: una vez respondido no hay nada más que contar, y
  // dejar el reloj corriendo confundía (parecía que seguía activo cuando el
  // estudiante ya terminó y solo falta que confirmen al siguiente).
  useEffect(() => {
    if (!current || submitted || livePaused) return;
    const intervalId = window.setInterval(() => setNowMs(Date.now()), 1000);
    return () => window.clearInterval(intervalId);
  }, [current, submitted, livePaused]);

  const remainingSeconds = useMemo(() => {
    if (!current) return null;
    // OPT-20 F2: con WebSocket activo y una fase de estación corriendo, el
    // `phaseEndsAt` del frame WS es la fuente de verdad; el `submission_deadline`
    // del REST es sólo el arranque/fallback (y en transición/pausa el REST ya
    // refleja la ventana cerrada, así que no lo pisamos con el reloj de la fase
    // siguiente).
    if (wsConnected && liveSnapshot?.status === "running" && liveSnapshot.phaseEndsAt != null) {
      return Math.max(0, Math.floor((liveSnapshot.phaseEndsAt - nowMs) / 1000));
    }
    const deadline = current.submission_deadline;
    if (!deadline) return null;
    return Math.max(
      0,
      Math.floor((parseServerUtc(deadline) - (nowMs + serverOffsetMs)) / 1000),
    );
  }, [current, liveSnapshot, nowMs, serverOffsetMs, wsConnected]);

  const timerLabel = useMemo(() => {
    if (remainingSeconds === null) return "--:--";
    const minutes = Math.floor(remainingSeconds / 60);
    const seconds = remainingSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }, [remainingSeconds]);

  const timeExpired = remainingSeconds !== null && remainingSeconds <= 0;

  // ── Autoenvío al expirar ─────────────────────────────────────────────
  useEffect(() => {
    if (!current || submitted || !timeExpired || autoSubmitAttemptedRef.current) return;
    // OPT-20 F1: en pausa (o con el reloj central detenido) no autoenviamos.
    if (!autoSubmitAllowed) return;
    autoSubmitAttemptedRef.current = true;
    setSubmitting(true);
    submitAnswers(current, answersRef.current)
      .then(() => {
        setSubmitted(true);
        setMessage("Se acabó el tiempo: tu respuesta fue enviada automáticamente.");
      })
      .catch((error) => {
        if (isAlreadySubmittedError(error)) {
          setSubmitted(true);
          setMessage("Tu respuesta ya había sido registrada por el servidor.");
          void reloadContext();
          return;
        }
        setMessage(error instanceof Error ? error.message : "No se pudo enviar automáticamente.");
      })
      .finally(() => setSubmitting(false));
  }, [autoSubmitAllowed, current, reloadContext, submitAnswers, submitted, timeExpired]);

  // ── Multimedia ───────────────────────────────────────────────────────
  useEffect(() => {
    if (!token || !current?.media_assets?.length) {
      setResolvedMedia([]);
      return;
    }
    let cancelled = false;
    const objectUrls: string[] = [];
    Promise.all(
      current.media_assets.map(async (asset) => {
        const blob = await api.kioskMediaFile(token, asset.id);
        const objectUrl = URL.createObjectURL(blob);
        objectUrls.push(objectUrl);
        return { ...asset, objectUrl };
      }),
    )
      .then((assets) => {
        if (!cancelled) setResolvedMedia(assets);
      })
      .catch(() => {
        if (!cancelled) setResolvedMedia([]);
      });
    return () => {
      cancelled = true;
      objectUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [current, token]);

  const questions = useMemo(
    () => current?.student_form_definition?.questions ?? [],
    [current],
  );

  const updateAnswer = (questionIndex: number, value: string | string[]) => {
    setAnswers((prev) => ({ ...prev, [`question_${questionIndex + 1}`]: value }));
  };

  // ── Pantalla de vinculación ─────────────────────────────────────────
  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
        <section className="panel-card w-full max-w-lg p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--color-primary)]">
            Modo kiosco ECOE
          </p>
          <h1 className="mt-4 text-3xl">Vincular esta tablet a una estación</h1>
          <p className="mt-4 text-sm leading-6 text-slate-600">
            Pide a coordinación el enlace o el token de la estación. Una vez vinculada, la
            tablet mostrará automáticamente el formulario de cada estudiante confirmado.
          </p>
          {linkError ? (
            <p role="alert" className="mt-4 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-800">
              {linkError}
            </p>
          ) : null}
          <form
            className="mt-6 space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              const value = tokenInput.trim();
              if (!value) return;
              window.localStorage.setItem(TOKEN_STORAGE_KEY, value);
              setLinkError(null);
              setToken(value);
            }}
          >
            <label className="block space-y-2">
              <span className="text-sm font-semibold">Token de la estación</span>
              <input
                value={tokenInput}
                onChange={(event) => setTokenInput(event.target.value)}
                placeholder="Pega aquí el token entregado por coordinación"
                autoComplete="off"
              />
            </label>
            <button className="btn-primary w-full">Vincular estación</button>
          </form>
        </section>
      </div>
    );
  }

  // ── Pantalla de espera ───────────────────────────────────────────────
  if (!current) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-slate-100 px-6 text-center">
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[var(--color-primary)]">
          {station ? `Estación ${station.station_number} · ${station.station_name}` : "Conectando..."}
        </p>
        <h1 className="mt-6 text-4xl text-slate-900">Esperando al siguiente estudiante</h1>
        <p className="mt-4 max-w-xl text-lg leading-8 text-slate-600">
          Cuando el evaluador confirme tu ingreso, esta pantalla mostrará automáticamente las
          instrucciones y el formulario de la estación.
        </p>
        <div className="mt-10 h-3 w-3 animate-ping rounded-full bg-[var(--color-primary)]" />
        <button
          type="button"
          className="mt-14 text-xs font-semibold uppercase tracking-[0.18em] text-slate-400 underline-offset-4 hover:underline"
          onClick={() => unlink(null)}
        >
          Desvincular esta tablet
        </button>
      </div>
    );
  }

  // ── Pantalla post-envío ───────────────────────────────────────────────
  // El check-in sigue "confirmado" en el servidor hasta que el evaluador
  // confirme al siguiente estudiante (ver nota en CLAUDE.md: el kiosco no
  // decide por si mismo cuando termino alguien). Mientras tanto, NO hay que
  // seguir mostrando la identidad ni las respuestas ya enviadas: el
  // siguiente estudiante que se acerque a la tablet no debe poder verlas.
  if (current && submitted) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-slate-100 px-6 text-center">
        <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[var(--color-primary)]">
          {station ? `Estación ${station.station_number} · ${station.station_name}` : "Conectando..."}
        </p>
        <h1 className="mt-6 text-4xl text-slate-900">Respuesta enviada ✓</h1>
        <p className="mt-4 max-w-xl text-lg leading-8 text-slate-600">
          Ya puedes entregar la tablet. Esta pantalla se actualizará sola cuando el evaluador
          confirme el ingreso del siguiente estudiante.
        </p>
        <div className="mt-10 h-3 w-3 animate-ping rounded-full bg-emerald-500" />
      </div>
    );
  }

  // ── Pantalla activa (estudiante confirmado) ──────────────────────────
  return (
    <div className="min-h-screen bg-slate-100 pb-16">
      {livePaused ? (
        <div
          role="alert"
          className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-950/95 px-6 text-center text-white"
        >
          <p className="text-sm font-semibold uppercase tracking-[0.3em] text-white/60">
            Pausa
          </p>
          <p className="mt-6 text-3xl font-bold md:text-4xl">
            PAUSA — el cronómetro está detenido
          </p>
          <p className="mt-4 max-w-xl text-lg text-white/70">
            Espera a que coordinación reanude el examen. Tu respuesta a medio
            escribir se conserva.
          </p>
        </div>
      ) : null}
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="truncate text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Estación {current ? station?.station_number : ""} · {station?.station_name}
            </p>
            <p className="truncate text-lg font-semibold text-slate-900">
              {current.student_ecoe_number} · {current.student_name}
            </p>
          </div>
          <div className="text-right">
            <p
              className={`text-3xl font-semibold tabular-nums ${
                TIMER_TONE_CLASSES[timeExpired ? "danger" : timerTone(remainingSeconds, Number(current.station_time_minutes) * 60)]
              }`}
            >
              {timerLabel}
            </p>
            {draftSavedAt ? (
              <p className="text-[11px] font-semibold text-emerald-700">
                ✓ borrador {draftSavedAt.toLocaleTimeString()}
              </p>
            ) : null}
          </div>
        </div>
      </header>

      <main className="mx-auto mt-6 max-w-4xl space-y-5 px-4">
        <div className="clinical-panel">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)]">
            Verifica que eres tú
          </p>
          <p className="mt-3 text-2xl font-semibold text-slate-900">
            {current.student_ecoe_number} · {current.student_name}
          </p>
          <p className="mt-2 text-sm text-slate-600">
            Si estos datos no corresponden, avisa de inmediato al evaluador antes de responder.
          </p>
        </div>

        {current.student_station_instruction ? (
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)]">
              Instrucciones de la estación
            </p>
            <p className="mt-4 text-xl font-semibold leading-9 text-slate-900">
              {current.student_station_instruction}
            </p>
          </div>
        ) : null}

        {resolvedMedia.length ? (
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Material de apoyo
            </p>
            <div className="mt-4 space-y-4">
              {resolvedMedia.map((asset) => (
                <div key={asset.id} className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="mb-3 text-sm font-semibold text-slate-900">{asset.original_name}</p>
                  {asset.content_type.startsWith("image/") ? (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      src={asset.objectUrl}
                      alt={asset.original_name}
                      className="max-h-96 w-full rounded-2xl bg-slate-100 object-contain"
                    />
                  ) : asset.content_type === "application/pdf" ? (
                    <iframe
                      src={asset.objectUrl}
                      title={asset.original_name}
                      className="h-[30rem] w-full rounded-2xl border border-slate-200 bg-white"
                    />
                  ) : asset.content_type.startsWith("video/") ? (
                    <video className="w-full rounded-2xl bg-black" controls>
                      <source src={asset.objectUrl} type={asset.content_type} />
                    </video>
                  ) : asset.content_type.startsWith("audio/") ? (
                    <audio className="w-full" controls>
                      <source src={asset.objectUrl} type={asset.content_type} />
                    </audio>
                  ) : (
                    <a
                      className="inline-flex items-center rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700"
                      href={asset.objectUrl}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Abrir archivo: {asset.original_name}
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <form
          className="grid gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            setShowSubmitConfirm(true);
          }}
        >
          {questions.length ? (
            questions.map((question, index) => {
              const fieldKey = `question_${index + 1}`;
              const value = answers[fieldKey];

              if (question.type === "short_text") {
                return (
                  <label key={fieldKey} className="space-y-2 rounded-[22px] border border-slate-200 bg-white p-4">
                    <span className="text-base font-semibold text-slate-900">{question.label}</span>
                    <textarea
                      rows={4}
                      value={typeof value === "string" ? value : ""}
                      disabled={submitted || timeExpired}
                      onChange={(event) => updateAnswer(index, event.target.value)}
                      placeholder="Escribe tu respuesta aquí."
                    />
                  </label>
                );
              }

              if (question.type === "multiple_choice") {
                const selectedValues = Array.isArray(value) ? value : [];
                return (
                  <fieldset key={fieldKey} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
                    <legend className="text-base font-semibold text-slate-900">{question.label}</legend>
                    <div className="space-y-2">
                      {(question.options ?? []).map((option) => {
                        const checked = selectedValues.includes(option);
                        return (
                          <label
                            key={option}
                            className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3"
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              disabled={submitted || timeExpired}
                              onChange={(event) => {
                                const nextValues = event.target.checked
                                  ? [...selectedValues, option]
                                  : selectedValues.filter((item) => item !== option);
                                updateAnswer(index, nextValues);
                              }}
                            />
                            <span className="text-base text-slate-800">{option}</span>
                          </label>
                        );
                      })}
                    </div>
                  </fieldset>
                );
              }

              return (
                <fieldset key={fieldKey} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
                  <legend className="text-base font-semibold text-slate-900">{question.label}</legend>
                  <div className="space-y-2">
                    {(question.options ?? []).map((option) => (
                      <label
                        key={option}
                        className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3"
                      >
                        <input
                          type="radio"
                          name={fieldKey}
                          checked={value === option}
                          disabled={submitted || timeExpired}
                          onChange={() => updateAnswer(index, option)}
                        />
                        <span className="text-base text-slate-800">{option}</span>
                      </label>
                    ))}
                  </div>
                </fieldset>
              );
            })
          ) : (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              Esta estación no tiene preguntas configuradas: sigue las instrucciones del evaluador.
            </div>
          )}

          <button
            className="btn-primary sticky bottom-4 w-full py-4 text-lg shadow-lg"
            disabled={submitted || submitting || (timeExpired && !submitted)}
          >
            {submitted
              ? "Respuesta enviada ✓"
              : submitting
                ? "Enviando..."
                : timeExpired
                  ? "Tiempo agotado"
                  : "Enviar respuesta final"}
          </button>
        </form>

        {message ? (
          <p role="alert" className="rounded-2xl bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow">
            {message}
          </p>
        ) : null}
      </main>
      <ConfirmDialog
        open={showSubmitConfirm}
        title="Enviar respuesta final"
        message="Una vez enviada no podrás modificarla. Verifica tus respuestas antes de continuar."
        confirmLabel="Enviar respuesta"
        severity="danger"
        busy={submitting}
        onConfirm={async () => {
          setMessage(null);
          setSubmitting(true);
          try {
            await submitAnswers(current, answersRef.current);
            setShowSubmitConfirm(false);
            setSubmitted(true);
            setMessage("Respuesta enviada correctamente. Puedes avanzar a tu siguiente estación.");
          } catch (error) {
            setShowSubmitConfirm(false);
            if (isAlreadySubmittedError(error)) {
              setSubmitted(true);
              setMessage("Tu respuesta ya había sido registrada por el servidor.");
              void reloadContext();
            } else {
              setMessage(error instanceof Error ? error.message : "No se pudo enviar.");
            }
          } finally {
            setSubmitting(false);
          }
        }}
        onCancel={() => setShowSubmitConfirm(false)}
      />
    </div>
  );
}
