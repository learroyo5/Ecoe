"use client";

import { useEffect } from "react";

// ── Navigation guard ───────────────────────────────────────────────────

export function useNavigationGuard(hasUnsavedChanges: boolean) {
  // Block browser tab close/refresh
  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const handler = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [hasUnsavedChanges]);

  // Intercept clicks on sidebar/header links
  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      const link = target.closest("a[href]") as HTMLAnchorElement | null;
      if (!link) return;
      const href = link.getAttribute("href") ?? "";
      // Only intercept internal navigation, not external links or file downloads
      if (href.startsWith("http") || href.startsWith("#") || href.startsWith("mailto:") || href.includes(".")) return;
      if (!window.confirm("Tienes cambios sin guardar en la estacion. Salir sin guardar?")) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
      }
    };
    document.addEventListener("click", handler, true);
    return () => document.removeEventListener("click", handler, true);
  }, [hasUnsavedChanges]);
}

// ── Form defaults & types ───────────────────────────────────────────────

export const defaultForm = {
  station_number: "1",
  name: "",
  station_type: "procedimental",
  circuit_name: "Circuito A",
  expected_outcomes: "",
  student_activity: "",
  student_station_instruction: "",
  pre_entry_instruction: "",
  evaluator_instruction: "",
  max_score: "20",
  materials: "",
  multimedia_notes: "",
};

export type FormKey = keyof typeof defaultForm;
export type AssessmentMode = "existing" | "create";

export type InstrumentDraftItem = {
  label: string;
  score_per_item: string;
};

export type InstrumentDraft = {
  name: string;
  tool_type: string;
  free_observation: boolean;
  items: InstrumentDraftItem[];
};

export type StudentQuestion = {
  prompt: string;
  type: string;
  optionsText: string;
};

export const defaultInstrumentDraft: InstrumentDraft = {
  name: "",
  tool_type: "lista_cotejo",
  free_observation: true,
  items: [
    { label: "", score_per_item: "1" },
    { label: "", score_per_item: "1" },
    { label: "", score_per_item: "1" },
  ],
};

export const defaultStudentQuestions: StudentQuestion[] = [
  { prompt: "", type: "single_choice", optionsText: "" },
];

export const stationTypeOptions = [
  { value: "procedimental", label: "Procedimental" },
  { value: "actitudinal", label: "Actitudinal" },
  { value: "conceptual", label: "Conceptual" },
];

export const circuitOptions = ["Circuito A", "Circuito B", "Circuito C"];

export const instrumentTypeOptions = [
  {
    value: "lista_cotejo",
    label: "Lista de cotejo",
    description: "Sirve cuando quieres verificar pasos o conductas observables como cumplido/no cumplido o con puntaje por ítem.",
  },
  {
    value: "rubrica_simple",
    label: "Rúbrica simple",
    description: "Sirve cuando necesitas valorar la calidad del desempeño en criterios como estructura, comunicación o seguridad.",
  },
  {
    value: "escala_puntaje",
    label: "Escala de puntaje",
    description: "Sirve cuando prefieres una pauta corta, con criterios puntuables y menos detalle descriptivo.",
  },
];

export const builderOriginOptions = [
  {
    label: "Estación nueva del ECOE",
    description:
      "Construye una estación específica para el ECOE que estás editando ahora.",
    href: "/stations/builder",
  },
  {
    label: "Usar una estación del banco",
    description:
      "Carga una estación estándar ya aprobada o piloteada, y adáptala al ECOE actual.",
    href: "/station-bank",
  },
  {
    label: "Crear o editar banco de estaciones",
    description:
      "Trabaja sobre estaciones reutilizables del hospital o de la institución.",
    href: "/stations/builder?scope=bank",
  },
];

export function createBuilderSnapshot({
  builderScope,
  form,
  selectedAssessmentToolId,
  selectedTemplateId,
  selectedPatientId,
  instrumentDraft,
  studentQuestions,
  bankStatus,
  assessmentMode,
}: {
  builderScope: "bank" | "ecoe";
  form: typeof defaultForm;
  selectedAssessmentToolId: string;
  selectedTemplateId: string;
  selectedPatientId: string;
  instrumentDraft: InstrumentDraft;
  studentQuestions: StudentQuestion[];
  bankStatus: string;
  assessmentMode: AssessmentMode;
}) {
  return JSON.stringify({
    builderScope,
    form: {
      ...form,
      station_number: builderScope === "ecoe" ? "" : form.station_number,
    },
    selectedAssessmentToolId,
    selectedTemplateId,
    selectedPatientId,
    instrumentDraft,
    studentQuestions,
    bankStatus,
    assessmentMode,
  });
}

// ── Field rendering ──────────────────────────────────────────────────────

export type FieldConfigItem = {
  label: string;
  description: string;
  placeholder?: string;
  multiline?: boolean;
};

