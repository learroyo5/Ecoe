"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";

export default function PublicationPage() {
  const { token, eventId } = useAuth();
  const { data, setData } = useApi(
    () => api.validation(eventId, token!) as Promise<Record<string, unknown>>,
    [eventId, token],
  );
  const { data: ecoeEvent } = useApi(
    () => api.ecoe(eventId, token!) as Promise<Record<string, unknown>>,
    [eventId, token],
  );
  const blockers = ((data?.blockers as string[] | undefined) ?? []);
  const [message, setMessage] = useState<string | null>(null);
  const [publishing, setPublishing] = useState(false);
  const isPublished = String(ecoeEvent?.status ?? "") === "publicado";

  return (
    <SectionCard title="Publicacion" subtitle="Revision final antes de abrir la ejecucion real del ECOE y dejar listo el entorno operativo.">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="clinical-panel">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Estaciones completas</p>
          <p className="mt-3 text-3xl font-semibold">
            {String(data?.complete_stations ?? 0)} / {String(data?.station_count ?? 0)}
          </p>
        </div>
        <div className="clinical-panel">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Pilotajes realizados</p>
          <p className="mt-3 text-3xl font-semibold">{String(data?.pilot_count ?? 0)}</p>
        </div>
      </div>
      <div className="clinical-panel">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Estado actual del ECOE</p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <span className={`status-badge ${isPublished ? "status-badge-success" : "status-badge-info"}`}>
            {String(ecoeEvent?.status ?? "sin_estado")}
          </span>
          <p className="text-sm leading-6 text-slate-600">
            Publicar este ECOE deja creada la sesion en vivo base y marca las estaciones listas como publicadas.
          </p>
        </div>
        <button
          className="btn-primary mt-4"
          disabled={!data?.can_publish || isPublished || publishing}
          onClick={async () => {
            if (!ecoeEvent) {
              return;
            }
            const confirmed = window.confirm(
              "Vas a publicar este ECOE. La sesion en vivo quedara preparada y el evento pasara a estado publicado. ¿Quieres continuar?",
            );
            if (!confirmed) {
              return;
            }
            setPublishing(true);
            setMessage(null);
            try {
              await api.updateECOE(
                eventId,
                {
                  ...ecoeEvent,
                  status: "publicado",
                },
                token!,
              );
              const updatedValidation = (await api.validation(eventId, token!)) as Record<string, unknown>;
              setData(updatedValidation);
              setMessage("ECOE publicado correctamente. La base operativa para ejecucion real ya quedo preparada.");
            } catch (publishError) {
              setMessage(
                publishError instanceof Error
                  ? publishError.message
                  : "No se pudo publicar el ECOE.",
              );
            } finally {
              setPublishing(false);
            }
          }}
        >
          {isPublished ? "ECOE ya publicado" : publishing ? "Publicando..." : "Publicar ECOE"}
        </button>
      </div>
      <div className="rounded-[28px] bg-[linear-gradient(135deg,var(--color-primary-dark),var(--color-primary))] p-5 text-white shadow-[0_18px_40px_rgba(27,73,101,0.18)]">
        <p className="text-sm uppercase tracking-[0.18em] text-slate-100/80">Estado</p>
        <p className="mt-2 text-2xl font-semibold">
          {data?.can_publish ? "Listo para publicar" : "Aun no cumple validacion completa"}
        </p>
      </div>
      {blockers.length ? (
        <div className="space-y-3">
          {blockers.map((blocker) => (
            <div
              key={blocker}
              className="rounded-2xl border border-red-200 bg-[var(--color-error-soft)] px-4 py-3 text-sm text-red-900"
            >
              {blocker}
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-2xl border border-green-200 bg-[var(--color-success-soft)] px-4 py-3 text-sm text-green-900">
          No se detectan bloqueos estructurales. El ECOE puede avanzar a publicacion cuando corresponda operativamente.
        </div>
      )}
      {message ? <p className="text-sm text-slate-600">{message}</p> : null}
    </SectionCard>
  );
}
