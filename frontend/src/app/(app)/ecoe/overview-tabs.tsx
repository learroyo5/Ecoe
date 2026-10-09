"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { api } from "@/lib/api";
import { roleLabel, stationStatusLabel, stationTypeLabel } from "@/lib/labels";
import { SectionCard } from "@/components/section-card";
import type { PilotRun, StaffAssignment, Station, Student } from "@/lib/types";

export type OverviewTab = "estaciones" | "participantes" | "pilotajes";

function ManageLink({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} className="font-semibold text-[var(--color-primary)] hover:underline">
      {label} &rarr;
    </Link>
  );
}

/**
 * Resumen de sólo lectura del ECOE activo (estaciones, participantes,
 * pilotajes) para las pestañas de Datos del ECOE. La edición vive en la
 * pantalla de cada dominio, enlazada desde cada tarjeta.
 */
export function EcoeOverviewTabs({ eventId, tab }: { eventId: number; tab: OverviewTab }) {
  const [stations, setStations] = useState<Station[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [staff, setStaff] = useState<StaffAssignment[]>([]);
  const [pilotage, setPilotage] = useState<PilotRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!eventId) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [st, stu, sf, p] = await Promise.all([
          api.stations(eventId) as Promise<Station[]>,
          api.students(eventId),
          api.staff(eventId),
          api.pilotage(eventId) as Promise<PilotRun[]>,
        ]);
        if (cancelled) return;
        setStations(st);
        setStudents(stu.items);
        setStaff(sf.items);
        setPilotage(p);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Error al cargar los datos");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [eventId]);

  if (loading) return <div className="h-60 animate-pulse rounded-3xl bg-slate-100" />;
  if (error) {
    return (
      <SectionCard title="No se pudo cargar el resumen">
        <p className="text-sm text-red-600">{error}</p>
      </SectionCard>
    );
  }

  const activeStudents = students.filter((s) => s.is_active);
  const evaluators = staff.filter((s) => s.role_code === "evaluador");
  const collaborators = staff.filter((s) => s.role_code !== "evaluador");

  return (
    <>
      {tab === "estaciones" ? (
        <SectionCard title={`Estaciones (${stations.length})`} subtitle={<ManageLink href="/stations" label="Gestionar estaciones" />}>
          {stations.length === 0 ? (
            <p className="text-sm text-slate-500">No hay estaciones configuradas.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                    <th className="pb-2 pr-4">#</th>
                    <th className="pb-2 pr-4">Nombre</th>
                    <th className="pb-2 pr-4">Tipo</th>
                    <th className="pb-2 pr-4">Circuito</th>
                    <th className="pb-2 pr-4">Puntaje máx.</th>
                    <th className="pb-2 pr-4">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {stations.map((st) => (
                    <tr key={st.id} className="hover:bg-slate-50/50">
                      <td className="py-2 pr-4 font-medium">{st.station_number}</td>
                      <td className="py-2 pr-4 font-medium text-slate-900">{st.name}</td>
                      <td className="py-2 pr-4 text-slate-600">{stationTypeLabel(st.station_type)}</td>
                      <td className="py-2 pr-4 text-slate-600">{st.circuit_name}</td>
                      <td className="py-2 pr-4">{st.max_score}</td>
                      <td className="py-2 pr-4">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
                          st.status === "activa" ? "bg-emerald-100 text-emerald-700" :
                          st.status === "publicada" ? "bg-blue-100 text-blue-700" :
                          "bg-slate-100 text-slate-600"
                        }`}>
                          {stationStatusLabel(st.status)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      ) : tab === "participantes" ? (
        <div className="space-y-6">
          <SectionCard title={`Estudiantes activos (${activeStudents.length})`} subtitle={<>{students.length} totales cargados. <ManageLink href="/students" label="Gestionar estudiantes" /></>}>
            {students.length === 0 ? (
              <p className="text-sm text-slate-500">No hay estudiantes cargados.</p>
            ) : (
              <div className="overflow-x-auto max-h-72">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                      <th className="pb-2 pr-4">N° ECOE</th>
                      <th className="pb-2 pr-4">Nombre</th>
                      <th className="pb-2 pr-4">RUT</th>
                      <th className="pb-2 pr-4">Grupo</th>
                      <th className="pb-2">Activo</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {students.slice(0, 50).map((s) => (
                      <tr key={s.id} className="hover:bg-slate-50/50">
                        <td className="py-2 pr-4 font-mono text-xs">{s.ecoe_number}</td>
                        <td className="py-2 pr-4 font-medium text-slate-900">{s.name} {s.last_name}</td>
                        <td className="py-2 pr-4 text-slate-600">{s.rut}</td>
                        <td className="py-2 pr-4 text-slate-600">{s.group_name}</td>
                        <td className="py-2">
                          <span
                            className={`pill ${
                              s.is_active
                                ? "pill-ok"
                                : "border border-amber-300 bg-[var(--color-warning-soft)] text-amber-900"
                            }`}
                          >
                            {s.is_active ? "Activo" : "Inactivo"}
                          </span>
                        </td>
                      </tr>
                    ))}
                    {students.length > 50 ? (
                      <tr><td colSpan={5} className="py-2 text-center text-xs text-slate-400">Mostrando 50 de {students.length} estudiantes</td></tr>
                    ) : null}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>

          <SectionCard title={`Evaluadores (${evaluators.length})`} subtitle={<ManageLink href="/evaluators" label="Gestionar equipo" />}>
            {evaluators.length === 0 ? (
              <p className="text-sm text-slate-500">No hay evaluadores asignados.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                      <th className="pb-2 pr-4">Nombre</th>
                      <th className="pb-2 pr-4">Email</th>
                      <th className="pb-2 pr-4">Estaciones asignadas</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {evaluators.map((ev) => (
                      <tr key={ev.id} className="hover:bg-slate-50/50">
                        <td className="py-2 pr-4 font-medium text-slate-900">{ev.name} {ev.last_name}</td>
                        <td className="py-2 pr-4 text-slate-600">{ev.email}</td>
                        <td className="py-2 pr-4 text-slate-600">{(ev.station_ids ?? []).join(", ") || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>

          {collaborators.length > 0 ? (
            <SectionCard title={`Colaboradores (${collaborators.length})`} subtitle="Coordinadores, cronometradores y otros roles.">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-100 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                      <th className="pb-2 pr-4">Nombre</th>
                      <th className="pb-2 pr-4">Email</th>
                      <th className="pb-2 pr-4">Rol</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {collaborators.map((c) => (
                      <tr key={c.id} className="hover:bg-slate-50/50">
                        <td className="py-2 pr-4 font-medium text-slate-900">{c.name} {c.last_name}</td>
                        <td className="py-2 pr-4 text-slate-600">{c.email}</td>
                        <td className="py-2 pr-4">
                          <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
                            {roleLabel(c.role_code)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </SectionCard>
          ) : null}
        </div>
      ) : tab === "pilotajes" ? (
        <SectionCard title={`Pilotajes (${pilotage.length})`} subtitle={<ManageLink href="/pilotage" label="Ir a Pilotaje" />}>
          {pilotage.length === 0 ? (
            <p className="text-sm text-slate-500">No se han realizado pilotajes.</p>
          ) : (
            <div className="space-y-3">
              {pilotage.map((p) => (
                <div key={p.id} className="rounded-2xl border border-slate-200 bg-white p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-semibold text-slate-900">{p.name}</p>
                      <p className="text-sm text-slate-500">Alcance: {p.scope} · {new Date(p.created_at).toLocaleDateString("es-CL")}</p>
                    </div>
                    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                      p.archived ? "bg-gray-100 text-gray-500" : "bg-amber-100 text-amber-700"
                    }`}>
                      {p.archived ? "Archivado" : "Activo"}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      ) : null}
    </>
  );
}
