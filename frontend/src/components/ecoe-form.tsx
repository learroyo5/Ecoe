"use client";

import { useState } from "react";

const CIRCUIT_MODES = [
  { value: "paralelo_espejo", label: "Paralelo en espejo", description: "Múltiples circuitos idénticos ejecutándose simultáneamente con las mismas estaciones." },
  { value: "secuencial", label: "Secuencial", description: "Los estudiantes rotan por todas las estaciones en orden fijo, un solo circuito." },
  { value: "estaciones_independientes", label: "Estaciones independientes", description: "Cada estación opera de forma autónoma sin rotación rígida entre estaciones." },
  { value: "mixto", label: "Mixto", description: "Combinación de modalidades según necesidad pedagógica de cada estación." },
] as const;

const STATUS_OPTIONS = [
  "borrador", "en_configuracion", "listo_para_pilotaje", "en_pilotaje",
  "pilotaje_validado", "publicado", "en_ejecucion", "cerrado", "archivado",
] as const;

/** Shared field wrapper — consistent layout across all ECOE forms */
export function FormField({
  label,
  children,
  description,
  required = false,
  error,
}: {
  label: string;
  children: React.ReactNode;
  description?: string;
  required?: boolean;
  error?: string;
}) {
  return (
    <label className="space-y-2 rounded-[22px] border border-slate-200 bg-white/80 p-4">
      <span className="text-sm font-semibold text-slate-700">
        {label}
        {required ? <span className="ml-1 text-red-500" title="Campo obligatorio">*</span> : null}
      </span>
      {description ? <p className="text-xs leading-5 text-slate-500">{description}</p> : null}
      {children}
      {error ? <p className="text-xs text-red-600">{error}</p> : null}
    </label>
  );
}

/** Section header inside form */
function FormSection({ title, description }: { title: string; description?: string }) {
  return (
    <div className="col-span-full mt-2 first:mt-0">
      <h3 className="text-base font-semibold text-slate-800">{title}</h3>
      {description ? <p className="mt-0.5 text-xs text-slate-500">{description}</p> : null}
    </div>
  );
}

const REQUIRED_FIELDS = ["name", "date", "course_name", "school_name", "responsible_teacher", "contact_email", "circuit_mode"] as const;

/** Validate form values before submission. Returns error map (field → message) or empty object. */
export function validateECOEPayload(values: Record<string, string>): Record<string, string> {
  const errors: Record<string, string> = {};

  for (const field of REQUIRED_FIELDS) {
    if (!(values[field] ?? "").trim()) {
      errors[field] = "Este campo es obligatorio";
    }
  }

  const email = (values.contact_email ?? "").trim();
  if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    errors.contact_email = "Ingresa un correo electrónico válido";
  }

  const stations = Number(values.total_stations);
  if (Number.isNaN(stations) || stations < 1) {
    errors.total_stations = "Debe ser al menos 1";
  }

  const stationTime = Number(values.station_time_minutes);
  if (Number.isNaN(stationTime) || stationTime < 0.1) {
    errors.station_time_minutes = "Debe ser al menos 0.1 minutos";
  }

  const groups = Number(values.total_groups);
  if (Number.isNaN(groups) || groups < 1) {
    errors.total_groups = "Debe ser al menos 1";
  }

  const passing = Number(values.passing_reference_percent);
  if (Number.isNaN(passing) || passing < 0 || passing > 100) {
    errors.passing_reference_percent = "Debe estar entre 0 y 100";
  }

  return errors;
}

