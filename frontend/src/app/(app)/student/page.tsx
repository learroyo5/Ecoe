"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { clockOffsetMs, parseServerUtc } from "@/lib/time";
import { useLiveTimer } from "@/lib/ws";
import { StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";
import { ConfirmDialog, TIMER_TONE_CLASSES, timerTone } from "@/components/confirm-dialog";

type StudentFormQuestion = {
  label: string;
  type: "single_choice" | "multiple_choice" | "short_text";
  options?: string[];
};

type MediaAsset = {
  id: number;
  original_name: string;
  content_type: string;
  file_url: string;
};

type ResolvedMediaAsset = MediaAsset & {
  objectUrl: string;
};

export default function StudentPage() {
  const { authenticated, eventId } = useECOE();
  const [ecoeNumber, setEcoeNumber] = useState("");
  const [context, setContext] = useState<Record<string, unknown> | null>(null);
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [autoSubmitting, setAutoSubmitting] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [manualSubmitting, setManualSubmitting] = useState(false);
  const [showSubmitConfirm, setShowSubmitConfirm] = useState(false);
  const [draftSavedAt, setDraftSavedAt] = useState<Date | null>(null);
  const [resolvedMediaAssets, setResolvedMediaAssets] = useState<ResolvedMediaAsset[]>([]);
  const [expandedImage, setExpandedImage] = useState<ResolvedMediaAsset | null>(null);
  const autoSubmitAttemptedRef = useRef(false);

  const confirmedAt = String(context?.confirmed_at ?? "");
  const serverNow = String(context?.server_now ?? "");
  // Offset reloj servidor - local: el backend re-valida el tiempo al enviar.
  const serverClockOffsetMs = useMemo(
    () => (serverNow ? clockOffsetMs(serverNow) : 0),
    [serverNow],
  );
  const timerDurationSeconds = Number(context?.station_time_minutes ?? 0) * 60;
  // Deadline autoritativo del servidor: la UI y el backend cierran la
  // ventana en el mismo instante (el backend suma además una gracia breve
  // para absorber latencia de red).
  const submissionDeadline = String(context?.submission_deadline ?? "");
  const draftStorageKey = context ? `student-station-draft-${String(context.checkin_id)}` : "";
  const submitted = Boolean(context?.student_response_exists);

  // ── Reloj central (OPT-20 F1) ──────────────────────────────────────
  const { snapshot: liveSnapshot, connected: wsConnected } = useLiveTimer(eventId, {
    enabled: authenticated,
  });
  const liveStatus =
    liveSnapshot?.status ?? (context?.live_status as string | null | undefined) ?? null;
  const livePaused =
    liveStatus === "paused" || (!wsConnected && Boolean(context?.paused));
  const autoSubmitAllowed = liveStatus == null || liveStatus === "running";
  const questions = useMemo(() => {
    const rawQuestions = (
      context?.student_form_definition as { questions?: StudentFormQuestion[] } | undefined
    )?.questions;
    return Array.isArray(rawQuestions) ? rawQuestions : [];
  }, [context]);
  const mediaAssets = useMemo(() => {
    const rawAssets = context?.media_assets as MediaAsset[] | undefined;
    return Array.isArray(rawAssets) ? rawAssets : [];
  }, [context]);

  useEffect(() => {
    let cancelled = false;
    const objectUrls: string[] = [];

    const loadMediaAssets = async () => {
      if (!mediaAssets.length || !authenticated) {
        setResolvedMediaAssets([]);
        return;
      }

      try {
        const nextAssets = await Promise.all(
          mediaAssets.map(async (asset) => {
            const blob = await api.mediaFile(asset.id);
            const objectUrl = URL.createObjectURL(blob);
            objectUrls.push(objectUrl);
            return { ...asset, objectUrl };
          }),
        );
        if (!cancelled) {
          setResolvedMediaAssets(nextAssets);
        }
      } catch {
        if (!cancelled) {
          setResolvedMediaAssets([]);
        }
      }
    };

    loadMediaAssets();

    return () => {
      cancelled = true;
      objectUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [mediaAssets, authenticated]);

  useEffect(() => {
    if (!expandedImage) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setExpandedImage(null);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [expandedImage]);

  useEffect(() => {
    if (!draftStorageKey || typeof window === "undefined" || submitted) {
      return;
    }
    window.localStorage.setItem(draftStorageKey, JSON.stringify(answers));
    if (Object.keys(answers).length > 0) {
      setDraftSavedAt(new Date());
    }
  }, [answers, draftStorageKey, submitted]);

  useEffect(() => {
    if (!context || !confirmedAt || !timerDurationSeconds || livePaused) {
      return;
    }

    const intervalId = window.setInterval(() => {
      setNowMs(Date.now());
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [context, confirmedAt, timerDurationSeconds, livePaused]);

  const remainingSeconds = useMemo(() => {
    if (!context) {
      return null;
    }
    if (submissionDeadline) {
      return Math.max(
        0,
        Math.floor((parseServerUtc(submissionDeadline) - (nowMs + serverClockOffsetMs)) / 1000),
      );
    }
    if (!confirmedAt || !timerDurationSeconds) {
      return timerDurationSeconds || null;
    }
    const elapsedSeconds = Math.max(
      0,
      Math.floor((nowMs + serverClockOffsetMs - parseServerUtc(confirmedAt)) / 1000),
    );
    return Math.max(timerDurationSeconds - elapsedSeconds, 0);
  }, [confirmedAt, context, nowMs, serverClockOffsetMs, submissionDeadline, timerDurationSeconds]);

  const timerLabel = useMemo(() => {
    if (remainingSeconds === null) {
      return "Sin cronómetro activo";
    }
    const minutes = Math.floor(remainingSeconds / 60);
    const seconds = remainingSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }, [remainingSeconds]);

  const resetToIdentification = useCallback((notice: string) => {
    setContext(null);
    setAutoSubmitting(false);
    setExpandedImage(null);
    autoSubmitAttemptedRef.current = false;
    setAnswers({});
    setEcoeNumber("");
    setNowMs(Date.now());
    setMessage(notice);
  }, []);

  const submitResponse = useCallback(async (reason: "manual" | "automatico") => {
    if (!context || submitted) {
      return;
    }
    const currentDraftStorageKey = draftStorageKey;
    await api.submitStudent(
      {
        checkin_id: Number(context.checkin_id),
        ecoe_event_id: eventId,
        station_id: Number(context.station_id),
        student_id: Number(context.student_id),
        answers,
        locked: true,
      },
    );
    if (currentDraftStorageKey && typeof window !== "undefined") {
      window.localStorage.removeItem(currentDraftStorageKey);
    }
    resetToIdentification(
      reason === "automatico"
        ? "Se acabó el tiempo de la estación. Tu respuesta fue enviada automáticamente."
        : "Respuesta enviada correctamente para tu estación confirmada.",
    );
  }, [answers, context, draftStorageKey, eventId, resetToIdentification, submitted]);

  useEffect(() => {
    if (!context || submitted || autoSubmitting || remainingSeconds !== 0 || autoSubmitAttemptedRef.current) {
      return;
    }
    // OPT-20 F1: en pausa (o con el reloj central detenido) no autoenviamos.
    if (!autoSubmitAllowed) {
      return;
    }
    autoSubmitAttemptedRef.current = true;
    const timeoutId = window.setTimeout(() => {
      setAutoSubmitting(true);
      submitResponse("automatico")
        .catch((error) => {
          setMessage(error instanceof Error ? error.message : "No se pudo enviar automáticamente.");
          autoSubmitAttemptedRef.current = false;
        })
        .finally(() => setAutoSubmitting(false));
    }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [autoSubmitAllowed, autoSubmitting, context, remainingSeconds, submitResponse, submitted]);

  const updateAnswer = (questionIndex: number, value: string | string[]) => {
    setAnswers((current) => ({
      ...current,
      [`question_${questionIndex + 1}`]: value,
    }));
  };

  const renderMediaAsset = (asset: ResolvedMediaAsset) => {
    if (asset.content_type.startsWith("image/")) {
      return (
        <button
          type="button"
          className="block w-full overflow-hidden rounded-2xl border border-slate-200 bg-white text-left"
          onClick={() => setExpandedImage(asset)}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={asset.objectUrl}
            alt={asset.original_name}
            className="max-h-80 w-full object-contain bg-slate-100"
          />
          <span className="block px-4 py-3 text-sm font-semibold text-slate-700">
            Toca la imagen para ampliarla a pantalla completa.
          </span>
        </button>
      );
    }

    if (asset.content_type === "application/pdf") {
      return (
        <iframe
          src={asset.objectUrl}
          title={asset.original_name}
          className="h-[34rem] w-full rounded-2xl border border-slate-200 bg-white"
        />
      );
    }

    if (asset.content_type.startsWith("video/")) {
      return (
        <video className="w-full rounded-2xl border border-slate-200 bg-black" controls>
          <source src={asset.objectUrl} type={asset.content_type} />
          Tu navegador no pudo reproducir este video.
        </video>
      );
    }

    if (asset.content_type.startsWith("audio/")) {
      return (
        <audio className="w-full" controls>
          <source src={asset.objectUrl} type={asset.content_type} />
          Tu navegador no pudo reproducir este audio.
        </audio>
      );
    }

    return (
      <a
        className="inline-flex items-center rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:text-slate-900"
        href={asset.objectUrl}
        target="_blank"
        rel="noreferrer"
      >
        Abrir archivo: {asset.original_name}
      </a>
    );
  };

  // Sin early-return cuando no hay contexto: el formulario de identificación
  // (número ECOE) vive en el layout principal y debe estar SIEMPRE visible;
  // un estado vacío sin ese formulario deja al estudiante sin forma de entrar.
  return (
    <SectionCard
      title="Interfaz del estudiante"
      subtitle="Primero verifica tu número ECOE y tu nombre; solo después de la confirmación del evaluador se habilita el envío."
    >
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
      {expandedImage ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/95 p-4"
          onClick={() => setExpandedImage(null)}
        >
          <button
            type="button"
            className="absolute right-4 top-4 rounded-full border border-white/30 bg-white/10 px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/20"
            onClick={() => setExpandedImage(null)}
          >
            Cerrar
          </button>
          <div
            className="flex h-full w-full max-w-7xl flex-col items-center justify-center gap-4"
            onClick={(event) => event.stopPropagation()}
          >
            <p className="text-sm font-semibold text-white">{expandedImage.original_name}</p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={expandedImage.objectUrl}
              alt={expandedImage.original_name}
              className="max-h-full max-w-full object-contain"
            />
          </div>
        </div>
      ) : null}
      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <section className="space-y-4 rounded-3xl border border-slate-200 bg-white/80 p-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Verificación de ingreso
            </p>
            <h3 className="mt-2 text-2xl text-slate-900">Confirma tu identidad</h3>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Tiempo visible de la estación
            </p>
            <p className={`mt-2 text-3xl font-semibold tabular-nums ${TIMER_TONE_CLASSES[timerTone(remainingSeconds, timerDurationSeconds)]}`}>
              {timerLabel}
            </p>
            <p className="mt-2 text-sm text-slate-600">
              Tus respuestas se guardan localmente mientras escribes y se enviarán automáticamente
              al terminar el tiempo si aún no las has enviado.
            </p>
            {draftSavedAt && !submitted ? (
              <p className="mt-1 text-xs font-semibold text-emerald-700">
                ✓ Borrador guardado a las {draftSavedAt.toLocaleTimeString()}
              </p>
            ) : null}
          </div>

          <form
            className="space-y-4"
            onSubmit={async (event) => {
              event.preventDefault();
              setMessage(null);
              setVerifying(true);
              try {
                const response = (await api.studentAccess(
                  { ecoe_event_id: eventId, ecoe_number: ecoeNumber },
                )) as Record<string, unknown>;
                const nextDraftStorageKey = `student-station-draft-${String(response.checkin_id)}`;
                let nextAnswers: Record<string, string | string[]> = {};

                if (typeof window !== "undefined" && response.checkin_id) {
                  const rawDraft = window.localStorage.getItem(nextDraftStorageKey);
                  if (rawDraft) {
                    try {
                      nextAnswers = JSON.parse(rawDraft) as Record<string, string | string[]>;
                    } catch {
                      window.localStorage.removeItem(nextDraftStorageKey);
                    }
                  }
                }

                setAnswers(nextAnswers);
                autoSubmitAttemptedRef.current = Boolean(response.student_response_exists);
                setNowMs(Date.now());
                setContext(response);
                setMessage("Ingreso verificado correctamente.");
              } catch (error) {
                setContext(null);
                setAnswers({});
                autoSubmitAttemptedRef.current = false;
                setMessage(error instanceof Error ? error.message : "No se pudo verificar.");
              } finally {
                setVerifying(false);
              }
            }}
          >
            <label className="space-y-2">
              <span className="text-sm font-semibold text-slate-700">Número ECOE</span>
              <input
                value={ecoeNumber}
                onChange={(event) => setEcoeNumber(event.target.value)}
                placeholder="Ejemplo: 008"
              />
            </label>
            <button className="btn-primary w-full" disabled={verifying}>
              {verifying ? "Verificando..." : "Verificar mi ingreso"}
            </button>
          </form>

          {context ? (
            <div className="clinical-panel">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)]">
                Datos confirmados
              </p>
              <p className="mt-3 text-lg font-semibold text-slate-900">
                {String(context.student_ecoe_number)} · {String(context.student_name)}
              </p>
              <p className="mt-2 text-sm text-slate-600">
                Estación {String(context.station_number)} - {String(context.station_name)}
              </p>
            </div>
          ) : (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              Tu respuesta solo se habilita cuando el evaluador confirma tu ingreso en la estación.
            </div>
          )}
        </section>

        <section className="space-y-4 rounded-3xl border border-slate-200 bg-white/80 p-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Respuesta en estación
            </p>
            <h3 className="mt-2 text-2xl text-slate-900">Formulario del estudiante</h3>
          </div>

          {context ? (
            <>
              <div className="clinical-panel">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)]">
                  Instrucción previa de ingreso
                </p>
                <p className="mt-4 text-lg font-semibold leading-8 text-slate-900 md:text-xl md:leading-9">
                  {String(
                    context.pre_entry_instruction ??
                      "Sin instrucción previa registrada para esta estación.",
                  )}
                </p>
              </div>
              <div className="clinical-panel">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)]">
                  Instrucciones dentro de la estación
                </p>
                <p className="mt-4 text-xl font-semibold leading-8 text-slate-900 md:text-2xl md:leading-9">
                  {String(
                    context.student_station_instruction ??
                      "Sin instrucciones específicas registradas para esta estación.",
                  )}
                </p>
              </div>
              {resolvedMediaAssets.length ? (
                <div className="clinical-panel">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Material de apoyo disponible
                  </p>
                  <div className="mt-4 space-y-4">
                    {resolvedMediaAssets.map((asset) => (
                      <div
                        key={asset.id}
                        className="rounded-2xl border border-slate-200 bg-white p-4"
                      >
                        <p className="mb-3 text-sm font-semibold text-slate-900">
                          {asset.original_name}
                        </p>
                        {renderMediaAsset(asset)}
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
                        <label key={fieldKey} className="space-y-2 rounded-[22px] border border-slate-200 bg-white/80 p-4">
                          <span className="text-sm font-semibold text-slate-900">
                            {question.label}
                          </span>
                          <textarea
                            rows={4}
                            value={typeof value === "string" ? value : ""}
                            disabled={submitted}
                            onChange={(event) => updateAnswer(index, event.target.value)}
                            placeholder="Escribe tu respuesta breve aquí."
                          />
                        </label>
                      );
                    }

                    if (question.type === "multiple_choice") {
                      const selectedValues = Array.isArray(value) ? value : [];
                      return (
                        <fieldset key={fieldKey} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
                          <legend className="text-sm font-semibold text-slate-900">
                            {question.label}
                          </legend>
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
                                    disabled={submitted}
                                    onChange={(event) => {
                                      const nextValues = event.target.checked
                                        ? [...selectedValues, option]
                                        : selectedValues.filter((item) => item !== option);
                                      updateAnswer(index, nextValues);
                                    }}
                                  />
                                  <span className="text-sm text-slate-800">{option}</span>
                                </label>
                              );
                            })}
                          </div>
                        </fieldset>
                      );
                    }

                    return (
                      <label key={fieldKey} className="space-y-2 rounded-[22px] border border-slate-200 bg-white/80 p-4">
                        <span className="text-sm font-semibold text-slate-900">
                          {question.label}
                        </span>
                        <select
                          value={typeof value === "string" ? value : ""}
                          disabled={submitted}
                          onChange={(event) => updateAnswer(index, event.target.value)}
                        >
                          <option value="">Selecciona una opción</option>
                          {(question.options ?? []).map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </select>
                      </label>
                    );
                  })
                ) : (
                  <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    Esta estación no tiene preguntas configuradas para el estudiante. Si necesitas
                    responder en pantalla, vuelve al constructor y guarda el formulario del estudiante.
                  </div>
                )}
                <button
                  className="btn-primary w-full text-base"
                  disabled={submitted || autoSubmitting || manualSubmitting}
                >
                  {submitted
                    ? "Respuesta ya enviada"
                    : manualSubmitting
                      ? "Enviando..."
                    : autoSubmitting
                      ? "Enviando automáticamente..."
                      : "Enviar respuesta final"}
                </button>
                {submitted ? (
                  <p className="text-sm text-amber-700">
                    Esta respuesta ya fue enviada y quedó cerrada para cambios.
                  </p>
                ) : null}
              </form>
            </>
          ) : (
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              Ingresa primero tu número ECOE para activar la vista completa de la estación. Cuando
              termines de enviar, esta pantalla volverá automáticamente a este paso de identificación.
            </div>
          )}
        </section>
      </div>
      <StatusNotice message={message} className="mt-4" />
      <ConfirmDialog
        open={showSubmitConfirm}
        title="Enviar respuesta final"
        message="Una vez enviada no podrás modificarla. Verifica que respondiste todo lo que querías responder."
        confirmLabel="Enviar respuesta"
        severity="danger"
        busy={manualSubmitting}
        onConfirm={async () => {
          setMessage(null);
          setManualSubmitting(true);
          try {
            await submitResponse("manual");
            setShowSubmitConfirm(false);
          } catch (error) {
            setShowSubmitConfirm(false);
            setMessage(error instanceof Error ? error.message : "No se pudo enviar.");
          } finally {
            setManualSubmitting(false);
          }
        }}
        onCancel={() => setShowSubmitConfirm(false)}
      />
    </SectionCard>
  );
}
