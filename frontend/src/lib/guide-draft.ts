// Estaciones sugeridas desde una guía de simulación: tipos de la respuesta
// del backend (services/guide_import.py), su paso por sessionStorage entre
// la pantalla de sugerencias y el Constructor, y la conversión al estado del
// Constructor. Nada de esto guarda en el servidor: es un borrador.

export type GuideFieldSource = "guia" | "ia" | "falta";

export type GuideQuestion = {
  label: string;
  type: string;
  options: string[];
  points: number;
  correct_option?: string | null;
  correct_options?: string[];
};

export type GuideStationSuggestion = {
  name: string;
  station_type: string;
  rationale: string;
  suggested_minutes: number | null;
  expected_outcomes: string;
  student_activity: string;
  pre_entry_instruction: string;
  student_station_instruction: string;
  evaluator_instruction: string;
  materials: string;
  clinical_equipment: string;
  simulator: string;
  ambience: string;
  requires_evaluator: boolean;
  requires_student_form: boolean;
  requires_deferred_grading: boolean;
  uses_simulated_patient: boolean;
  max_score: number;
  instrument: {
    name: string;
    tool_type: string;
    max_score: number;
    items: { label: string; score_per_item: number }[];
  } | null;
  student_form_definition: { questions: GuideQuestion[] };
  field_sources: Record<string, GuideFieldSource>;
  missing: string[];
  warnings: string[];
};

export type GuideSuggestionResult = {
  guide_title: string;
  summary: string;
  warnings: string[];
  stations: GuideStationSuggestion[];
};

export type GuideSession = {
  eventId: number;
  filename: string;
  result: GuideSuggestionResult;
  // Índices de las propuestas que ya se guardaron como estación.
  created: number[];
};

const STORAGE_KEY = "ecoe.guideSuggestions";

export function loadGuideSession(eventId: number): GuideSession | null {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as GuideSession;
    if (session?.eventId !== eventId || !Array.isArray(session?.result?.stations)) return null;
    return { ...session, created: Array.isArray(session.created) ? session.created : [] };
  } catch {
    return null;
  }
}

export function saveGuideSession(session: GuideSession | null) {
  try {
    if (session) window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    else window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Sin sessionStorage la propuesta sólo vive mientras dure la pantalla.
  }
}

export function markGuideStationCreated(eventId: number, index: number) {
  const session = loadGuideSession(eventId);
  if (!session || session.created.includes(index)) return;
  saveGuideSession({ ...session, created: [...session.created, index] });
}

/** El Constructor tiene un solo campo de recursos: se arma por secciones. */
export function composeGuideMaterials(station: GuideStationSuggestion): string {
  return [
    ["Insumos", station.materials],
    ["Equipos y mobiliario", station.clinical_equipment],
    ["Simulador", station.simulator],
    ["Ambientación", station.ambience],
  ]
    .filter(([, text]) => text.trim())
    .map(([title, text]) => `${title}:\n${text.trim()}`)
    .join("\n\n");
}

/** Forma «estación» que entiende applyStationLikeData del Constructor. */
export function guideStationToStationLike(station: GuideStationSuggestion): Record<string, unknown> {
  return {
    name: station.name,
    station_type: station.station_type,
    expected_outcomes: station.expected_outcomes,
    student_activity: station.student_activity,
    student_station_instruction: station.student_station_instruction,
    pre_entry_instruction: station.pre_entry_instruction,
    evaluator_instruction: station.evaluator_instruction,
    max_score: station.max_score,
    materials: composeGuideMaterials(station),
    multimedia_notes: "",
    requires_evaluator: station.requires_evaluator,
    requires_student_form: station.requires_student_form,
    requires_deferred_grading: station.requires_deferred_grading,
    uses_multimedia: false,
    uses_simulated_patient: station.uses_simulated_patient,
    student_form_definition: station.student_form_definition,
  };
}

const FIELD_LABELS: Record<string, string> = {
  expected_outcomes: "desempeños esperados",
  student_activity: "actividad del estudiante",
  pre_entry_instruction: "instrucción previa",
  student_station_instruction: "instrucciones internas",
  evaluator_instruction: "guía del evaluador",
  materials: "insumos",
  clinical_equipment: "equipos",
  simulator: "simulador",
  ambience: "ambientación",
};

/** Qué viene de la guía y qué redactó la IA, para que el docente sepa qué revisar. */
export function describeGuideSources(station: GuideStationSuggestion) {
  const fromGuide: string[] = [];
  const fromAi: string[] = [];
  for (const [field, label] of Object.entries(FIELD_LABELS)) {
    const source = station.field_sources[field];
    if (source === "guia") fromGuide.push(label);
    else if (source === "ia") fromAi.push(label);
  }
  if (station.instrument) fromGuide.push(`pauta (${station.instrument.items.length} criterios)`);
  if (station.student_form_definition.questions.length) {
    fromAi.push(`preguntas del formulario (${station.student_form_definition.questions.length})`);
  }
  return { fromGuide, fromAi, missing: station.missing };
}
