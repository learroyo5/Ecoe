"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { canEditStations } from "@/lib/permissions";
import { defaultRouteForRole } from "@/lib/routes";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";
import {
  describeGuideSources,
  loadGuideSession,
  saveGuideSession,
  type GuideSession,
  type GuideStationSuggestion,
} from "@/lib/guide-draft";

const stationTypeLabels: Record<string, string> = {
  procedimental: "Procedimental",
  actitudinal: "Actitudinal",
  conceptual: "Conceptual",
};

const POLL_MS = 3000;
// El backend descarta el análisis a los 30 min; la pantalla se rinde antes.
const MAX_WAIT_MS = 6 * 60 * 1000;

function SuggestionCard({
  station,
  index,
  created,
}: {
  station: GuideStationSuggestion;
  index: number;
  created: boolean;
}) {
  const sources = describeGuideSources(station);
  const questions = station.student_form_definition.questions;
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-primary)]">
            Propuesta {index + 1} · {stationTypeLabels[station.station_type] ?? station.station_type}
            {station.suggested_minutes ? ` · ~${station.suggested_minutes} min` : ""}
          </p>
          <h4 className="mt-1 text-lg font-semibold text-slate-900">{station.name}</h4>
          {station.rationale ? <p className="mt-1 text-sm text-slate-600">{station.rationale}</p> : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {created ? (
            <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">
              Ya creada
            </span>
          ) : null}
          <Link
            href={`/stations/builder?guideStation=${index}`}
            className={created ? "btn-secondary" : "btn-primary"}
          >
            {created ? "Crear otra copia" : "Revisar y crear"}
          </Link>
        </div>
      </div>

      <dl className="mt-4 grid gap-3 text-sm md:grid-cols-2">
        <div>
          <dt className="font-semibold text-slate-800">Qué hace el estudiante</dt>
          <dd className="mt-1 whitespace-pre-line text-slate-600">{station.student_activity || "—"}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-800">Desempeños esperados</dt>
          <dd className="mt-1 whitespace-pre-line text-slate-600">{station.expected_outcomes || "—"}</dd>
        </div>
      </dl>

      {station.instrument ? (
        <details className="mt-3 rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2 text-sm">
          <summary className="cursor-pointer font-semibold text-slate-800">
            Pauta del evaluador: {station.instrument.items.length} criterios ·{" "}
            {station.instrument.max_score} puntos
          </summary>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-slate-600">
            {station.instrument.items.map((item, itemIndex) => (
              <li key={itemIndex}>
                {item.label} <span className="text-slate-400">({item.score_per_item} pt)</span>
              </li>
            ))}
          </ol>
        </details>
      ) : null}

      {questions.length ? (
        <details className="mt-3 rounded-xl border border-slate-200 bg-slate-50/70 px-3 py-2 text-sm">
          <summary className="cursor-pointer font-semibold text-slate-800">
            Formulario del estudiante: {questions.length} preguntas
          </summary>
          <ol className="mt-2 list-decimal space-y-2 pl-5 text-slate-600">
            {questions.map((question, questionIndex) => (
              <li key={questionIndex}>
                {question.label} <span className="text-slate-400">({question.points} pt)</span>
                {question.options.length ? (
                  <ul className="mt-1 list-disc pl-5">
                    {question.options.map((option) => {
                      const correct =
                        option === question.correct_option ||
                        (question.correct_options ?? []).includes(option);
                      return (
                        <li key={option} className={correct ? "font-semibold text-emerald-700" : ""}>
                          {option}
                          {correct ? " ✓" : ""}
                        </li>
                      );
                    })}
                  </ul>
                ) : null}
              </li>
            ))}
          </ol>
        </details>
      ) : null}

      <div className="mt-3 space-y-1 text-xs leading-5 text-slate-600">
        {sources.fromGuide.length ? (
          <p>
            <span className="font-semibold text-emerald-700">Tomado de la guía:</span>{" "}
            {sources.fromGuide.join(", ")}.
          </p>
        ) : null}
        {sources.fromAi.length ? (
          <p>
            <span className="font-semibold text-amber-700">Redactado por la IA, revísalo:</span>{" "}
            {sources.fromAi.join(", ")}.
          </p>
        ) : null}
        {sources.missing.length ? (
          <p>
            <span className="font-semibold text-slate-800">Falta completar:</span>{" "}
            {sources.missing.join(", ")}.
          </p>
        ) : null}
      </div>

      {station.warnings.length ? (
        <ul className="mt-3 space-y-1 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {station.warnings.map((warning, warningIndex) => (
            <li key={warningIndex}>⚠ {warning}</li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}

export default function StationsFromGuidePage() {
  const router = useRouter();
  const { authenticated, eventId, user, eventRoles, eventRolesLoaded } = useECOE();
  const canEdit = canEditStations(user?.role, eventRoles);
  const accessDenied = eventRolesLoaded && !canEdit;
  const { data: status, loading: statusLoading } = useApi(
    () => api.stationGuideStatus(),
    [authenticated],
  );
  const [file, setFile] = useState<File | null>(null);
  const [session, setSession] = useState<GuideSession | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cancelledRef = useRef(false);

  useEffect(() => {
    if (accessDenied) {
      router.replace(defaultRouteForRole(user?.role ?? ""));
    }
  }, [router, accessDenied, user?.role]);

  // Al volver del Constructor la propuesta sigue aquí (sessionStorage).
  useEffect(() => {
    if (eventId) setSession(loadGuideSession(eventId));
  }, [eventId]);

  useEffect(() => {
    cancelledRef.current = false;
    return () => {
      cancelledRef.current = true;
    };
  }, []);

  const analyze = async () => {
    if (!file) return;
    setError(null);
    setAnalyzing(true);
    try {
      const { job_id } = await api.suggestStationsFromGuide(eventId, file);
      const startedAt = Date.now();
      for (;;) {
        await new Promise((resolve) => window.setTimeout(resolve, POLL_MS));
        if (cancelledRef.current) return;
        const job = await api.stationGuideJob(job_id);
        if (job.status === "done" && job.result) {
          const next: GuideSession = { eventId, filename: file.name, result: job.result, created: [] };
          saveGuideSession(next);
          setSession(next);
          setFile(null);
          return;
        }
        if (job.status === "error") {
          throw new Error(job.error ?? "No se pudo analizar la guía.");
        }
        if (Date.now() - startedAt > MAX_WAIT_MS) {
          throw new Error("El análisis está tardando demasiado. Vuelve a intentarlo.");
        }
      }
    } catch (caught) {
      if (!cancelledRef.current) {
        setError(caught instanceof Error ? caught.message : "No se pudo analizar la guía.");
      }
    } finally {
      if (!cancelledRef.current) setAnalyzing(false);
    }
  };

  if (accessDenied) {
    return (
      <SectionCard title="Acceso restringido" subtitle="Tu rol en este ECOE no permite diseñar estaciones.">
        <p>Te estamos redirigiendo a tu interfaz operativa.</p>
      </SectionCard>
    );
  }

  const maxSizeMb = status?.max_size_mb ?? 20;
  const stations = session?.result.stations ?? [];

  return (
    <div className="space-y-6">
      <SectionCard
        title="Estaciones desde una guía de simulación"
        subtitle="Sube la guía de un práctico y el asistente propone una o más estaciones de ECOE. Nada se guarda solo: revisas cada propuesta en el Constructor antes de crearla."
      >
        {statusLoading ? (
          <p className="text-sm text-slate-500">Cargando…</p>
        ) : status && !status.enabled ? (
          <div role="alert" className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            El asistente de IA no está configurado en esta instalación. Pide a quien administra la
            plataforma que agregue la clave de API; mientras tanto puedes crear la estación desde cero o
            desde el banco.
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-3">
              <input
                type="file"
                aria-label="Guía de simulación"
                accept=".docx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                disabled={analyzing}
                onChange={(event) => {
                  const selected = event.target.files?.[0] ?? null;
                  setError(null);
                  if (selected && selected.size > maxSizeMb * 1024 * 1024) {
                    setFile(null);
                    setError(`El archivo excede el tamaño máximo de ${maxSizeMb} MB.`);
                    return;
                  }
                  setFile(selected);
                }}
                className="max-w-full text-sm"
              />
              <button
                type="button"
                className="btn-primary disabled:opacity-50"
                disabled={!file || analyzing}
                onClick={analyze}
              >
                {analyzing ? "Analizando la guía…" : "Proponer estaciones"}
              </button>
              <Link href="/stations" className="btn-secondary">
                Volver a Estaciones
              </Link>
            </div>
            <p className="text-xs leading-5 text-slate-500">
              Word (.docx) o PDF con texto, hasta {maxSizeMb} MB. El análisis tarda cerca de un minuto. Antes
              de enviar el texto al asistente se quitan nombre, RUT, teléfono y correo del docente; la guía
              no queda guardada en la plataforma. No subas documentos con datos de pacientes o estudiantes
              reales.
            </p>
            {analyzing ? (
              <p role="status" className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
                Leyendo la guía y armando las propuestas. Puedes dejar esta pantalla abierta; no la cierres.
              </p>
            ) : null}
            {error ? (
              <p role="alert" className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-900">
                {error}
              </p>
            ) : null}
          </div>
        )}
      </SectionCard>

      {session ? (
        <SectionCard
          title={session.result.guide_title || "Propuestas"}
          subtitle={`${stations.length} ${stations.length === 1 ? "estación propuesta" : "estaciones propuestas"} a partir de «${session.filename}».`}
        >
          {session.result.summary ? (
            <p className="text-sm leading-6 text-slate-700">{session.result.summary}</p>
          ) : null}
          {session.result.warnings.length ? (
            <ul className="space-y-1 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {session.result.warnings.map((warning, index) => (
                <li key={index}>⚠ {warning}</li>
              ))}
            </ul>
          ) : null}
          <div className="space-y-4">
            {stations.map((station, index) => (
              <SuggestionCard
                key={index}
                station={station}
                index={index}
                created={session.created.includes(index)}
              />
            ))}
          </div>
          <div>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                saveGuideSession(null);
                setSession(null);
              }}
            >
              Descartar estas propuestas
            </button>
          </div>
        </SectionCard>
      ) : null}
    </div>
  );
}