export const fieldConfig: Record<FormKey, FieldConfigItem> = {
  station_number: {
    label: "Número correlativo de la estación",
    description:
      "Este número se asigna automáticamente según las estaciones ya creadas en este ECOE.",
    placeholder: "Se asigna automáticamente",
  },
  name: {
    label: "Nombre breve de la estación",
    description: "Escribe un título claro para identificar rápidamente el caso o procedimiento.",
    placeholder: "Ejemplo: Dolor torácico en urgencia",
  },
  station_type: {
    label: "Tipo de estación",
    description:
      "Selecciona la naturaleza pedagógica de la estación. La modalidad operativa se define más abajo, en la plantilla de referencia.",
  },
  circuit_name: {
    label: "Circuito asignado",
    description: "Indica en qué circuito operativo se ubicará esta estación.",
  },
  expected_outcomes: {
    label: "Aprendizajes o desempeños esperados",
    description: "Describe qué debería demostrar el estudiante al finalizar esta estación.",
    placeholder: "Ejemplo: Reconoce signos de alarma, prioriza diagnósticos y comunica un plan inicial seguro.",
    multiline: true,
  },
  student_activity: {
    label: "Actividad específica del estudiante",
    description:
      "Describe la tarea, el procedimiento o el desempeño central que realizará el estudiante en esta estación.",
    placeholder:
      "Ejemplo: Realizar anamnesis focalizada, examinar al paciente y comunicar una conducta inicial segura.",
    multiline: true,
  },
  student_station_instruction: {
    label: "Instrucciones dentro de la estación para el estudiante",
    description:
      "Escribe la indicación precisa que el estudiante debe seguir una vez que ya esté dentro de la estación.",
    placeholder:
      "Ejemplo: Salude al paciente, explique el procedimiento y luego ejecute la tarea siguiendo el orden esperado.",
    multiline: true,
  },
  pre_entry_instruction: {
    label: "Instrucción previa de ingreso",
    description: "Texto breve que el estudiante leería antes de entrar a la estación.",
    placeholder: "Ejemplo: Revise el motivo de consulta y prepárese para realizar una anamnesis focalizada.",
    multiline: true,
  },
  evaluator_instruction: {
    label: "Guía para el evaluador",
    description: "Indica en qué debe fijarse el evaluador y cómo debe registrar la observación.",
    placeholder: "Ejemplo: Observe la estructura de la entrevista, la seguridad del abordaje y la comunicación con el paciente.",
    multiline: true,
  },
  max_score: {
    label: "Puntaje máximo",
    description: "Puntaje total que podrá obtener el estudiante en esta estación.",
    placeholder: "Ejemplo: 20",
  },
  materials: {
    label: "Materiales y recursos físicos",
    description: "Lista el equipamiento, los insumos o los documentos necesarios para montar la estación.",
    placeholder: "Ejemplo: Fonendoscopio, tensiómetro, ficha clínica impresa, guantes y lápiz.",
    multiline: true,
  },
  multimedia_notes: {
    label: "Indicaciones sobre material multimedia",
    description: "Especifica si se usará audio, video, PDF o imagen, y en qué momento debe mostrarse.",
    placeholder: "Ejemplo: Mostrar ECG inicial al minuto 2 y radiografía de tórax solo si el estudiante la solicita.",
    multiline: true,
  },
};

export function FieldBlock({
  label,
  description,
  children,
  wide = false,
}: {
  label: string;
  description: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  return (
    <div className={`min-w-0 space-y-2 ${wide ? "lg:col-span-2" : ""}`}>
      <span className="block text-sm font-semibold text-slate-800">{label}</span>
      <p className="block text-xs leading-5 text-slate-500">{description}</p>
      {children}
    </div>
  );
}

export function BuilderSection({
  index,
  title,
  subtitle,
  expanded,
  completed = false,
  onToggle,
  children,
  sectionRef,
}: {
  index: number;
  title: string;
  subtitle: string;
  expanded: boolean;
  completed?: boolean;
  onToggle: () => void;
  children: React.ReactNode;
  sectionRef?: (node: HTMLElement | null) => void;
}) {
  return (
    <section
      ref={sectionRef}
      className={`scroll-mt-24 rounded-3xl border bg-white/90 transition ${
        expanded
          ? "border-teal-200 shadow-[0_18px_40px_-32px_rgba(13,148,136,0.55)]"
          : "border-slate-200"
      }`}
    >
      <button
        type="button"
        className="flex w-full items-start justify-between gap-4 px-5 py-5 text-left"
        onClick={onToggle}
      >
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <div
              className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-white ${
                completed ? "bg-emerald-600" : "bg-teal-700"
              }`}
            >
              {completed ? `Paso ${index} listo` : `Paso ${index}`}
            </div>
            <span
              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${
                completed
                  ? "bg-emerald-100 text-emerald-700"
                  : expanded
                    ? "bg-teal-100 text-teal-700 animate-pulse-soft"
                    : "bg-orange-50 text-orange-600"
              }`}
            >
              {completed ? "Completo" : expanded ? "Activo" : "Pendiente"}
            </span>
          </div>
          <h4 className="mt-2 text-xl text-slate-900">{title}</h4>
          <p className="mt-1 text-sm leading-6 text-slate-600">{subtitle}</p>
        </div>
        <span className="rounded-full border border-slate-300 px-3 py-1 text-sm font-semibold text-slate-600">
          {expanded ? "Ocultar" : "Abrir"}
        </span>
      </button>
      {expanded ? <div className="border-t border-slate-200 px-5 py-5">{children}</div> : null}
    </section>
  );
}

export type StepIndex = 1 | 2 | 3 | 4;

/** Common scaffolding props shared by every numbered wizard step. */
export type StepScaffoldProps = {
  expandedSection: StepIndex;
  stepCompleted: boolean;
  openSection: (section: StepIndex) => void;
  sectionRef: (node: HTMLElement | null) => void;
};
