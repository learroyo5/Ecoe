/** Etiquetas legibles para los valores internos de estado y modo. */

const ECOE_STATUS_LABELS: Record<string, string> = {
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

const SESSION_STATUS_LABELS: Record<string, string> = {
  ready: "Lista para iniciar",
  running: "En curso",
  paused: "En pausa",
  transition: "En transición",
  finished: "Finalizada",
  sin_sesion: "Sin sesión",
};

const STATION_STATUS_LABELS: Record<string, string> = {
  no_iniciada: "No iniciada",
  en_diseno: "En diseño",
  incompleta: "Incompleta",
  lista_para_pilotaje: "Lista para pilotaje",
  en_pilotaje: "En pilotaje",
  validada: "Validada",
  publicada: "Publicada",
  activa: "Activa",
  finalizada: "Finalizada",
  con_incidencia: "Con incidencia",
  cerrada: "Cerrada",
};

const ROLE_LABELS: Record<string, string> = {
  admin_global: "Administración global",
  admin_ecoe: "Administración ECOE",
  coeditor_docente: "Coeditor docente",
  coordinador_operativo: "Coordinación operativa",
  evaluador: "Evaluador",
  estudiante: "Estudiante",
  cronometrador: "Cronometrador",
};

const MODE_LABELS: Record<string, string> = {
  pilotaje: "pilotaje",
  ejecucion: "ejecución",
};

function humanize(value: string): string {
  const clean = value.replace(/_/g, " ").trim();
  return clean.charAt(0).toUpperCase() + clean.slice(1);
}

export function ecoeStatusLabel(status: unknown): string {
  const key = String(status ?? "");
  return ECOE_STATUS_LABELS[key] ?? humanize(key);
}

export function sessionStatusLabel(status: unknown): string {
  const key = String(status ?? "");
  return SESSION_STATUS_LABELS[key] ?? humanize(key);
}

export function stationStatusLabel(status: unknown): string {
  const key = String(status ?? "");
  return STATION_STATUS_LABELS[key] ?? humanize(key);
}

export function roleLabel(role: unknown): string {
  const key = String(role ?? "");
  return ROLE_LABELS[key] ?? humanize(key);
}

export function modeLabel(mode: unknown): string {
  const key = String(mode ?? "");
  return MODE_LABELS[key] ?? key;
}
