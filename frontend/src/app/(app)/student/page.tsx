"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { SectionCard } from "@/components/section-card";

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
  const { token, eventId } = useAuth();
  const [ecoeNumber, setEcoeNumber] = useState("");
  const [context, setContext] = useState<Record<string, unknown> | null>(null);
  const [answers, setAnswers] = useState<Record<string, string | string[]>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [autoSubmitting, setAutoSubmitting] = useState(false);
  const [resolvedMediaAssets, setResolvedMediaAssets] = useState<ResolvedMediaAsset[]>([]);
  const [expandedImage, setExpandedImage] = useState<ResolvedMediaAsset | null>(null);
  const autoSubmitAttemptedRef = useRef(false);

  const confirmedAt = String(context?.confirmed_at ?? "");
  const timerDurationSeconds = Number(context?.station_time_minutes ?? 0) * 60;
  const draftStorageKey = context ? `student-station-draft-${String(context.checkin_id)}` : "";
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
      if (!mediaAssets.length || !token) {
        setResolvedMediaAssets([]);
        return;
      }

      try {
        const nextAssets = await Promise.all(
          mediaAssets.map(async (asset) => {
            const blob = await api.mediaFile(asset.id, token);
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
  }, [mediaAssets, token]);

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
    setSubmitted(Boolean(context?.student_response_exists));
    autoSubmitAttemptedRef.current = Boolean(context?.student_response_exists);
  }, [context]);

  useEffect(() => {
    if (!draftStorageKey || typeof window === "undefined") {
      setAnswers({});
      return;
    }
    const rawDraft = window.localStorage.getItem(draftStorageKey);
    if (!rawDraft) {
      setAnswers({});
      return;
    }
    try {
      const parsedDraft = JSON.parse(rawDraft) as Record<string, string | string[]>;
      setAnswers(parsedDraft);
    } catch {
      window.localStorage.removeItem(draftStorageKey);
    }
  }, [draftStorageKey]);

  useEffect(() => {
    if (!draftStorageKey || typeof window === "undefined" || submitted) {
      return;
    }
    window.localStorage.setItem(draftStorageKey, JSON.stringify(answers));
  }, [answers, draftStorageKey, submitted]);

  useEffect(() => {
    if (!context || !confirmedAt || !timerDurationSeconds) {
      setRemainingSeconds(timerDurationSeconds || null);
      return;
    }

    const updateTimer = () => {
      const elapsedSeconds = Math.max(
        0,
        Math.floor((Date.now() - new Date(confirmedAt).getTime()) / 1000),
      );
      setRemainingSeconds(Math.max(timerDurationSeconds - elapsedSeconds, 0));
    };

    updateTimer();
    const intervalId = window.setInterval(updateTimer, 1000);
    return () => window.clearInterval(intervalId);
  }, [context, confirmedAt, timerDurationSeconds]);

  const timerLabel = useMemo(() => {
    if (remainingSeconds === null) {
      return "Sin cronometro activo";
    }
    const minutes = Math.floor(remainingSeconds / 60);
    const seconds = remainingSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }, [remainingSeconds]);

  const resetToIdentification = (notice: string) => {
    setContext(null);
    setSubmitted(false);
    setAutoSubmitting(false);
    setExpandedImage(null);
    autoSubmitAttemptedRef.current = false;
    setAnswers({});
    setEcoeNumber("");
    setRemainingSeconds(null);
    setMessage(notice);
  };

  const submitResponse = async (reason: "manual" | "automatico") => {
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
      token!,
    );
    if (currentDraftStorageKey && typeof window !== "undefined") {
      window.localStorage.removeItem(currentDraftStorageKey);
    }
    resetToIdentification(
      reason === "automatico"
        ? "Se acabo el tiempo de la estacion. Tu respuesta fue enviada automaticamente."
        : "Respuesta enviada correctamente para tu estacion confirmada.",
    );
  };

  useEffect(() => {
    if (!context || submitted || autoSubmitting || remainingSeconds !== 0 || autoSubmitAttemptedRef.current) {
      return;
    }
    autoSubmitAttemptedRef.current = true;
    setAutoSubmitting(true);
    submitResponse("automatico")
      .catch((error) => {
        setMessage(error instanceof Error ? error.message : "No se pudo enviar automaticamente.");
        autoSubmitAttemptedRef.current = false;
      })
      .finally(() => setAutoSubmitting(false));
  }, [autoSubmitting, context, remainingSeconds, submitted]);

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

  return (
    <SectionCard
      title="Interfaz del estudiante"
      subtitle="Primero verifica tu Numero ECOE y tu nombre; solo despues de la confirmacion del evaluador se habilita el envio."
    >
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
              Verificacion de ingreso
            </p>
            <h3 className="mt-2 text-2xl text-slate-900">Confirma tu identidad</h3>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Tiempo visible de la estacion
            </p>
            <p className="mt-2 text-3xl font-semibold text-slate-900">{timerLabel}</p>
            <p className="mt-2 text-sm text-slate-600">
              Tus respuestas se guardan localmente mientras escribes y se enviaran automaticamente
              al terminar el tiempo si aun no las has enviado.
            </p>
          </div>

          <form
            className="space-y-4"
            onSubmit={async (event) => {
              event.preventDefault();
              setMessage(null);
              try {
                const response = (await api.studentAccess(
                  { ecoe_event_id: eventId, ecoe_number: ecoeNumber },
                  token!,
                )) as Record<string, unknown>;
                setContext(response);
                setSubmitted(Boolean(response.student_response_exists));
                setMessage("Ingreso verificado correctamente.");
              } catch (error) {
                setContext(null);
                setMessage(error instanceof Error ? error.message : "No se pudo verificar.");
              }
            }}
          >
            <label className="space-y-2">
              <span className="text-sm font-semibold text-slate-700">Numero ECOE</span>
              <input
                value={ecoeNumber}
                onChange={(event) => setEcoeNumber(event.target.value)}
                placeholder="Ejemplo: 008"
              />
            </label>
            <button className="btn-primary w-full">Verificar mi ingreso</button>
          </form>

          {context ? (
            <div className="rounded-3xl border border-teal-200 bg-teal-50/80 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-700">
                Datos confirmados
              </p>
              <p className="mt-3 text-lg font-semibold text-slate-900">
                {String(context.student_ecoe_number)} · {String(context.student_name)}
              </p>
              <p className="mt-2 text-sm text-slate-600">
                Estacion {String(context.station_number)} - {String(context.station_name)}
              </p>
            </div>
          ) : (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              Tu respuesta solo se habilita cuando el evaluador confirma tu ingreso en la estacion.
            </div>
          )}
        </section>

        <section className="space-y-4 rounded-3xl border border-slate-200 bg-white/80 p-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Respuesta en estacion
            </p>
            <h3 className="mt-2 text-2xl text-slate-900">Formulario del estudiante</h3>
          </div>

          {context ? (
            <>
              <div className="rounded-3xl border border-teal-200 bg-teal-50/80 p-6">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-700">
                  Instrucciones dentro de la estacion
                </p>
                <p className="mt-4 text-xl font-semibold leading-8 text-slate-900 md:text-2xl md:leading-9">
                  {String(
                    context.student_station_instruction ??
                      "Sin instrucciones especificas registradas para esta estacion.",
                  )}
                </p>
              </div>
              {resolvedMediaAssets.length ? (
                <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5">
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
                onSubmit={async (event) => {
                  event.preventDefault();
                  const confirmed = window.confirm(
                    "Vas a enviar tu respuesta final. Luego no podras modificarla. ¿Quieres continuar?",
                  );
                  if (!confirmed) {
                    return;
                  }
                  setMessage(null);
                  try {
                    await submitResponse("manual");
                  } catch (error) {
                    setMessage(error instanceof Error ? error.message : "No se pudo enviar.");
                  }
                }}
              >
                {questions.length ? (
                  questions.map((question, index) => {
                    const fieldKey = `question_${index + 1}`;
                    const value = answers[fieldKey];

                    if (question.type === "short_text") {
                      return (
                        <label key={fieldKey} className="space-y-2">
                          <span className="text-sm font-semibold text-slate-900">
                            {question.label}
                          </span>
                          <textarea
                            rows={4}
                            value={typeof value === "string" ? value : ""}
                            disabled={submitted}
                            onChange={(event) => updateAnswer(index, event.target.value)}
                            placeholder="Escribe tu respuesta breve aqui."
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
                      <label key={fieldKey} className="space-y-2">
                        <span className="text-sm font-semibold text-slate-900">
                          {question.label}
                        </span>
                        <select
                          value={typeof value === "string" ? value : ""}
                          disabled={submitted}
                          onChange={(event) => updateAnswer(index, event.target.value)}
                        >
                          <option value="">Selecciona una opcion</option>
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
                    Esta estacion no tiene preguntas configuradas para el estudiante. Si necesitas
                    responder en pantalla, vuelve al constructor y guarda el formulario del estudiante.
                  </div>
                )}
                <button className="btn-primary w-full text-base" disabled={submitted || autoSubmitting}>
                  {submitted
                    ? "Respuesta ya enviada"
                    : autoSubmitting
                      ? "Enviando automaticamente..."
                      : "Enviar respuesta final"}
                </button>
                {submitted ? (
                  <p className="text-sm text-amber-700">
                    Esta respuesta ya fue enviada y quedo cerrada para cambios.
                  </p>
                ) : null}
              </form>
            </>
          ) : (
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
              Ingresa primero tu Numero ECOE para activar la vista completa de la estacion. Cuando
              termines de enviar, esta pantalla volvera automaticamente a este paso de identificacion.
            </div>
          )}
        </section>
      </div>
      {message ? <p className="mt-4 text-sm text-slate-600">{message}</p> : null}
    </SectionCard>
  );
}
