"use client";

import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { FileImport, StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";

export default function EvaluatorsPage() {
  const { token, eventId } = useECOE();
  const { data: rawStaff, loading, error, setData: setRawStaff } = useApi(
    () => api.staff(eventId, token!) as unknown as Promise<Record<string, unknown>>,
    [eventId, token],
  );
  const data = (rawStaff?.items as Record<string, unknown>[]) ?? (Array.isArray(rawStaff) ? rawStaff as Record<string, unknown>[] : []);
  const { data: rawStations } = useApi(
    () => api.stations(eventId, token!) as Promise<Record<string, unknown>[]>,
    [eventId, token],
  );
  const stations = rawStations ?? [];
  const [form, setForm] = useState({
    name: "",
    last_name: "",
    email: "",
    role_code: "evaluador",
    station_id: "",
  });
  const [assignmentDrafts, setAssignmentDrafts] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [savingForm, setSavingForm] = useState(false);
  const [processingAction, setProcessingAction] = useState<string | null>(null);

  const refresh = async () => {
    const result = await api.staff(eventId, token!) as unknown as Record<string, unknown>;
    setRawStaff(result);
  };

  const stationOptions = (stations ?? []).map((station) => ({
    id: String(station.id),
    label: `${String(station.station_number)} - ${String(station.name)}`,
  }));

  return (
    <div className="space-y-6">
      <SectionCard
        title="Equipo operativo del ECOE"
        subtitle="Cada integrante debe tener cuenta activa con el rol correcto; los evaluadores además necesitan una estación principal."
      >
        <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <FileImport
            label="Importar evaluadores o colaboradores"
            helper={
              <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-3">
                <p>Usa un archivo Excel o CSV con estos encabezados:</p>
                <p className="font-semibold text-slate-800">
                  nombre | apellidos | correo | rol
                </p>
                <p>El orden puede cambiar, pero los nombres de columna deben coincidir.</p>
                <p>
                  El correo debe corresponder a una cuenta existente del sistema con el mismo rol.
                </p>
                <Link
                  href="/plantilla_evaluadores.csv"
                  className="inline-block font-semibold text-[var(--color-primary)] underline-offset-4 hover:underline"
                >
                  Descargar plantilla base CSV
                </Link>
              </div>
            }
            onImport={async (file) => {
              const response = (await api.importStaff(eventId, file, token!)) as {
                imported?: number;
                skipped?: number;
              };
              await refresh();
              return `Carga completada: ${response.imported ?? 0} evaluadores o colaboradores importados y ${response.skipped ?? 0} omitidos por correo duplicado.`;
            }}
          />

          <form
            className="grid gap-4 md:grid-cols-2"
            onSubmit={async (event) => {
              event.preventDefault();
              setMessage(null);
              setSavingForm(true);
              try {
                await api.createStaff(
                  {
                    ecoe_event_id: eventId,
                    name: form.name,
                    last_name: form.last_name,
                    email: form.email,
                    role_code: form.role_code,
                    station_ids: form.station_id ? [Number(form.station_id)] : [],
                  },
                  token!,
                );
                await refresh();
                setForm({
                  name: "",
                  last_name: "",
                  email: "",
                  role_code: "evaluador",
                  station_id: "",
                });
                setMessage("Evaluador o colaborador guardado correctamente.");
              } catch (error) {
                setMessage(error instanceof Error ? error.message : "No se pudo guardar.");
              } finally {
                setSavingForm(false);
              }
            }}
          >
            <label className="space-y-2 rounded-[22px] border border-slate-200 bg-white/80 p-4">
              <span className="text-sm font-semibold text-slate-700">Nombre</span>
              <input
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
              />
            </label>
            <label className="space-y-2 rounded-[22px] border border-slate-200 bg-white/80 p-4">
              <span className="text-sm font-semibold text-slate-700">Apellidos</span>
              <input
                value={form.last_name}
                onChange={(event) =>
                  setForm((current) => ({ ...current, last_name: event.target.value }))
                }
              />
            </label>
            <label className="space-y-2 rounded-[22px] border border-slate-200 bg-white/80 p-4">
              <span className="text-sm font-semibold text-slate-700">Correo</span>
              <input
                type="email"
                value={form.email}
                onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
              />
            </label>
            <label className="space-y-2 rounded-[22px] border border-slate-200 bg-white/80 p-4">
              <span className="text-sm font-semibold text-slate-700">Rol</span>
              <select
                value={form.role_code}
                onChange={(event) =>
                  setForm((current) => ({ ...current, role_code: event.target.value }))
                }
              >
                <option value="evaluador">Evaluador</option>
                <option value="coeditor_docente">Coeditor docente</option>
                <option value="coordinador_operativo">Coordinador operativo</option>
                <option value="cronometrador">Cronometrador</option>
              </select>
            </label>
            <label className="space-y-2 rounded-[22px] border border-slate-200 bg-white/80 p-4 md:col-span-2">
              <span className="text-sm font-semibold text-slate-700">Estación principal asignada</span>
              <select
                value={form.station_id}
                onChange={(event) =>
                  setForm((current) => ({ ...current, station_id: event.target.value }))
                }
              >
                <option value="">Sin estación asignada por ahora</option>
                {stationOptions.map((station) => (
                  <option key={station.id} value={station.id}>
                    {station.label}
                  </option>
                ))}
              </select>
              <p className="text-xs leading-5 text-slate-500">
                Si el rol es evaluador, esta estación es obligatoria. Coeditores, coordinadores y
                cronometradores pueden quedar sin estación principal.
              </p>
            </label>
            <div className="space-y-3 md:col-span-2">
              <button className="btn-primary" disabled={savingForm}>
                {savingForm ? "Guardando..." : "Guardar asignación"}
              </button>
              <StatusNotice message={message} />
            </div>
          </form>
        </div>
      </SectionCard>

      <SectionCard title="Equipo operativo" subtitle="Las asignaciones quedan amarradas al ECOE activo y deben coincidir con la cuenta real de cada persona.">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="btn-secondary"
            onClick={async () => {
              const confirmed = window.confirm(
                "Se revisará el equipo operativo de este ECOE y se borrarán los duplicados por correo, conservando el primer registro cargado. ¿Quieres continuar?",
              );
              if (!confirmed) {
                setMessage("La limpieza de duplicados fue cancelada.");
                return;
              }
              setProcessingAction("deduplicate-staff");
              setMessage(null);
              try {
                const response = (await api.deduplicateStaffByEmail(eventId, token!)) as {
                  removed?: number;
                };
                await refresh();
                setMessage(
                  `Limpieza completada: ${response.removed ?? 0} registros duplicados fueron eliminados.`,
                );
              } catch (actionError) {
                setMessage(
                  actionError instanceof Error
                    ? actionError.message
                    : "No se pudo completar la limpieza de duplicados.",
                );
              } finally {
                setProcessingAction(null);
              }
            }}
            disabled={processingAction === "deduplicate-staff"}
          >
            {processingAction === "deduplicate-staff"
              ? "Limpiando duplicados..."
              : "Limpiar duplicados por correo"}
          </button>
          <p className="text-sm text-slate-600">
            Cada evaluador debería tener una sola estación principal asignada, aunque puedes
            corregirla después si hay contingencia.
          </p>
        </div>
        <StatusNotice message={message} />
        {loading ? (
          <p>Cargando equipo...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={data ?? []}
            columns={[
              { key: "name", label: "Nombre" },
              { key: "last_name", label: "Apellidos" },
              { key: "email", label: "Correo" },
              { key: "role_code", label: "Rol" },
              {
                key: "station_ids",
                label: "Estación principal",
                render: (row) => {
                  const stationId = String(((row as { station_ids?: number[] }).station_ids ?? [])[0] ?? "");
                  const station = stationOptions.find((item) => item.id === stationId);
                  return station?.label ?? "Sin asignar";
                },
              },
              {
                key: "assignment",
                label: "Reasignar",
                render: (row) => {
                  const staff = row as {
                    id?: number;
                    role_code?: string;
                    station_ids?: number[];
                  };
                  const staffId = String(staff.id ?? "");
                  const currentStationId = String((staff.station_ids ?? [])[0] ?? "");
                  const selectedStationId = assignmentDrafts[staffId] ?? currentStationId;

                  return (
                    <div className="flex min-w-[260px] flex-wrap items-center gap-2">
                      <select
                        value={selectedStationId}
                        onChange={(event) =>
                          setAssignmentDrafts((current) => ({
                            ...current,
                            [staffId]: event.target.value,
                          }))
                        }
                      >
                        <option value="">Sin estación asignada</option>
                        {stationOptions.map((station) => (
                          <option key={station.id} value={station.id}>
                            {station.label}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={async () => {
                          setProcessingAction(`assign-${staffId}`);
                          setMessage(null);
                          try {
                            await api.updateStaff(
                              Number(staff.id),
                              {
                                role_code: String(staff.role_code ?? "evaluador"),
                                station_ids: selectedStationId ? [Number(selectedStationId)] : [],
                              },
                              token!,
                            );
                            await refresh();
                            setMessage("Asignación principal actualizada correctamente.");
                          } catch (actionError) {
                            setMessage(
                              actionError instanceof Error
                                ? actionError.message
                                : "No se pudo actualizar la asignación principal.",
                            );
                          } finally {
                            setProcessingAction(null);
                          }
                        }}
                        disabled={processingAction === `assign-${staffId}`}
                      >
                        {processingAction === `assign-${staffId}` ? "Guardando..." : "Guardar"}
                      </button>
                    </div>
                  );
                },
              },
              {
                key: "actions",
                label: "Acciones",
                render: (row) => {
                  const staff = row as { id?: number };
                  return (
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={async () => {
                        const confirmed = window.confirm(
                          "Vas a borrar este evaluador o colaborador de forma permanente. Esta acción no se puede deshacer. ¿Quieres continuar?",
                        );
                        if (!confirmed) {
                          setMessage("El borrado del evaluador o colaborador fue cancelado.");
                          return;
                        }
                        setProcessingAction(`delete-${String(staff.id ?? "")}`);
                        setMessage(null);
                        try {
                          await api.deleteStaff(Number(staff.id), token!);
                          await refresh();
                          setMessage("Evaluador o colaborador borrado correctamente.");
                        } catch (actionError) {
                          setMessage(
                            actionError instanceof Error
                              ? actionError.message
                              : "No se pudo borrar el evaluador o colaborador.",
                          );
                        } finally {
                          setProcessingAction(null);
                        }
                      }}
                      disabled={processingAction === `delete-${String(staff.id ?? "")}`}
                    >
                      {processingAction === `delete-${String(staff.id ?? "")}`
                        ? "Borrando..."
                        : "Borrar"}
                    </button>
                  );
                },
              },
            ]}
          />
        )}
      </SectionCard>
    </div>
  );
}
