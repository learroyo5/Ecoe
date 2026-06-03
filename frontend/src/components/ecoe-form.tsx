"use client";

const STATUS_OPTIONS = [
  "borrador", "en_configuracion", "listo_para_pilotaje", "en_pilotaje",
  "pilotaje_validado", "publicado", "en_ejecucion", "cerrado", "archivado",
] as const;

/** Shared field wrapper — consistent layout across all ECOE forms */
export function FormField({
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

/** All ECOE form fields — shared between edit and create */
export function ECOEFormFields({
  values,
  onChange,
  includeStatus = false,
}: {
  values: Record<string, string>;
  onChange: (name: string, value: string) => void;
  includeStatus?: boolean;
}) {
  const update = (name: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    onChange(name, e.target.value);

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <FormField label="Nombre del ECOE">
        <input value={values.name ?? ""} onChange={update("name")} />
      </FormField>
      <FormField label="Fecha oficial">
        <input type="date" value={values.date ?? ""} onChange={update("date")} />
      </FormField>
      <FormField label="Curso">
        <input value={values.course_name ?? ""} onChange={update("course_name")} />
      </FormField>
      <FormField label="Escuela o unidad académica">
        <input value={values.school_name ?? ""} onChange={update("school_name")} />
      </FormField>
      <FormField label="Docente responsable">
        <input value={values.responsible_teacher ?? ""} onChange={update("responsible_teacher")} />
      </FormField>
      <FormField label="Correo de contacto">
        <input type="email" value={values.contact_email ?? ""} onChange={update("contact_email")} />
      </FormField>
      <FormField label="Modo de circuito">
        <input value={values.circuit_mode ?? ""} onChange={update("circuit_mode")} />
      </FormField>
      {includeStatus ? (
        <FormField
          label="Estado del ECOE"
          description="Puedes ajustar el estado aquí; si el backend detecta una transición inválida, te devolverá el error correspondiente."
        >
          <select value={values.status ?? "borrador"} onChange={update("status")}>
            {STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>
        </FormField>
      ) : null}
      <FormField label="Total de estaciones">
        <input type="number" min="1" value={values.total_stations ?? ""} onChange={update("total_stations")} />
      </FormField>
      <FormField label="Minutos por estación">
        <input type="number" min="0.1" step="0.1" value={values.station_time_minutes ?? ""} onChange={update("station_time_minutes")} />
      </FormField>
      <FormField label="Minutos de transición">
        <input type="number" min="0" step="0.1" value={values.transition_time_minutes ?? ""} onChange={update("transition_time_minutes")} />
      </FormField>
      <FormField label="Total de estudiantes">
        <input type="number" min="0" value={values.total_students ?? ""} onChange={update("total_students")} />
      </FormField>
      <FormField label="Total de grupos">
        <input type="number" min="1" value={values.total_groups ?? ""} onChange={update("total_groups")} />
      </FormField>
      <FormField label="Porcentaje de aprobación">
        <input type="number" min="0" max="100" step="0.1" value={values.passing_reference_percent ?? ""} onChange={update("passing_reference_percent")} />
      </FormField>
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

export { STATUS_OPTIONS };