/** All ECOE form fields — shared between edit and create */
export function ECOEFormFields({
  values,
  onChange,
  includeStatus = false,
  errors = {},
}: {
  values: Record<string, string>;
  onChange: (name: string, value: string) => void;
  includeStatus?: boolean;
  errors?: Record<string, string>;
}) {
  const update = (name: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    onChange(name, e.target.value);

  return (
    <div className="grid gap-4 md:grid-cols-2">

      {/* ── Datos generales ── */}
      <FormSection title="Datos generales" description="Identificación del evento y responsable académico." />

      <FormField label="Nombre del ECOE" required error={errors.name}>
        <input
          value={values.name ?? ""} onChange={update("name")}
          placeholder="Ej: ECOE Medicina Interna 2026"
        />
      </FormField>

      <FormField label="Fecha oficial" required error={errors.date}>
        <input type="date" value={values.date ?? ""} onChange={update("date")} />
      </FormField>

      <FormField label="Curso" required error={errors.course_name}>
        <input value={values.course_name ?? ""} onChange={update("course_name")}
          placeholder="Ej: Medicina Interna" />
      </FormField>

      <FormField label="Escuela o unidad académica" required error={errors.school_name}>
        <input value={values.school_name ?? ""} onChange={update("school_name")}
          placeholder="Ej: Escuela de Medicina" />
      </FormField>

      <FormField label="Docente responsable" required error={errors.responsible_teacher}>
        <input value={values.responsible_teacher ?? ""} onChange={update("responsible_teacher")}
          placeholder="Nombre completo" />
      </FormField>

      <FormField label="Correo de contacto" required error={errors.contact_email}>
        <input type="email" value={values.contact_email ?? ""} onChange={update("contact_email")}
          placeholder="ecoe@universidad.cl" />
      </FormField>

      {/* ── Configuración del circuito ── */}
      <FormSection
        title="Configuración del circuito"
        description="Define cómo se organizan las estaciones y los estudiantes."
      />

      <FormField label="Modo de circuito" required error={errors.circuit_mode}
        description="Define cómo rotan los estudiantes entre estaciones.">
        <select value={values.circuit_mode ?? "paralelo_espejo"} onChange={update("circuit_mode")}>
          {CIRCUIT_MODES.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
        {/* Show description of selected mode */}
        {(() => {
          const selected = CIRCUIT_MODES.find((m) => m.value === values.circuit_mode);
          return selected ? (
            <p className="text-xs leading-5 text-slate-500 mt-1">{selected.description}</p>
          ) : null;
        })()}
      </FormField>

      <FormField label="Total de estaciones" description="Número total de estaciones del ECOE (mín. 1)." error={errors.total_stations}>
        <input type="number" min="1" value={values.total_stations ?? ""} onChange={update("total_stations")} />
      </FormField>

      <FormField label="Total de grupos" description="Cantidad de grupos de estudiantes que rotarán en paralelo." error={errors.total_groups}>
        <input type="number" min="1" value={values.total_groups ?? ""} onChange={update("total_groups")} />
      </FormField>

      <FormField label="Total de estudiantes" description="Cantidad total estimada de estudiantes (0 = aún sin definir).">
        <input type="number" min="0" value={values.total_students ?? ""} onChange={update("total_students")} />
      </FormField>

      {/* ── Parámetros de tiempo y evaluación ── */}
      <FormSection
        title="Parámetros de tiempo y evaluación"
        description="Configuración de la duración de cada estación y criterios de aprobación."
      />

      <FormField label="Minutos por estación" description="Tiempo que cada estudiante permanece en una estación." error={errors.station_time_minutes}>
        <input type="number" min="0.1" step="0.1" value={values.station_time_minutes ?? ""} onChange={update("station_time_minutes")} />
      </FormField>

      <FormField label="Minutos de transición" description="Tiempo entre estaciones para cambio y lectura de instrucciones.">
        <input type="number" min="0" step="0.1" value={values.transition_time_minutes ?? ""} onChange={update("transition_time_minutes")} />
      </FormField>

      <FormField label="Porcentaje de aprobación" description="Nota mínima en porcentaje para considerar aprobado." error={errors.passing_reference_percent}>
        <input type="number" min="0" max="100" step="0.1" value={values.passing_reference_percent ?? ""} onChange={update("passing_reference_percent")} />
      </FormField>

      {/* ── Estado (solo edición) ── */}
      {includeStatus ? (
        <FormField
          label="Estado del ECOE"
          description="Puedes ajustar el estado aquí; si el backend detecta una transición inválida, te devolverá el error correspondiente."
        >
          <select value={values.status ?? "borrador"} onChange={update("status")}>
            {STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>
                {status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
              </option>
            ))}
          </select>
        </FormField>
      ) : null}
    </div>
  );
}

/** Build API payload from form values */
export function buildECOEPayload(values: Record<string, string>) {
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

/** Convert ECOEEvent to editable string values */
export function toEditableValues(ecoeEvent: Record<string, unknown> | null): Record<string, string> | null {
  if (!ecoeEvent) return null;
  return {
    name: String(ecoeEvent.name ?? ""),
    date: String(ecoeEvent.date ?? ""),
    course_name: String(ecoeEvent.course_name ?? ""),
    school_name: String(ecoeEvent.school_name ?? ""),
    responsible_teacher: String(ecoeEvent.responsible_teacher ?? ""),
    contact_email: String(ecoeEvent.contact_email ?? ""),
    circuit_mode: String(ecoeEvent.circuit_mode ?? ""),
    total_stations: String(ecoeEvent.total_stations ?? 0),
    station_time_minutes: String(ecoeEvent.station_time_minutes ?? 0),
    transition_time_minutes: String(ecoeEvent.transition_time_minutes ?? 0),
    total_students: String(ecoeEvent.total_students ?? 0),
    total_groups: String(ecoeEvent.total_groups ?? 1),
    passing_reference_percent: String(ecoeEvent.passing_reference_percent ?? 60),
    status: String(ecoeEvent.status ?? "borrador"),
  };
}

export { STATUS_OPTIONS, CIRCUIT_MODES };

// ── Status transition UI ─────────────────────────────────────────────

interface TransitionAction {
  target: string;
  label: string;
  confirmTitle: string;
  confirmMessage: string;
  severity: "info" | "warning" | "danger";
}

const STATUS_TRANSITIONS: Record<string, TransitionAction[]> = {
  borrador: [
    { target: "en_configuracion", label: "Iniciar configuración", confirmTitle: "¿Iniciar configuración?", confirmMessage: "El ECOE pasará a estado de configuración. Podrás construir estaciones y cargar participantes.", severity: "info" },
  ],
  en_configuracion: [
    { target: "borrador", label: "Volver a borrador", confirmTitle: "¿Volver a borrador?", confirmMessage: "El ECOE regresará a estado borrador.", severity: "warning" },
    { target: "listo_para_pilotaje", label: "Listo para pilotaje", confirmTitle: "¿Marcar como listo para pilotaje?", confirmMessage: "Solo si todas las estaciones tienen su configuración base completa.", severity: "info" },
  ],
  listo_para_pilotaje: [
    { target: "en_configuracion", label: "Volver a configuración", confirmTitle: "¿Volver a configuración?", confirmMessage: "El ECOE regresará a configuración para hacer ajustes.", severity: "warning" },
    { target: "en_pilotaje", label: "Iniciar pilotaje", confirmTitle: "¿Iniciar pilotaje?", confirmMessage: "Se habilitará el modo de pruebas. Los datos generados se marcarán como pilotaje.", severity: "info" },
  ],
  en_pilotaje: [
    { target: "listo_para_pilotaje", label: "Pausar pilotaje", confirmTitle: "¿Pausar pilotaje?", confirmMessage: "El ECOE volverá a listo para pilotaje.", severity: "warning" },
    { target: "pilotaje_validado", label: "Validar pilotaje", confirmTitle: "¿Validar pilotaje?", confirmMessage: "Confirmas que el pilotaje fue exitoso y el ECOE está listo para publicarse.", severity: "info" },
  ],
  pilotaje_validado: [
    { target: "en_pilotaje", label: "Reabrir pilotaje", confirmTitle: "¿Reabrir pilotaje?", confirmMessage: "El ECOE volverá a modo pilotaje para ajustes adicionales.", severity: "warning" },
    { target: "publicado", label: "Publicar ECOE", confirmTitle: "¿Publicar ECOE?", confirmMessage: "El ECOE quedará visible para evaluadores y estudiantes. Se creará la sesión en vivo.", severity: "danger" },
  ],
  publicado: [
    { target: "pilotaje_validado", label: "Despublicar", confirmTitle: "¿Despublicar ECOE?", confirmMessage: "El ECOE dejará de estar visible para evaluadores y estudiantes.", severity: "danger" },
    { target: "en_ejecucion", label: "Iniciar ejecución", confirmTitle: "¿Iniciar ejecución en vivo?", confirmMessage: "Se activará el cronómetro y los evaluadores podrán comenzar a evaluar.", severity: "danger" },
  ],
  en_ejecucion: [
    { target: "cerrado", label: "Cerrar ECOE", confirmTitle: "¿Cerrar ECOE?", confirmMessage: "Se detendrá la ejecución y ya no se aceptarán más evaluaciones.", severity: "danger" },
  ],
  cerrado: [
    { target: "archivado", label: "Archivar", confirmTitle: "¿Archivar ECOE?", confirmMessage: "El ECOE se archivará. Seguirá accesible en modo lectura.", severity: "info" },
  ],
  archivado: [
    { target: "borrador", label: "Reactivar", confirmTitle: "¿Reactivar ECOE?", confirmMessage: "El ECOE volverá a borrador para una nueva edición.", severity: "warning" },
  ],
};

const STATUS_LABELS: Record<string, string> = {
  borrador: "Borrador",
  en_configuracion: "En configuración",
  listo_para_pilotaje: "Listo para pilotaje",
  en_pilotaje: "En pilotaje",
  pilotaje_validado: "Pilotaje validado",
  publicado: "Publicado",
  en_ejecucion: "En ejecución",
  cerrado: "Cerrado",
  archivado: "Archivado",
};

const STATUS_COLORS: Record<string, string> = {
  borrador: "bg-slate-100 text-slate-700",
  en_configuracion: "bg-blue-100 text-blue-700",
  listo_para_pilotaje: "bg-amber-100 text-amber-700",
  en_pilotaje: "bg-orange-100 text-orange-700",
  pilotaje_validado: "bg-emerald-100 text-emerald-700",
  publicado: "bg-violet-100 text-violet-700",
  en_ejecucion: "bg-red-100 text-red-700",
  cerrado: "bg-gray-200 text-gray-600",
  archivado: "bg-gray-100 text-gray-500",
};

interface StatusTransitionBarProps {
  currentStatus: string;
  onTransition: (targetStatus: string) => void;
  disabled?: boolean;
  loading?: boolean;
}

export function StatusTransitionBar({ currentStatus, onTransition, disabled = false, loading = false }: StatusTransitionBarProps) {
  const [confirming, setConfirming] = useState<TransitionAction | null>(null);

  const transitions = STATUS_TRANSITIONS[currentStatus] ?? [];
  const label = STATUS_LABELS[currentStatus] ?? currentStatus;
  const color = STATUS_COLORS[currentStatus] ?? "bg-slate-100 text-slate-700";

  return (
    <>
      <div className="rounded-[22px] border border-slate-200 bg-white/80 p-5 space-y-3">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-sm font-semibold text-slate-700">Estado actual:</span>
          <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ${color}`}>
            {label}
          </span>
          {currentStatus === "en_ejecucion" ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-700 animate-pulse">
              <span className="size-1.5 rounded-full bg-red-500" />
              EN VIVO
            </span>
          ) : null}
        </div>

        {transitions.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {transitions.map((t) => (
              <button
                key={t.target}
                type="button"
                disabled={disabled || loading}
                onClick={() => setConfirming(t)}
                className={`inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-sm font-semibold transition ${
                  t.severity === "danger"
                    ? "bg-red-50 text-red-700 hover:bg-red-100 border border-red-200"
                    : t.severity === "warning"
                      ? "bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200"
                      : "bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200"
                } disabled:opacity-50`}
              >
                {t.label}
              </button>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">No hay transiciones disponibles desde este estado.</p>
        )}
      </div>

      {/* Confirmation modal */}
      {confirming ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={() => setConfirming(null)}>
          <div className="mx-4 w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl animate-fade-in" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-xl font-semibold text-slate-900">{confirming.confirmTitle}</h3>
            <p className="mt-2 text-sm text-slate-600">{confirming.confirmMessage}</p>
            <div className="mt-6 flex gap-3 justify-end">
              <button className="btn-secondary" onClick={() => setConfirming(null)}>Cancelar</button>
              <button
                className={`btn-primary ${
                  confirming.severity === "danger"
                    ? "!bg-red-600 hover:!bg-red-700"
                    : confirming.severity === "warning"
                      ? "!bg-amber-600 hover:!bg-amber-700"
                      : ""
                }`}
                disabled={loading}
                onClick={() => {
                  onTransition(confirming.target);
                  setConfirming(null);
                }}
              >
                {loading ? "Procesando..." : confirming.label}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

export { STATUS_TRANSITIONS, STATUS_LABELS, STATUS_COLORS };

