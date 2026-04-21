"use client";

import { useMemo, useState } from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";
import type { ECOEEvent } from "@/lib/types";

const STATUS_OPTIONS = [
  "borrador",
  "en_configuracion",
  "listo_para_pilotaje",
  "en_pilotaje",
  "pilotaje_validado",
  "publicado",
  "en_ejecucion",
  "cerrado",
  "archivado",
] as const;

const DEFAULT_CREATE_VALUES = {
  name: "",
  date: "",
  course_name: "",
  school_name: "",
  responsible_teacher: "",
  contact_email: "",
  circuit_mode: "paralelo_espejo",
  total_stations: "8",
  station_time_minutes: "8",
  transition_time_minutes: "2",
  total_students: "0",
  total_groups: "1",
  passing_reference_percent: "60",
};

function Field({
  label,
  children,
  description,
}: {
  label: string;
  children: React.ReactNode;
  description?: string;
}) {
  return (
    <label className="space-y-2 rounded-[22px] border border-slate-200 bg-white/80 p-4">
      <span className="text-sm font-semibold text-slate-700">{label}</span>
      {description ? <p className="text-xs leading-5 text-slate-500">{description}</p> : null}
      {children}
    </label>
  );
}

function toEditableValues(ecoeEvent: ECOEEvent | null) {
  if (!ecoeEvent) {
    return null;
  }
  return {
    name: ecoeEvent.name ?? "",
    date: ecoeEvent.date ?? "",
    course_name: ecoeEvent.course_name ?? "",
    school_name: ecoeEvent.school_name ?? "",
    responsible_teacher: ecoeEvent.responsible_teacher ?? "",
    contact_email: ecoeEvent.contact_email ?? "",
    circuit_mode: ecoeEvent.circuit_mode ?? "",
    total_stations: String(ecoeEvent.total_stations ?? 0),
    station_time_minutes: String(ecoeEvent.station_time_minutes ?? 0),
    transition_time_minutes: String(ecoeEvent.transition_time_minutes ?? 0),
    total_students: String(ecoeEvent.total_students ?? 0),
    total_groups: String(ecoeEvent.total_groups ?? 1),
    passing_reference_percent: String(ecoeEvent.passing_reference_percent ?? 60),
    status: ecoeEvent.status ?? "borrador",
  };
}

function buildPayload(values: Record<string, string>) {
  return {
    name: values.name,
    date: values.date,
    course_name: values.course_name,
    school_name: values.school_name,
    responsible_teacher: values.responsible_teacher,
    contact_email: values.contact_email,
    circuit_mode: values.circuit_mode,
    total_stations: Number(values.total_stations),
    station_time_minutes: Number(values.station_time_minutes),
    transition_time_minutes: Number(values.transition_time_minutes),
    total_students: Number(values.total_students),
    total_groups: Number(values.total_groups),
    passing_reference_percent: Number(values.passing_reference_percent),
  };
}

