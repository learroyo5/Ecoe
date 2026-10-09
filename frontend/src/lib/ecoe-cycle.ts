/**
 * Lectura del ciclo de vida del ECOE para orientar al usuario en Inicio.
 * Es sólo presentación: el grafo de transiciones y sus reglas viven en el
 * backend (`services/validation.py`) y en `components/ecoe-form.tsx`.
 */

export type CyclePhase = {
  key: "configurar" | "pilotar" | "publicar" | "ejecutar" | "cerrar";
  label: string;
  statuses: string[];
};

export const CYCLE_PHASES: CyclePhase[] = [
  { key: "configurar", label: "Configurar", statuses: ["borrador", "en_configuracion"] },
  { key: "pilotar", label: "Pilotar", statuses: ["listo_para_pilotaje", "en_pilotaje", "pilotaje_validado"] },
  { key: "publicar", label: "Publicar", statuses: ["publicado"] },
  { key: "ejecutar", label: "Ejecutar", statuses: ["en_ejecucion"] },
  { key: "cerrar", label: "Cerrar", statuses: ["cerrado", "archivado"] },
];

/** Índice de la fase del ciclo para un estado; -1 si el estado es desconocido. */
export function phaseIndexForStatus(status: string): number {
  return CYCLE_PHASES.findIndex((phase) => phase.statuses.includes(status));
}

export type NextStep = {
  title: string;
  detail: string;
  href: string;
  cta: string;
};

type ValidationSnapshot = {
  students_count?: number;
  station_count?: number;
  can_pilot?: boolean;
  can_publish?: boolean;
  blockers?: string[];
};

function pendingCount(validation: ValidationSnapshot): string {
  const count = validation.blockers?.length ?? 0;
  if (count === 0) return "Hay pendientes de validación";
  return count === 1 ? "Hay 1 pendiente de validación" : `Hay ${count} pendientes de validación`;
}

/** El paso que conviene dar ahora según el estado del evento y su validación. */
export function nextStepFor(status: string, validation: ValidationSnapshot = {}): NextStep | null {
  switch (status) {
    case "borrador":
      return {
        title: "Inicia la configuración",
        detail: "Revisa los datos generales del ECOE y pásalo a configuración para armar estaciones y cargar participantes.",
        href: "/ecoe",
        cta: "Ir a Datos del ECOE",
      };
    case "en_configuracion":
      if ((validation.station_count ?? 0) === 0) {
        return {
          title: "Crea las estaciones",
          detail: "El ECOE todavía no tiene estaciones. Créalas desde cero o tráelas del banco.",
          href: "/stations",
          cta: "Ir a Estaciones",
        };
      }
      if ((validation.students_count ?? 0) === 0) {
        return {
          title: "Carga la nómina de estudiantes",
          detail: "Sube la nómina por Excel/CSV o agrega estudiantes uno a uno.",
          href: "/students",
          cta: "Ir a Estudiantes",
        };
      }
      if (!validation.can_pilot) {
        return {
          title: "Resuelve los pendientes de validación",
          detail: `${pendingCount(validation)} antes de poder pilotar.`,
          href: "/validation",
          cta: "Ver Validación",
        };
      }
      return {
        title: "Marca el ECOE como listo para pilotaje",
        detail: "La configuración base está completa. Avanza el estado para habilitar el ensayo.",
        href: "/ecoe",
        cta: "Ir a Datos del ECOE",
      };
    case "listo_para_pilotaje":
      return {
        title: "Inicia el pilotaje",
        detail: "Avanza el estado a «En pilotaje» para ensayar el circuito con tu equipo.",
        href: "/ecoe",
        cta: "Ir a Datos del ECOE",
      };
    case "en_pilotaje":
      return {
        title: "Ensaya el circuito y registra hallazgos",
        detail: "Prueba una estación o el circuito completo; al terminar, valida el pilotaje.",
        href: "/pilotage",
        cta: "Ir a Pilotaje",
      };
    case "pilotaje_validado":
      if (!validation.can_publish) {
        return {
          title: "Resuelve los bloqueos antes de publicar",
          detail: `${pendingCount(validation)} que impiden publicar.`,
          href: "/validation",
          cta: "Ver Validación",
        };
      }
      return {
        title: "Publica el ECOE",
        detail: "El pilotaje está validado y no hay bloqueos. Publicar deja lista la sesión en vivo.",
        href: "/publication",
        cta: "Ir a Publicación",
      };
    case "publicado":
      return {
        title: "Inicia la ejecución el día del examen",
        detail: "Todo está publicado. Cuando comience el examen, pasa el ECOE a «En ejecución».",
        href: "/ecoe",
        cta: "Ir a Datos del ECOE",
      };
    case "en_ejecucion":
      return {
        title: "Opera el examen desde el Panel en vivo",
        detail: "Controla el cronómetro, las rotaciones y las incidencias del circuito.",
        href: "/live",
        cta: "Abrir Panel en vivo",
      };
    case "cerrado":
      return {
        title: "Revisa y exporta los resultados",
        detail: "El ECOE está cerrado y sus resultados quedaron consolidados.",
        href: "/results",
        cta: "Ver Resultados",
      };
    case "archivado":
      return {
        title: "ECOE archivado",
        detail: "Sigue disponible en modo lectura.",
        href: "/results",
        cta: "Ver Resultados",
      };
    default:
      return null;
  }
}
