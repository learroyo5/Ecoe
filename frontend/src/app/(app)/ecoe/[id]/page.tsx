"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { SectionCard } from "@/components/section-card";
import { StatusTransitionBar, STATUS_LABELS, STATUS_COLORS } from "@/components/ecoe-form";
import type { ECOEEvent, Station, Student, StaffAssignment, PilotRun } from "@/lib/types";

type Tab = "general" | "estaciones" | "participantes" | "pilotajes";

const TABS: { key: Tab; label: string }[] = [
  { key: "general", label: "General" },
  { key: "estaciones", label: "Estaciones" },
  { key: "participantes", label: "Participantes" },
  { key: "pilotajes", label: "Pilotajes" },
];

export default function ECOEDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { token, setEventId } = useECOE();
  const eventId = Number(params.id);

  const [tab, setTab] = useState<Tab>("general");
  const [ecoe, setEcoe] = useState<ECOEEvent | null>(null);
  const [stations, setStations] = useState<Station[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [staff, setStaff] = useState<StaffAssignment[]>([]);
  const [pilotage, setPilotage] = useState<PilotRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [transitioning, setTransitioning] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!token || Number.isNaN(eventId)) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [e, st, stu, sf, p] = await Promise.all([
          api.ecoe(eventId, token!) as Promise<ECOEEvent>,
          api.stations(eventId, token!) as Promise<Station[]>,
          api.students(eventId, token!) as Promise<Student[]>,
          api.staff(eventId, token!) as Promise<StaffAssignment[]>,
          api.pilotage(eventId, token!) as Promise<PilotRun[]>,
        ]);
        if (cancelled) return;
        setEcoe(e);
        setStations(st);
        setStudents(stu);
        setStaff(sf);
        setPilotage(p);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Error al cargar los datos");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [eventId, token]);

  const handleStatusTransition = async (targetStatus: string) => {
    if (!ecoe) return;
    setTransitioning(true); setMessage(null);
    try {
      const updated = await api.updateECOE(
        ecoe.id,
        {
          name: ecoe.name, date: ecoe.date,
          course_name: ecoe.course_name, school_name: ecoe.school_name,
          responsible_teacher: ecoe.responsible_teacher, contact_email: ecoe.contact_email,
          circuit_mode: ecoe.circuit_mode, total_stations: ecoe.total_stations,
          station_time_minutes: ecoe.station_time_minutes, transition_time_minutes: ecoe.transition_time_minutes,
          total_students: ecoe.total_students, total_groups: ecoe.total_groups,
          passing_reference_percent: ecoe.passing_reference_percent,
          status: targetStatus,
        },
        token!,
      ) as ECOEEvent;
      setEcoe(updated);
      setMessage(`Estado actualizado a: ${targetStatus.replace(/_/g, " ")}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Error al cambiar estado.");
    } finally {
      setTransitioning(false);
    }
  };

  const handleSelectECOE = () => {
    setEventId(eventId);
    router.push("/ecoe");
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-8 w-64 rounded-lg bg-slate-100" />
        <div className="h-40 rounded-3xl bg-slate-100" />
        <div className="h-60 rounded-3xl bg-slate-100" />
      </div>
    );
  }

  if (error || !ecoe) {
    return (
      <div className="space-y-4">
        <Link href="/ecoe" className="text-sm text-[var(--color-primary)] hover:underline">&larr; Volver a Gestión ECOE</Link>
        <SectionCard title="Error">
          <p className="text-red-600">{error ?? "ECOE no encontrado"}</p>
        </SectionCard>
      </div>
    );
  }

  const statusLabel = STATUS_LABELS[ecoe.status] ?? ecoe.status;
  const statusColor = STATUS_COLORS[ecoe.status] ?? "bg-slate-100 text-slate-700";

  const evaluators = staff.filter((s) => s.role_code === "evaluador");
  const collaborators = staff.filter((s) => s.role_code !== "evaluador");
  const activeStudents = students.filter((s) => s.is_active);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href="/ecoe" className="text-sm text-[var(--color-primary)] hover:underline">&larr; Gestión ECOE</Link>
          <h1 className="mt-1 text-2xl font-bold text-slate-900">{ecoe.name}</h1>
          <p className="text-sm text-slate-500">{ecoe.course_name} · {ecoe.school_name}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-primary" onClick={handleSelectECOE}>
            Editar en Gestión
          </button>
          <button className="btn-secondary" onClick={() => {
            router.push(`/ecoe?id=${eventId}`);
          }}>
            Duplicar
          </button>
        </div>
      </div>

      {message ? (
        <div className={`rounded-2xl px-4 py-3 text-sm font-medium ${
          message.startsWith("Error") ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"
        }`}>
          {message}
        </div>
      ) : null}

      {/* Status bar */}
      <StatusTransitionBar
        currentStatus={ecoe.status}
        onTransition={handleStatusTransition}
        loading={transitioning}
      />

      {/* Tabs */}
      <div className="flex gap-1 rounded-2xl bg-slate-100 p-1 w-fit">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
              tab === t.key
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "general" ? (
        <SectionCard title="Datos generales">
          <div className="grid gap-4 md:grid-cols-2">
            <DetailItem label="Nombre" value={ecoe.name} />
            <DetailItem label="Fecha" value={ecoe.date} />
            <DetailItem label="Curso" value={ecoe.course_name} />
            <DetailItem label="Escuela" value={ecoe.school_name} />
            <DetailItem label="Docente responsable" value={ecoe.responsible_teacher} />
            <DetailItem label="Contacto" value={ecoe.contact_email} />
            <DetailItem label="Modo de circuito" value={ecoe.circuit_mode?.replace(/_/g, " ")} />
            <DetailItem label="Estado" value={
              <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${statusColor}`}>
                {statusLabel}
              </span>
            } />
          </div>

          <hr className="my-4 border-slate-100" />

          <div className="grid gap-4 md:grid-cols-2">
            <DetailItem label="Total de estaciones" value={String(ecoe.total_stations)} />
            <DetailItem label="Minutos por estación" value={`${ecoe.station_time_minutes} min`} />
            <DetailItem label="Minutos de transición" value={`${ecoe.transition_time_minutes} min`} />
            <DetailItem label="Total de estudiantes" value={String(ecoe.total_students)} />
            <DetailItem label="Total de grupos" value={String(ecoe.total_groups)} />
            <DetailItem label="% Aprobación" value={`${ecoe.passing_reference_percent}%`} />
          </div>
        </SectionCard>
      ) : tab === "estaciones" ? (
        <SectionCard title={`Estaciones (${stations.length})`} subtitle="Estaciones vinculadas a este ECOE.">
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
                      <td className="py-2 pr-4 text-slate-600">{st.station_type}</td>
                      <td className="py-2 pr-4 text-slate-600">{st.circuit_name}</td>
                      <td className="py-2 pr-4">{st.max_score}</td>
                      <td className="py-2 pr-4">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
                          st.status === "activa" ? "bg-emerald-100 text-emerald-700" :
                          st.status === "publicada" ? "bg-blue-100 text-blue-700" :
                          "bg-slate-100 text-slate-600"
                        }`}>
                          {st.status}
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
          <SectionCard title={`Estudiantes activos (${activeStudents.length})`} subtitle={`${students.length} totales cargados.`}>
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
                        <td className="py-2">{s.is_active ? "✅" : "❌"}</td>
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

          <SectionCard title={`Evaluadores (${evaluators.length})`} subtitle="Personal asignado a este ECOE.">
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
                            {c.role_code}
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
        <SectionCard title={`Pilotajes (${pilotage.length})`} subtitle="Ejecuciones de prueba realizadas.">
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
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white p-3">
      <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</p>
      <div className="mt-1 text-sm font-medium text-slate-900">{value}</div>
    </div>
  );
}