export default function ECOEPage() {
  const { token, eventId, setEventId, user } = useAuth();
  const { data: ecoeList, loading: listLoading, error: listError, setData: setECOEList } = useApi(
    () => api.listECOE(token!) as Promise<ECOEEvent[]>,
    [token],
  );
  const { data: ecoeEvent, loading, error, setData } = useApi(
    () => api.ecoe(eventId, token!) as Promise<ECOEEvent>,
    [eventId, token],
  );
  const [formValues, setFormValues] = useState<Record<string, string> | null>(null);
  const [createValues, setCreateValues] = useState<Record<string, string>>(DEFAULT_CREATE_VALUES);
  const [message, setMessage] = useState<string | null>(null);
  const [createMessage, setCreateMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [duplicating, setDuplicating] = useState(false);

  const editableValues = useMemo(() => toEditableValues(ecoeEvent ?? null), [ecoeEvent]);
  const activeValues = formValues ?? editableValues;

  const refreshList = async (targetEventId?: number) => {
    const refreshed = (await api.listECOE(token!)) as ECOEEvent[];
    setECOEList(refreshed);
    if (targetEventId && !refreshed.some((item) => item.id === targetEventId)) {
      setEventId(refreshed[0]?.id ?? eventId);
    }
  };

  const updateField = (name: string, value: string) => {
    setFormValues((current) => ({ ...(current ?? editableValues ?? {}), [name]: value }));
  };

  const resetForm = () => {
    setFormValues(editableValues);
    setMessage(null);
  };

  return (
    <div className="space-y-6">
      <SectionCard
        title="Gestion del ECOE"
        subtitle="Aqui puedes editar los datos generales del evento activo, cambiar su estado operativo, duplicarlo o crear uno nuevo para la siguiente iteracion."
      >
        <div className="grid gap-4 md:grid-cols-3">
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Evento activo</p>
            <p className="mt-3 text-2xl font-semibold">{ecoeEvent?.name ?? "Sin cargar"}</p>
            <p className="mt-2 text-sm text-slate-600">{ecoeEvent?.course_name ?? "Curso sin definir"}</p>
          </div>
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Estado actual</p>
            <p className="mt-3 text-2xl font-semibold">{ecoeEvent?.status ?? "sin_estado"}</p>
            <p className="mt-2 text-sm text-slate-600">{ecoeEvent?.date ?? "Fecha no definida"}</p>
          </div>
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Seleccion de ECOE</p>
            <select
              className="mt-3"
              value={String(eventId)}
              onChange={(event) => {
                setEventId(Number(event.target.value));
                setFormValues(null);
                setMessage(null);
              }}
            >
              {(ecoeList ?? []).map((item) => (
                <option key={item.id} value={String(item.id)}>
                  {item.name} · {item.course_name}
                </option>
              ))}
            </select>
            <p className="mt-2 text-sm text-slate-600">
              Cambia rapido entre eventos sin salir del modulo de administracion.
            </p>
          </div>
        </div>
      </SectionCard>

      <SectionCard
        title="Datos generales y estado"
        subtitle="Este formulario concentra la configuracion academica base del ECOE. Guarda aqui antes de seguir con estaciones, validacion o publicacion."
      >
        {loading || listLoading ? <p>Cargando configuracion del ECOE...</p> : null}
        {error || listError ? <p>{error ?? listError}</p> : null}
        {activeValues ? (
          <form
            className="space-y-4"
            onSubmit={async (event) => {
              event.preventDefault();
              if (!ecoeEvent) {
                return;
              }
              setSaving(true);
              setMessage(null);
              try {
                const updated = (await api.updateECOE(
                  ecoeEvent.id,
                  {
                    ...buildPayload(activeValues),
                    status: activeValues.status,
                  },
                  token!,
                )) as ECOEEvent;
                setData(updated);
                setFormValues(toEditableValues(updated));
                await refreshList(updated.id);
                setMessage("Configuracion del ECOE guardada correctamente.");
              } catch (saveError) {
                setMessage(saveError instanceof Error ? saveError.message : "No se pudo guardar el ECOE.");
              } finally {
                setSaving(false);
              }
            }}
          >
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Nombre del ECOE">
                <input value={activeValues.name} onChange={(event) => updateField("name", event.target.value)} />
              </Field>
              <Field label="Fecha oficial">
                <input
                  type="date"
                  value={activeValues.date}
                  onChange={(event) => updateField("date", event.target.value)}
                />
              </Field>
              <Field label="Curso">
                <input
                  value={activeValues.course_name}
                  onChange={(event) => updateField("course_name", event.target.value)}
                />
              </Field>
              <Field label="Escuela o unidad academica">
                <input
                  value={activeValues.school_name}
                  onChange={(event) => updateField("school_name", event.target.value)}
                />
              </Field>
              <Field label="Docente responsable">
                <input
                  value={activeValues.responsible_teacher}
                  onChange={(event) => updateField("responsible_teacher", event.target.value)}
                />
              </Field>
              <Field label="Correo de contacto">
                <input
                  type="email"
                  value={activeValues.contact_email}
                  onChange={(event) => updateField("contact_email", event.target.value)}
                />
              </Field>
              <Field label="Modo de circuito">
                <input
                  value={activeValues.circuit_mode}
                  onChange={(event) => updateField("circuit_mode", event.target.value)}
                />
              </Field>
              <Field
                label="Estado del ECOE"
                description="Puedes ajustar el estado aqui; si el backend detecta una transicion invalida, te devolvera el error correspondiente."
              >
                <select
                  value={activeValues.status}
                  onChange={(event) => updateField("status", event.target.value)}
                >
                  {STATUS_OPTIONS.map((status) => (
                    <option key={status} value={status}>
                      {status}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Total de estaciones">
                <input
                  type="number"
                  min="1"
                  value={activeValues.total_stations}
                  onChange={(event) => updateField("total_stations", event.target.value)}
                />
              </Field>
              <Field label="Minutos por estacion">
                <input
                  type="number"
                  min="0.1"
                  step="0.1"
                  value={activeValues.station_time_minutes}
                  onChange={(event) => updateField("station_time_minutes", event.target.value)}
                />
              </Field>
              <Field label="Minutos de transicion">
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={activeValues.transition_time_minutes}
                  onChange={(event) => updateField("transition_time_minutes", event.target.value)}
                />
              </Field>
              <Field label="Total de estudiantes">
                <input
                  type="number"
                  min="0"
                  value={activeValues.total_students}
                  onChange={(event) => updateField("total_students", event.target.value)}
                />
              </Field>
              <Field label="Total de grupos">
                <input
                  type="number"
                  min="1"
                  value={activeValues.total_groups}
                  onChange={(event) => updateField("total_groups", event.target.value)}
                />
              </Field>
              <Field label="Porcentaje de aprobacion">
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={activeValues.passing_reference_percent}
                  onChange={(event) => updateField("passing_reference_percent", event.target.value)}
                />
              </Field>
            </div>
            <div className="flex flex-wrap gap-3">
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? "Guardando..." : "Guardar ECOE"}
              </button>
              <button type="button" className="btn-secondary" onClick={resetForm} disabled={saving}>
                Revertir cambios locales
              </button>
              <button
                type="button"
                className="btn-secondary"
                disabled={!ecoeEvent || duplicating || user?.role !== "creador_ecoe"}
                onClick={async () => {
                  if (!ecoeEvent) {
                    return;
                  }
                  const confirmed = window.confirm(
                    "Se creara una copia del ECOE activo con los mismos datos generales. ¿Quieres continuar?",
                  );
                  if (!confirmed) {
                    return;
                  }
                  setDuplicating(true);
                  setMessage(null);
                  try {
                    const duplicated = (await api.duplicateECOE(ecoeEvent.id, token!)) as ECOEEvent;
                    await refreshList(duplicated.id);
                    setEventId(duplicated.id);
                    setData(duplicated);
                    setFormValues(toEditableValues(duplicated));
                    setMessage("Copia creada. Ya quedo seleccionada como ECOE activo para seguir editando.");
                  } catch (duplicateError) {
                    setMessage(
                      duplicateError instanceof Error
                        ? duplicateError.message
                        : "No se pudo duplicar el ECOE.",
                    );
                  } finally {
                    setDuplicating(false);
                  }
                }}
              >
                {duplicating ? "Duplicando..." : "Duplicar ECOE"}
              </button>
            </div>
            {user?.role !== "creador_ecoe" ? (
              <p className="text-sm text-slate-500">
                Solo el rol creador ECOE puede duplicar eventos completos.
              </p>
            ) : null}
            {message ? <p className="text-sm text-slate-600">{message}</p> : null}
          </form>
        ) : null}
      </SectionCard>

      <SectionCard
        title="Crear nuevo ECOE"
        subtitle="Usa este bloque para abrir un nuevo evento desde cero sin salir del trabajo actual. Al crearlo, quedara en estado borrador y pasara a ser el ECOE seleccionado."
      >
        <form
          className="space-y-4"
          onSubmit={async (event) => {
            event.preventDefault();
            setCreating(true);
            setCreateMessage(null);
            try {
              const created = (await api.createECOE(buildPayload(createValues), token!)) as ECOEEvent;
              await refreshList(created.id);
              setEventId(created.id);
              setData(created);
              setFormValues(toEditableValues(created));
              setCreateValues(DEFAULT_CREATE_VALUES);
              setCreateMessage("Nuevo ECOE creado y seleccionado para continuar su configuracion.");
            } catch (createError) {
              setCreateMessage(
                createError instanceof Error ? createError.message : "No se pudo crear el ECOE.",
              );
            } finally {
              setCreating(false);
            }
          }}
        >
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Nombre del nuevo ECOE">
              <input
                value={createValues.name}
                onChange={(event) =>
                  setCreateValues((current) => ({ ...current, name: event.target.value }))
                }
              />
            </Field>
            <Field label="Fecha oficial">
              <input
                type="date"
                value={createValues.date}
                onChange={(event) =>
                  setCreateValues((current) => ({ ...current, date: event.target.value }))
                }
              />
            </Field>
            <Field label="Curso">
              <input
                value={createValues.course_name}
                onChange={(event) =>
                  setCreateValues((current) => ({ ...current, course_name: event.target.value }))
                }
              />
            </Field>
            <Field label="Escuela o unidad academica">
              <input
                value={createValues.school_name}
                onChange={(event) =>
                  setCreateValues((current) => ({ ...current, school_name: event.target.value }))
                }
              />
            </Field>
            <Field label="Docente responsable">
              <input
                value={createValues.responsible_teacher}
                onChange={(event) =>
                  setCreateValues((current) => ({ ...current, responsible_teacher: event.target.value }))
                }
              />
            </Field>
            <Field label="Correo de contacto">
              <input
                type="email"
                value={createValues.contact_email}
                onChange={(event) =>
                  setCreateValues((current) => ({ ...current, contact_email: event.target.value }))
                }
              />
            </Field>
            <Field label="Modo de circuito">
              <input
                value={createValues.circuit_mode}
                onChange={(event) =>
                  setCreateValues((current) => ({ ...current, circuit_mode: event.target.value }))
                }
              />
            </Field>
            <Field label="Total de estaciones">
              <input
                type="number"
                min="1"
                value={createValues.total_stations}
                onChange={(event) =>
                  setCreateValues((current) => ({ ...current, total_stations: event.target.value }))
                }
              />
            </Field>
            <Field label="Minutos por estacion">
              <input
                type="number"
                min="0.1"
                step="0.1"
                value={createValues.station_time_minutes}
                onChange={(event) =>
                  setCreateValues((current) => ({ ...current, station_time_minutes: event.target.value }))
                }
              />
            </Field>
            <Field label="Minutos de transicion">
              <input
                type="number"
                min="0"
                step="0.1"
                value={createValues.transition_time_minutes}
                onChange={(event) =>
                  setCreateValues((current) => ({ ...current, transition_time_minutes: event.target.value }))
                }
              />
            </Field>
            <Field label="Total de estudiantes">
              <input
                type="number"
                min="0"
                value={createValues.total_students}
                onChange={(event) =>
                  setCreateValues((current) => ({ ...current, total_students: event.target.value }))
                }
              />
            </Field>
            <Field label="Total de grupos">
              <input
                type="number"
                min="1"
                value={createValues.total_groups}
                onChange={(event) =>
                  setCreateValues((current) => ({ ...current, total_groups: event.target.value }))
                }
              />
            </Field>
            <Field label="Porcentaje de aprobacion">
              <input
                type="number"
                min="0"
                max="100"
                step="0.1"
                value={createValues.passing_reference_percent}
                onChange={(event) =>
                  setCreateValues((current) => ({
                    ...current,
                    passing_reference_percent: event.target.value,
                  }))
                }
              />
            </Field>
          </div>
          <div className="flex flex-wrap gap-3">
            <button type="submit" className="btn-primary" disabled={creating}>
              {creating ? "Creando..." : "Crear nuevo ECOE"}
            </button>
          </div>
          {createMessage ? <p className="text-sm text-slate-600">{createMessage}</p> : null}
        </form>
      </SectionCard>
    </div>
  );
}
