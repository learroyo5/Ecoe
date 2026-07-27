"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { FileImport, StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";

export default function EvaluatorsPage() {
  const { authenticated, eventId, eventRoles, user } = useECOE();
  const canInviteMembers = user?.role === "admin_global" || eventRoles.includes("admin_ecoe");
  const { data: rawStaff, loading, error, setData: setRawStaff } = useApi(
    () => api.staff(eventId),
    [eventId, authenticated],
  );
  const data = rawStaff?.items ?? [];

  // Count current staff by role for validation warnings
  const roleCounts: Record<string, number> = {};
  for (const s of data) {
    const rc = String((s as { role_code?: string }).role_code ?? "");
    roleCounts[rc] = (roleCounts[rc] ?? 0) + 1;
  }

  const SINGLE_ROLE_WARNINGS: Record<string, string> = {
    coordinador_operativo: "Ya existe un coordinador operativo en este ECOE. Normalmente basta con uno. ¿Agregar otro de todas formas?",
    cronometrador: "Ya existe un cronometrador en este ECOE. Normalmente basta con uno. ¿Agregar otro de todas formas?",
  };
  const { data: rawStations } = useApi(
    () => api.stations(eventId) as Promise<Record<string, unknown>[]>,
    [eventId, authenticated],
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
  const [lookupMessage, setLookupMessage] = useState<string | null>(null);
  const [activationLink, setActivationLink] = useState<string | null>(null);
  const [savingForm, setSavingForm] = useState(false);
  const [processingAction, setProcessingAction] = useState<string | null>(null);

  const refresh = async () => {
    const result = await api.staff(eventId);
    setRawStaff(result);
  };

  const stationOptions = (stations ?? []).map((station) => ({
    id: String(station.id),
    label: `${String(station.station_number)} - ${String(station.name)}`,
  }));

  return (
    <div className="space-y-6">
      {/* Team composition summary */}
      <SectionCard title="Composición del equipo" subtitle="Roles requeridos y estado actual de asignación.">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { role: "coeditor_docente", label: "Coeditor", min: 1, max: Infinity },
            { role: "coordinador_operativo", label: "Coord. operativo", min: 1, max: 1 },
            { role: "cronometrador", label: "Cronometrador", min: 1, max: 1 },
          ].map(({ role, label, min, max }) => {
            const count = roleCounts[role] ?? 0;
            const ok = count >= min;
            const over = max < Infinity && count > max;
            return (
              <div
                key={role}
                className={`rounded-2xl border p-3 ${
                  ok && !over
                    ? "border-emerald-200 bg-emerald-50/60"
                    : "border-amber-200 bg-amber-50/60"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-slate-800">{label}</span>
                  <span className={`text-lg font-bold ${ok && !over ? "text-emerald-600" : "text-amber-600"}`}>
                    {count}
                  </span>
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {ok && !over
                    ? "✓ Asignado"
                    : count === 0
                      ? `Falta asignar (mín. ${min})`
                      : `Revisar: hay ${count}, recomendado ${max}`}
                </p>
              </div>
            );
          })}
        </div>
        <p className="mt-3 text-xs text-slate-500">
          El rol Admin se asigna automáticamente al crear el ECOE y no aparece en esta lista.
          Evaluadores: {roleCounts["evaluador"] ?? 0} asignados. Sin limite maximo.
        </p>
      </SectionCard>

      <SectionCard
        title="Equipo operativo del ECOE"
        subtitle="Asigna una cuenta existente o genera una invitación temporal; los evaluadores además necesitan una estación principal."
      >
        <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <FileImport
            label="Importar evaluadores o colaboradores"
            helper={
              <div className="space-y-4">
                <div className="rounded-2xl border border-blue-200 bg-blue-50/60 p-4">
                  <p className="text-sm font-semibold text-blue-900">Como preparar tu archivo</p>
                  <ol className="mt-2 list-inside list-decimal space-y-1 text-xs leading-5 text-blue-800">
                    <li>Descarga la plantilla Excel o CSV usando los botones de abajo.</li>
                    <li>Abre el archivo y completa una fila por cada persona.</li>
                    <li>Los unicos campos obligatorios son: <strong>nombre, apellidos, correo, rol</strong>.</li>
                    <li>Para importación masiva, el <strong>correo</strong> debe corresponder a una cuenta institucional activa.</li>
                    <li>Roles validos: <strong>evaluador</strong>, <strong>coeditor_docente</strong>, <strong>coordinador_operativo</strong>, <strong>cronometrador</strong>.</li>
                    <li>Guarda el archivo y arrastralo o seleccionalo en el campo de abajo.</li>
                  </ol>
                </div>

                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Columnas del archivo</p>
                  <div className="mt-2 overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-slate-100 text-left text-slate-500">
                          <th className="pb-1 pr-3 font-semibold">Columna</th>
                          <th className="pb-1 pr-3 font-semibold">Obligatorio</th>
                          <th className="pb-1 font-semibold">Descripción</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50">
                        <tr><td className="py-1 pr-3 font-mono text-slate-700">nombre</td><td className="py-1 pr-3 text-emerald-600">Sí</td><td className="py-1 text-slate-500">Nombre de la persona</td></tr>
                        <tr><td className="py-1 pr-3 font-mono text-slate-700">apellidos</td><td className="py-1 pr-3 text-emerald-600">Sí</td><td className="py-1 text-slate-500">Apellidos completos</td></tr>
                        <tr><td className="py-1 pr-3 font-mono text-slate-700">correo</td><td className="py-1 pr-3 text-emerald-600">Sí</td><td className="py-1 text-slate-500">Correo de una cuenta institucional activa</td></tr>
                        <tr><td className="py-1 pr-3 font-mono text-slate-700">rol</td><td className="py-1 pr-3 text-emerald-600">Sí</td><td className="py-1 text-slate-500">evaluador | coeditor_docente | coordinador_operativo | cronometrador</td></tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <a
                    href="/plantilla_evaluadores.xlsx"
                    download
                    className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-emerald-700"
                  >
                    <svg className="size-4" viewBox="0 0 20 20" fill="currentColor"><path d="M10 2a1 1 0 011 1v7.586l2.293-2.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L9 10.586V3a1 1 0 011-1z"/><path fillRule="evenodd" d="M3 14a2 2 0 012-2h10a2 2 0 012 2v2a2 2 0 01-2 2H5a2 2 0 01-2-2v-2zm2 0v2h10v-2H5z" clipRule="evenodd"/></svg>
                    Plantilla Excel
                  </a>
                  <a
                    href="/plantilla_evaluadores.csv"
                    download
                    className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
                  >
                    <svg className="size-4" viewBox="0 0 20 20" fill="currentColor"><path d="M10 2a1 1 0 011 1v7.586l2.293-2.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L9 10.586V3a1 1 0 011-1z"/><path fillRule="evenodd" d="M3 14a2 2 0 012-2h10a2 2 0 012 2v2a2 2 0 01-2 2H5a2 2 0 01-2-2v-2zm2 0v2h10v-2H5z" clipRule="evenodd"/></svg>
                    Plantilla CSV
                  </a>
                </div>
              </div>
            }
            onImport={async (file) => {
              const response = (await api.importStaff(eventId, file)) as {
                imported?: number;
                skipped?: number;
                skipped_duplicate?: number;
                skipped_no_account?: number;
                skipped_missing_data?: number;
              };
              await refresh();
              const imported = response.imported ?? 0;
              const dupes = response.skipped_duplicate ?? 0;
              const noAcct = response.skipped_no_account ?? 0;
              const missing = response.skipped_missing_data ?? 0;
              const parts: string[] = [`${imported} evaluadores importados.`];
              if (dupes > 0) parts.push(`${dupes} omitidos por correo duplicado en este ECOE.`);
              if (noAcct > 0) parts.push(`${noAcct} omitidos: no existe cuenta de usuario con ese rol. Crea el usuario primero en Usuarios.`);
              if (missing > 0) parts.push(`${missing} omitidos por falta de datos.`);
              return parts.join(" ");
            }}
          />

          <form
            className="grid gap-4 md:grid-cols-2"
            onSubmit={async (event) => {
              event.preventDefault();
              setMessage(null);
              if (!canInviteMembers) {
                setMessage("Solo un administrador del ECOE puede invitar nuevas cuentas.");
                return;
              }

              // Warn if adding a duplicate single-role staff member
              const warning = SINGLE_ROLE_WARNINGS[form.role_code];
              if (warning && (roleCounts[form.role_code] ?? 0) > 0) {
                if (!window.confirm(warning)) return;
              }

              setSavingForm(true);
              try {
                const result = await api.inviteEventMember(
                  {
                    ecoe_event_id: eventId,
                    name: form.name,
                    last_name: form.last_name,
                    email: form.email,
                    role_code: form.role_code,
                    station_ids: form.station_id ? [Number(form.station_id)] : [],
                  },
                );
                await refresh();
                setActivationLink(
                  result.activation_path
                    ? `${window.location.origin}${result.activation_path}`
                    : null,
                );
                setForm({
                  name: "",
                  last_name: "",
                  email: "",
                  role_code: "evaluador",
                  station_id: "",
                });
                setMessage(
                  result.status === "assigned"
                    ? "La cuenta existente fue asignada correctamente al ECOE."
                    : "Invitación creada. Comparte el enlace temporal por un canal institucional.",
                );
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
                onBlur={async () => {
                  if (!form.email) return;
                  setLookupMessage(null);
                  try {
                    const result = await api.lookupEventMember(eventId, form.email);
                    if (result.assigned_to_event) {
                      setLookupMessage("Esta persona ya pertenece al equipo del ECOE.");
                    } else if (result.account_status === "suspended") {
                      setLookupMessage("La cuenta está suspendida y requiere revisión del administrador global.");
                    } else if (result.exists) {
                      setLookupMessage("Cuenta institucional encontrada; se asignará sin crear otra cuenta.");
                    } else {
                      setLookupMessage("No existe una cuenta; se generará una invitación de activación.");
                    }
                  } catch {
                    setLookupMessage("No se pudo comprobar el correo.");
                  }
                }}
              />
              {lookupMessage ? <p className="text-xs leading-5 text-slate-500">{lookupMessage}</p> : null}
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
              <button className="btn-primary" disabled={savingForm || !canInviteMembers}>
                {savingForm ? "Guardando..." : "Guardar asignación"}
              </button>
              {!canInviteMembers ? (
                <p className="text-sm text-slate-600">Solo el administrador del ECOE puede asignar o invitar nuevas personas.</p>
              ) : null}
              <StatusNotice message={message} />
              {activationLink ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
                  <p className="text-sm font-semibold text-amber-900">Enlace de activación — visible solo ahora</p>
                  <div className="mt-2 flex flex-col gap-2 sm:flex-row">
                    <input readOnly value={activationLink} className="min-w-0 flex-1" />
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={async () => {
                        await navigator.clipboard.writeText(activationLink);
                        setMessage("Enlace de activación copiado.");
                      }}
                    >
                      Copiar enlace
                    </button>
                  </div>
                </div>
              ) : null}
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
                const response = (await api.deduplicateStaffByEmail(eventId)) as {
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
            searchKeys={["name", "last_name", "email", "role_code"]}
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
                          await api.deleteStaff(Number(staff.id));
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
