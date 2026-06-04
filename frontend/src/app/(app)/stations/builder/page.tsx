"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";
import { MediaPreview } from "@/components/media-preview";

// ── Navigation guard ───────────────────────────────────────────────────

function useNavigationGuard(hasUnsavedChanges: boolean) {
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

const defaultForm = {
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

const defaultInstrumentDraft: InstrumentDraft = {
  name: "",
  tool_type: "lista_cotejo",
  free_observation: true,
  items: [
    { label: "", score_per_item: "1" },
    { label: "", score_per_item: "1" },
    { label: "", score_per_item: "1" },
  ],
};

const defaultStudentQuestions: StudentQuestion[] = [
  { prompt: "", type: "single_choice", optionsText: "" },
];

const stationTypeOptions = [
  { value: "procedimental", label: "Procedimental" },
  { value: "actitudinal", label: "Actitudinal" },
  { value: "conceptual", label: "Conceptual" },
];

const circuitOptions = ["Circuito A", "Circuito B", "Circuito C"];
type FormKey = keyof typeof defaultForm;
type AssessmentMode = "existing" | "create";
type InstrumentDraftItem = {
  label: string;
  score_per_item: string;
};
type InstrumentDraft = {
  name: string;
  tool_type: string;
  free_observation: boolean;
  items: InstrumentDraftItem[];
};
type StudentQuestion = {
  prompt: string;
  type: string;
  optionsText: string;
};

function createBuilderSnapshot({
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

type FieldConfigItem = {
  label: string;
  description: string;
  placeholder?: string;
  multiline?: boolean;
};

const fieldConfig: Record<FormKey, FieldConfigItem> = {
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

function FieldBlock({
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

function BuilderSection({
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
                    ? "bg-teal-100 text-teal-700"
                    : "bg-slate-100 text-slate-500"
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

const instrumentTypeOptions = [
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

const builderOriginOptions = [
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

export default function StationBuilderPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { token, eventId, user } = useECOE();
  const builderScope = searchParams.get("scope") === "bank" ? "bank" : "ecoe";
  const editingStationId = Number(searchParams.get("stationId") ?? "");
  const isEditing = Number.isFinite(editingStationId) && editingStationId > 0;
  const editingBankStationId = Number(searchParams.get("bankStationId") ?? "");
  const isEditingBankStation =
    builderScope === "bank" && Number.isFinite(editingBankStationId) && editingBankStationId > 0;
  const useBankStationId = Number(searchParams.get("useBankStationId") ?? "");
  const isUsingBankStation =
    builderScope === "ecoe" && Number.isFinite(useBankStationId) && useBankStationId > 0;
  const { data: templates } = useApi(
    () => api.templates(token!) as Promise<Record<string, unknown>[]>,
    [token],
  );
  const { data: instruments, setData: setInstruments } = useApi(
    () => api.instruments(token!) as Promise<Record<string, unknown>[]>,
    [token],
  );
  const { data: stations, setData: setStations } = useApi(
    () => api.stations(eventId, token!) as Promise<Record<string, unknown>[]>,
    [eventId, token],
  );
  const { data: bankStations, setData: setBankStations } = useApi(
    () => api.stationBank(token!) as Promise<Record<string, unknown>[]>,
    [token],
  );
  const { data: patients } = useApi(
    () => api.simulatedPatients(token!) as Promise<Record<string, unknown>[]>,
    [token],
  );
  const { data: mediaAssets, setData: setMediaAssets } = useApi(
    () =>
      isEditing
        ? (api.media(editingStationId, token!) as Promise<Record<string, unknown>[]>)
        : Promise.resolve([] as Record<string, unknown>[]),
    [editingStationId, isEditing, token],
  );
  const [form, setForm] = useState(defaultForm);
  const [assessmentMode, setAssessmentMode] = useState<AssessmentMode>("existing");
  const [selectedAssessmentToolId, setSelectedAssessmentToolId] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [instrumentDraft, setInstrumentDraft] = useState<InstrumentDraft>(defaultInstrumentDraft);
  const [studentQuestions, setStudentQuestions] =
    useState<StudentQuestion[]>(defaultStudentQuestions);
  const [bankStatus, setBankStatus] = useState("en_diseno");
  const [expandedSection, setExpandedSection] = useState<1 | 2 | 3 | 4>(1);
  const [mediaTargetViewer, setMediaTargetViewer] = useState("estudiante");
  const [mediaMessage, setMediaMessage] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [instrumentMessage, setInstrumentMessage] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const sectionRefs = useRef<Record<1 | 2 | 3 | 4, HTMLElement | null>>({
    1: null,
    2: null,
    3: null,
    4: null,
  });
  const pendingScrollSectionRef = useRef<1 | 2 | 3 | 4 | null>(null);
  const selectedTemplate =
    (templates ?? []).find((template) => String(template.id) === selectedTemplateId) ?? null;
  const selectedTemplateConfig =
    ((selectedTemplate?.default_configuration as Record<string, unknown> | undefined) ?? {});
  const selectedBankStation =
    (bankStations ?? []).find((station) => String(station.id) === String(useBankStationId)) ?? null;
  const selectedTemplateCategory = String(selectedTemplate?.category ?? "").toLowerCase();
  const templateUsesStudentForm =
    Boolean(selectedTemplateConfig.requires_student_form) ||
    selectedTemplateCategory.includes("formulario") ||
    selectedTemplateCategory.includes("hibrid");
  const templateUsesMultimedia =
    Boolean(selectedTemplateConfig.uses_multimedia) ||
    selectedTemplateCategory.includes("multimedia") ||
    selectedTemplateCategory.includes("hibrid");
  const templateUsesSimulatedPatient =
    Boolean(selectedTemplateConfig.uses_simulated_patient) ||
    selectedTemplateCategory.includes("paciente") ||
    selectedTemplateCategory.includes("hibrid");
  const nextStationNumber = String(
    ((stations ?? []).reduce((max, station) => {
      const value = Number(station.station_number ?? 0);
      return value > max ? value : max;
    }, 0) || 0) + 1,
  );

  const bankStatusOptions = [
    { value: "en_diseno", label: "En diseño" },
    { value: "piloteada", label: "Piloteada" },
    { value: "aprobada", label: "Aprobada" },
    { value: "archivada", label: "Archivada" },
  ];

  const updateField = (key: FormKey, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const hasStudentQuestions = studentQuestions.some((question) => {
    const prompt = question.prompt.trim();
    if (!prompt) {
      return false;
    }
    if (question.type === "short_text") {
      return true;
    }
    return question.optionsText
      .split("\n")
      .map((option) => option.trim())
      .filter(Boolean).length > 0;
  });

  const stepCompletion: Record<1 | 2 | 3 | 4, boolean> = {
    1:
      Boolean(form.name.trim()) &&
      Boolean(form.station_type.trim()) &&
      Boolean(form.expected_outcomes.trim()) &&
      Boolean(form.student_activity.trim()),
    2:
      Boolean(selectedAssessmentToolId) &&
      (!templateUsesSimulatedPatient || Boolean(selectedPatientId)),
    3:
      Boolean(form.pre_entry_instruction.trim()) &&
      Boolean(form.student_station_instruction.trim()) &&
      Boolean(form.evaluator_instruction.trim()) &&
      (!templateUsesStudentForm || hasStudentQuestions),
    4:
      Boolean(form.materials.trim()) &&
      (!templateUsesMultimedia ||
        Boolean(form.multimedia_notes.trim()) ||
        Boolean((mediaAssets ?? []).length)),
  };
  const completedSteps = (Object.values(stepCompletion).filter(Boolean).length);
  const completionPercent = Math.round((completedSteps / 4) * 100);
  const currentBuilderSnapshot = useMemo(
    () =>
      createBuilderSnapshot({
        builderScope,
        form,
        selectedAssessmentToolId,
        selectedTemplateId,
        selectedPatientId,
        instrumentDraft,
        studentQuestions,
        bankStatus,
        assessmentMode,
      }),
    [
      assessmentMode,
      bankStatus,
      builderScope,
      form,
      instrumentDraft,
      selectedAssessmentToolId,
      selectedPatientId,
      selectedTemplateId,
      studentQuestions,
    ],
  );
  const [savedSnapshot, setSavedSnapshot] = useState(currentBuilderSnapshot);
  const hasUnsavedChanges = currentBuilderSnapshot !== savedSnapshot;
  const saveButtonLabel = isSaving
    ? "Guardando..."
    : hasUnsavedChanges
      ? builderScope === "bank"
        ? isEditingBankStation
          ? "Guardar cambios en banco"
          : "Guardar estación en banco"
        : isEditing
          ? "Guardar cambios"
          : "Guardar estación"
      : "Cambios guardados";

  const builderFlowSteps = [
    {
      index: 1 as const,
      title: "1. Identidad de la estación",
      description: "Nombre, tipo, circuito, y resultados esperados.",
    },
    {
      index: 2 as const,
      title: "2. Instrumento de evaluación",
      description: "Plantilla, pauta, y paciente simulado.",
    },
    {
      index: 3 as const,
      title: "3. Instrucciones",
      description: "Qué ve el estudiante y cómo evalúa el docente.",
    },
    {
      index: 4 as const,
      title: "4. Recursos y multimedia",
      description: "Materiales, archivos, y formulario del estudiante.",
    },
  ];

  const updateInstrumentItem = (
    index: number,
    field: keyof InstrumentDraftItem,
    value: string,
  ) => {
    setInstrumentDraft((current) => ({
      ...current,
      items: current.items.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [field]: value } : item,
      ),
    }));
  };

  const addInstrumentItem = () => {
    setInstrumentDraft((current) => ({
      ...current,
      items: [...current.items, { label: "", score_per_item: "1" }],
    }));
  };

  const removeInstrumentItem = (index: number) => {
    setInstrumentDraft((current) => ({
      ...current,
      items:
        current.items.length === 1
          ? current.items
          : current.items.filter((_, itemIndex) => itemIndex !== index),
    }));
  };

  const updateStudentQuestion = (
    index: number,
    field: keyof StudentQuestion,
    value: string,
  ) => {
    setStudentQuestions((current) =>
      current.map((question, questionIndex) =>
        questionIndex === index ? { ...question, [field]: value } : question,
      ),
    );
  };

  const addStudentQuestion = () => {
    setStudentQuestions((current) => [
      ...current,
      { prompt: "", type: "single_choice", optionsText: "" },
    ]);
  };

  const removeStudentQuestion = (index: number) => {
    setStudentQuestions((current) =>
      current.length === 1 ? current : current.filter((_, questionIndex) => questionIndex !== index),
    );
  };

  const buildInstrumentPayload = () => {
    const cleanItems = instrumentDraft.items
      .map((item, index) => ({
        label: item.label.trim(),
        score_per_item: Number(item.score_per_item),
        order_index: index + 1,
      }))
      .filter((item) => item.label && item.score_per_item > 0);

    if (!instrumentDraft.name.trim()) {
      throw new Error("Debes escribir un nombre para la pauta de evaluación.");
    }

    if (!cleanItems.length) {
      throw new Error("Debes agregar al menos un criterio evaluable en la pauta.");
    }

    return {
      name: instrumentDraft.name.trim(),
      tool_type: instrumentDraft.tool_type,
      max_score: Number(form.max_score),
      free_observation: instrumentDraft.free_observation,
      items: cleanItems,
    };
  };

  const saveInstrumentDraft = async () => {
    const createdInstrument = (await api.createInstrument(
      buildInstrumentPayload(),
      token!,
    )) as Record<string, unknown>;

    setInstruments((current) => {
      const existing = current ?? [];
      if (existing.some((instrument) => Number(instrument.id) === Number(createdInstrument.id))) {
        return existing.map((instrument) =>
          Number(instrument.id) === Number(createdInstrument.id) ? createdInstrument : instrument,
        );
      }
      return [...existing, createdInstrument];
    });
    setSelectedAssessmentToolId(String(createdInstrument.id));
    setAssessmentMode("existing");
    setInstrumentMessage("Pauta guardada correctamente y asociada a esta estación.");
    return createdInstrument;
  };

  const renderTextField = (key: FormKey) => {
    const config = fieldConfig[key];
    const wide = Boolean(config.multiline);

    return (
      <FieldBlock
        key={key}
        label={config.label}
        description={config.description}
        wide={wide}
      >
        {config.multiline ? (
          <textarea
            rows={4}
            placeholder={config.placeholder}
            value={form[key]}
            onChange={(event) => updateField(key, event.target.value)}
          />
        ) : (
          <input
            placeholder={config.placeholder}
            value={form[key]}
            onChange={(event) => updateField(key, event.target.value)}
          />
        )}
      </FieldBlock>
    );
  };

  const buildStudentFormDefinition = () => ({
    questions: studentQuestions
      .map((question) => ({
        type: question.type,
        label: question.prompt.trim(),
        options:
          question.type === "short_text"
            ? []
            : question.optionsText
                .split("\n")
                .map((option) => option.trim())
                .filter(Boolean),
      }))
      .filter((question) => question.label),
  });

  const buildStationPayload = () => ({
    ecoe_event_id: eventId,
    template_id: Number(selectedTemplateId) || null,
    assessment_tool_id: selectedAssessmentToolId ? Number(selectedAssessmentToolId) : null,
    simulated_patient_id: Number(selectedPatientId) || null,
    ...form,
    station_number: Number(isEditing ? form.station_number : nextStationNumber),
    max_score: Number(form.max_score),
    requires_evaluator: true,
    requires_student_form: templateUsesStudentForm,
    uses_multimedia: templateUsesMultimedia,
    uses_simulated_patient: templateUsesSimulatedPatient,
    uses_physical_resources: true,
    student_form_definition: buildStudentFormDefinition(),
    contingency_ready: true,
    status: "en_diseno",
  });

  const buildStationBankPayload = () => ({
    template_id: Number(selectedTemplateId) || null,
    assessment_tool_id: selectedAssessmentToolId ? Number(selectedAssessmentToolId) : null,
    simulated_patient_id: Number(selectedPatientId) || null,
    name: form.name,
    station_type: form.station_type,
    circuit_name: form.circuit_name,
    expected_outcomes: form.expected_outcomes,
    student_activity: form.student_activity,
    student_station_instruction: form.student_station_instruction,
    pre_entry_instruction: form.pre_entry_instruction,
    evaluator_instruction: form.evaluator_instruction,
    requires_evaluator: true,
    requires_student_form: templateUsesStudentForm,
    uses_multimedia: templateUsesMultimedia,
    uses_simulated_patient: templateUsesSimulatedPatient,
    uses_physical_resources: true,
    max_score: Number(form.max_score),
    materials: form.materials,
    clinical_equipment: "",
    simulator: "",
    ambience: "",
    multimedia_notes: form.multimedia_notes,
    student_form_definition: buildStudentFormDefinition(),
    contingency_ready: true,
    status: bankStatus,
  });

  const applyStationLikeData = useCallback((station: Record<string, unknown>) => {
    const nextForm = {
      station_number: String(station.station_number ?? nextStationNumber),
      name: String(station.name ?? ""),
      station_type: String(station.station_type ?? "procedimental"),
      circuit_name: String(station.circuit_name ?? "Circuito A"),
      expected_outcomes: String(station.expected_outcomes ?? ""),
      student_activity: String(station.student_activity ?? ""),
      student_station_instruction: String(station.student_station_instruction ?? ""),
      pre_entry_instruction: String(station.pre_entry_instruction ?? ""),
      evaluator_instruction: String(station.evaluator_instruction ?? ""),
      max_score: String(station.max_score ?? "0"),
      materials: String(station.materials ?? ""),
      multimedia_notes: String(station.multimedia_notes ?? ""),
    };
    const nextSelectedTemplateId = station.template_id ? String(station.template_id) : "";
    const nextSelectedPatientId = station.simulated_patient_id
      ? String(station.simulated_patient_id)
      : "";
    const nextSelectedAssessmentToolId = station.assessment_tool_id
      ? String(station.assessment_tool_id)
      : "";
    const nextBankStatus = String(station.status ?? "en_diseno");
    setAssessmentMode("existing");
    const rawQuestions = (
      station.student_form_definition as { questions?: Record<string, unknown>[] } | undefined
    )?.questions;
    const nextStudentQuestions =
      Array.isArray(rawQuestions) && rawQuestions.length
        ? rawQuestions.map((question) => ({
            prompt: String(question.label ?? ""),
            type: String(question.type ?? "single_choice"),
            optionsText: Array.isArray(question.options)
              ? (question.options as unknown[]).map((option) => String(option)).join("\n")
              : "",
          }))
        : defaultStudentQuestions;

    setForm(nextForm);
    setSelectedTemplateId(nextSelectedTemplateId);
    setSelectedPatientId(nextSelectedPatientId);
    setSelectedAssessmentToolId(nextSelectedAssessmentToolId);
    setInstrumentDraft(defaultInstrumentDraft);
    setBankStatus(nextBankStatus);
    setStudentQuestions(nextStudentQuestions);
    setSavedSnapshot(
      createBuilderSnapshot({
        builderScope,
        form: nextForm,
        selectedAssessmentToolId: nextSelectedAssessmentToolId,
        selectedTemplateId: nextSelectedTemplateId,
        selectedPatientId: nextSelectedPatientId,
        instrumentDraft: defaultInstrumentDraft,
        studentQuestions: nextStudentQuestions,
        bankStatus: nextBankStatus,
        assessmentMode: "existing",
      }),
    );
  }, [builderScope, nextStationNumber]);

  const openSection = useCallback((section: 1 | 2 | 3 | 4) => {
    pendingScrollSectionRef.current = section;
    setExpandedSection(section);
  }, []);

  const confirmDiscardChanges = useCallback(() => {
    if (!hasUnsavedChanges) {
      return true;
    }
    return window.confirm(
      "Tienes cambios sin guardar en esta estación. Si sales ahora, podrías perderlos. ¿Quieres salir de todos modos?",
    );
  }, [hasUnsavedChanges]);

  useEffect(() => {
    if (user?.role === "evaluador") {
      router.replace("/evaluator");
    }
  }, [router, user?.role]);

  useNavigationGuard(hasUnsavedChanges);

  useEffect(() => {
    setForm((current) =>
      current.station_number === nextStationNumber
        ? current
        : { ...current, station_number: nextStationNumber },
    );
  }, [nextStationNumber]);

  useEffect(() => {
    if (assessmentMode !== "create") {
      return;
    }

    const totalScore = instrumentDraft.items.reduce((sum, item) => {
      const score = Number(item.score_per_item);
      return Number.isFinite(score) ? sum + score : sum;
    }, 0);

    setForm((current) => ({
      ...current,
      max_score: totalScore > 0 ? String(totalScore) : current.max_score,
    }));
  }, [assessmentMode, instrumentDraft.items]);

  useEffect(() => {
    if (!isEditing || !stations?.length || builderScope !== "ecoe") {
      return;
    }

    const station = stations.find((item) => Number(item.id) === editingStationId);
    if (!station) {
      return;
    }
    applyStationLikeData(station);
  }, [applyStationLikeData, builderScope, editingStationId, isEditing, nextStationNumber, stations]);

  useEffect(() => {
    if (!isEditingBankStation || !bankStations?.length) {
      return;
    }
    const bankStation = bankStations.find((item) => Number(item.id) === editingBankStationId);
    if (!bankStation) {
      return;
    }
    applyStationLikeData(bankStation);
  }, [applyStationLikeData, bankStations, editingBankStationId, isEditingBankStation]);

  useEffect(() => {
    if (!isUsingBankStation || isEditing || builderScope !== "ecoe" || !selectedBankStation) {
      return;
    }
    applyStationLikeData(selectedBankStation);
    setMessage(
      `Estás creando una estación del ECOE a partir del banco: ${String(selectedBankStation.name ?? "")}.`,
    );
  }, [applyStationLikeData, builderScope, isEditing, isUsingBankStation, selectedBankStation]);

  useEffect(() => {
    if (pendingScrollSectionRef.current !== expandedSection) {
      return;
    }

    const target = sectionRefs.current[expandedSection];
    if (!target) {
      return;
    }

    const scrollToSection = () => {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      pendingScrollSectionRef.current = null;
    };

    if (typeof window !== "undefined") {
      window.setTimeout(scrollToSection, 40);
    }
  }, [expandedSection]);

  if (user?.role === "evaluador") {
    return (
      <SectionCard
        title="Acceso restringido"
        subtitle="El perfil evaluador no puede editar estaciones."
      >
        <p>Te estamos redirigiendo a tu interfaz operativa.</p>
      </SectionCard>
    );
  }

  return (
    <SectionCard>
      {hasUnsavedChanges ? (
        <div className="mb-4 flex items-center justify-between rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3">
          <p className="text-sm font-semibold text-amber-800">
            ⚠️ Tienes cambios sin guardar. Recuerda guardar antes de salir.
          </p>
          <button
            type="button"
            className="btn-primary text-xs"
            disabled={isSaving}
            onClick={() => {
              const formEl = document.querySelector("form") as HTMLFormElement | null;
              formEl?.requestSubmit();
            }}
          >
            {isSaving ? "Guardando..." : "Guardar ahora"}
          </button>
        </div>
      ) : null}
      <section className="space-y-4 rounded-3xl border border-indigo-200 bg-indigo-50/70 p-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-700">
            Ruta de trabajo
          </p>
          <h2 className="mt-2 text-2xl text-slate-950">
            {builderScope === "bank"
              ? isEditingBankStation
                ? "Editar estación del banco"
                : "Constructor del banco de estaciones"
              : isEditing
                ? "Editar estación"
                : "Constructor de estaciones"}
          </h2>
          <p className="mt-1 text-sm font-medium text-slate-700">
            Haz clic en cada paso para abrirlo, completarlo y avanzar con menos ruido visual.
          </p>
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          {builderFlowSteps.map((step, index) => (
            <button
              key={step.title}
              type="button"
              className={`rounded-2xl border px-4 py-4 text-left transition ${
                expandedSection === step.index
                  ? "border-teal-600 bg-white text-slate-900 shadow-sm"
                  : "border-indigo-200 bg-white/80 text-slate-700 hover:border-indigo-300"
              }`}
              onClick={() => openSection(step.index)}
            >
              <div className="flex items-start gap-4">
                <div
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${
                    stepCompletion[step.index]
                      ? "bg-emerald-600 text-white"
                      : "bg-teal-700 text-white"
                  }`}
                >
                  {stepCompletion[step.index] ? "✓" : index + 1}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold">{step.title}</p>
                    <span
                      className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.12em] ${
                        stepCompletion[step.index]
                          ? "bg-emerald-100 text-emerald-700"
                          : expandedSection === step.index
                            ? "bg-teal-100 text-teal-700"
                            : "bg-slate-100 text-slate-500"
                      }`}
                    >
                      {stepCompletion[step.index] ? "Completo" : expandedSection === step.index ? "En curso" : "Pendiente"}
                    </span>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-slate-600">{step.description}</p>
                </div>
              </div>
            </button>
          ))}
        </div>

        <div className="rounded-2xl border border-white/70 bg-white/90 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Avance del constructor
              </p>
              <p className="mt-1 text-sm text-slate-700">
                {completedSteps} de 4 pasos completos. El constructor te lleva al inicio del bloque activo.
              </p>
            </div>
            <p className="text-sm font-semibold text-slate-900">{completionPercent}%</p>
          </div>
          <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-gradient-to-r from-teal-500 to-emerald-500 transition-all"
              style={{ width: `${completionPercent}%` }}
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-700">
            {builderScope === "bank"
              ? isEditingBankStation
                ? "Modo: editando banco"
                : "Modo: creando banco"
              : isUsingBankStation
                ? "Modo: desde banco hacia ECOE"
              : isEditing
                ? "Modo: editando ECOE"
                : "Modo: nueva estación del ECOE"}
          </span>
          {builderScope === "bank" ? (
            <span className="rounded-full bg-white px-3 py-1 text-xs text-slate-600">
              Estación reutilizable para futuros ECOE
            </span>
          ) : null}
        </div>
      </section>

      <form
        className="space-y-6"
        onSubmit={async (event) => {
          event.preventDefault();
          setMessage(null);
          setIsSaving(true);
          try {
            if (assessmentMode === "create") {
              throw new Error(
                "Debes guardar primero la pauta de evaluación antes de guardar los cambios de la estación.",
              );
            }

            if (builderScope === "bank") {
              const bankPayload = buildStationBankPayload();

              if (
                templateUsesStudentForm &&
                !bankPayload.student_form_definition.questions.length
              ) {
                throw new Error(
                  "Debes agregar al menos una pregunta en el formulario del estudiante para este tipo de estación del banco.",
                );
              }

              if (isEditingBankStation) {
                const updatedBankStation = (await api.updateStationBank(
                  editingBankStationId,
                  bankPayload,
                  token!,
                )) as Record<string, unknown>;
                setBankStations((current) =>
                  (current ?? []).map((station) =>
                    Number(station.id) === editingBankStationId ? updatedBankStation : station,
                  ),
                );
                setMessage("Estación del banco actualizada correctamente.");
                setSavedSnapshot(currentBuilderSnapshot);
                return;
              }

              const createdBankStation = (await api.createStationBank(
                bankPayload,
                token!,
              )) as Record<string, unknown>;
              setBankStations((current) => [createdBankStation, ...(current ?? [])]);
              setMessage("Estación del banco guardada correctamente.");
              setSavedSnapshot(currentBuilderSnapshot);
              router.replace(`/stations/builder?scope=bank&bankStationId=${String(createdBankStation.id)}`);
              return;
            }

            const payload = buildStationPayload();

            if (
              templateUsesStudentForm &&
              !payload.student_form_definition.questions.length
            ) {
              throw new Error(
                "Debes agregar al menos una pregunta en el formulario del estudiante para este tipo de estación.",
              );
            }

            if (isEditing) {
              const updatedStation = (await api.updateStation(
                editingStationId,
                payload,
                token!,
              )) as Record<string, unknown>;
              setStations((current) =>
                (current ?? []).map((station) =>
                  Number(station.id) === editingStationId ? updatedStation : station,
                ),
              );
              setMessage("Estación actualizada correctamente.");
              setSavedSnapshot(currentBuilderSnapshot);
              return;
            }

            const createdStation = (await api.createStation(
              payload,
              token!,
            )) as Record<string, unknown>;
            setStations((current) => [...(current ?? []), createdStation]);
            setMessage(
              "Estación creada correctamente. Ya puedes seguir editándola y cargar recursos si hace falta.",
            );
            router.replace(`/stations/builder?stationId=${String(createdStation.id)}`);
          } catch (error) {
            setMessage(error instanceof Error ? error.message : "No se pudo guardar.");
          } finally {
            setIsSaving(false);
          }
        }}
      >
        <BuilderSection
          index={1}
          title="Origen y base de la estación"
          subtitle="Primero define desde dónde nace esta estación y luego completa su identidad pedagógica central."
          expanded={expandedSection === 1}
          completed={stepCompletion[1]}
          onToggle={() => openSection(1)}
          sectionRef={(node) => {
            sectionRefs.current[1] = node;
          }}
        >
          <div className="mb-5 space-y-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
            <div>
              <p className="text-sm font-semibold text-slate-900">Origen de la estación</p>
              <p className="mt-1 text-xs leading-5 text-slate-600">
                Esta decisión ordena el resto del trabajo. Elige desde dónde quieres construir.
              </p>
            </div>
            <div className="grid gap-3 lg:grid-cols-3">
              {builderOriginOptions.map((option) => {
                const isActive =
                  (option.href === "/stations/builder" && builderScope === "ecoe" && !isUsingBankStation) ||
                  (option.href === "/station-bank" && isUsingBankStation) ||
                  (option.href.includes("scope=bank") && builderScope === "bank");

                return (
                  <Link
                    key={option.label}
                    href={option.href}
                    onClick={(event) => {
                      if (confirmDiscardChanges()) {
                        return;
                      }
                      event.preventDefault();
                    }}
                    className={`rounded-2xl border px-4 py-4 transition ${
                      isActive
                        ? "border-teal-600 bg-white text-slate-900"
                        : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                    }`}
                  >
                    <p className="text-sm font-semibold">{option.label}</p>
                    <p className="mt-2 text-xs leading-5 text-slate-600">{option.description}</p>
                  </Link>
                );
              })}
            </div>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            {builderScope === "ecoe" ? (
              <FieldBlock
                label={fieldConfig.station_number.label}
                description={fieldConfig.station_number.description}
              >
                <input
                  value={isEditing ? form.station_number : nextStationNumber}
                  readOnly
                  className="bg-slate-100 text-slate-600"
                />
              </FieldBlock>
            ) : (
              <FieldBlock
                label="Estado de la estación en el banco"
                description="Indica si esta estación aún está en diseño, si ya fue piloteada o si ya está aprobada para reutilización."
              >
                <select
                  value={bankStatus}
                  onChange={(event) => setBankStatus(event.target.value)}
                >
                  {bankStatusOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </FieldBlock>
            )}
            {renderTextField("name")}
            <FieldBlock
              label={fieldConfig.station_type.label}
              description={fieldConfig.station_type.description}
              wide
            >
              <div className="grid items-stretch gap-3 md:grid-cols-3">
                {stationTypeOptions.map((option) => {
                  const checked = form.station_type === option.value;
                  return (
                    <label
                      key={option.value}
                      className={`flex w-full min-w-0 cursor-pointer items-center gap-3 rounded-2xl border px-4 py-4 transition ${
                        checked
                          ? "border-[var(--color-primary)] bg-[var(--color-bg-soft)] shadow-sm"
                          : "border-slate-200 bg-white hover:border-slate-300"
                      }`}
                    >
                      <span
                        className={`flex size-5 shrink-0 items-center justify-center rounded-full border-2 transition ${
                          checked
                            ? "border-[var(--color-primary)] bg-[var(--color-primary)]"
                            : "border-slate-300"
                        }`}
                      >
                        {checked ? (
                          <span className="size-2 rounded-full bg-white" />
                        ) : null}
                      </span>
                      <span className="min-w-0 break-words text-sm font-semibold text-slate-800">
                        {option.label}
                      </span>
                      <input
                        type="radio"
                        name="station_type"
                        value={option.value}
                        checked={checked}
                        onChange={(event) => updateField("station_type", event.target.value)}
                        className="sr-only"
                      />
                    </label>
                  );
                })}
              </div>
            </FieldBlock>
            {builderScope === "ecoe" ? (
              <FieldBlock
                label={fieldConfig.circuit_name.label}
                description={fieldConfig.circuit_name.description}
              >
                <select
                  value={form.circuit_name}
                  onChange={(event) => updateField("circuit_name", event.target.value)}
                >
                  {circuitOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </FieldBlock>
            ) : (
              <FieldBlock
                label="Circuito sugerido"
                description="Puedes dejar un circuito de referencia, aunque después el ECOE concreto lo cambie."
              >
                <select
                  value={form.circuit_name}
                  onChange={(event) => updateField("circuit_name", event.target.value)}
                >
                  {circuitOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              </FieldBlock>
            )}
            {renderTextField("expected_outcomes")}
            {renderTextField("student_activity")}
            <div className="lg:col-span-2 flex justify-end">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => openSection(2)}
              >
                Continuar a configuración
              </button>
            </div>
          </div>
        </BuilderSection>

        <BuilderSection
          index={2}
          title="Configuración académica"
          subtitle="Aquí decides la plantilla, la pauta y los apoyos que activan el flujo real de la estación."
          expanded={expandedSection === 2}
          completed={stepCompletion[2]}
          onToggle={() => openSection(2)}
          sectionRef={(node) => {
            sectionRefs.current[2] = node;
          }}
        >
          <div className="grid gap-4 lg:grid-cols-2">
            <FieldBlock
              label="Plantilla de referencia"
              description="Usa una plantilla si quieres partir desde una estructura ya preparada."
            >
              <select
                value={selectedTemplateId}
                onChange={(event) => setSelectedTemplateId(event.target.value)}
              >
                <option value="">Crear sin plantilla</option>
                {(templates ?? []).map((template) => (
                  <option key={String(template.id)} value={String(template.id)}>
                    {String(template.name)}
                  </option>
                ))}
              </select>
              <p className="text-xs leading-5 text-slate-500">
                Aquí se define la modalidad operativa de la estación, por ejemplo, si usará
                formulario del estudiante, apoyo multimedia, paciente simulado o una modalidad
                híbrida.
              </p>
              {selectedTemplate ? (
                <p className="text-xs leading-5 text-slate-600">
                  Plantilla seleccionada: {String(selectedTemplate.name)} · categoría{" "}
                  {String(selectedTemplate.category ?? "sin categoría")}
                </p>
              ) : null}
              <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-xs leading-6 text-slate-600">
                Esta decisión afecta el flujo posterior. Por ejemplo:
                {` `}
                `Híbrida` combina evaluador, formulario y multimedia;
                {` `}
                `Formulario estudiante` activa preguntas para el estudiante;
                {` `}
                `Paciente simulado` espera un personaje asociado.
              </div>
            </FieldBlock>
            <FieldBlock
              label="Instrumento de evaluación"
              description="Define aquí mismo la pauta que completará el evaluador o reutiliza una ya creada."
              wide
            >
              <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className={assessmentMode === "existing" ? "btn-primary" : "btn-secondary"}
                    onClick={() => {
                      setAssessmentMode("existing");
                      setInstrumentMessage(null);
                    }}
                  >
                    Usar pauta existente
                  </button>
                  <button
                    type="button"
                    className={assessmentMode === "create" ? "btn-primary" : "btn-secondary"}
                    onClick={() => {
                      setAssessmentMode("create");
                      setInstrumentMessage(null);
                    }}
                  >
                    Crear pauta en esta estación
                  </button>
                </div>

                {assessmentMode === "existing" ? (
                  <div className="space-y-3">
                    <p className="text-sm text-slate-600">
                      Elige una pauta ya creada si quieres reutilizarla tal como está.
                    </p>
                    <select
                      name="assessment_tool_id"
                      value={selectedAssessmentToolId}
                      onChange={(event) => setSelectedAssessmentToolId(event.target.value)}
                    >
                      <option value="">Aún sin instrumento asignado</option>
                      {(instruments ?? []).map((instrument) => (
                        <option key={String(instrument.id)} value={String(instrument.id)}>
                          {String(instrument.name)}
                        </option>
                      ))}
                    </select>
                    <p className="text-xs leading-5 text-slate-500">
                      Las pautas creadas para este ECOE quedan guardadas en el banco de instrumentos
                      y luego puedes reutilizarlas en otras estaciones.
                    </p>
                    <p className="text-xs leading-5 text-slate-500">
                      Si lo que necesitas es que el estudiante responda preguntas en pantalla, eso
                      no se configura en esta pauta. Debes usar la plantilla adecuada y completar el
                      formulario del estudiante en la sección correspondiente.
                    </p>
                    {instrumentMessage ? (
                      <p className="text-sm text-[var(--color-primary)]">{instrumentMessage}</p>
                    ) : null}
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="flex items-start justify-between gap-3 rounded-2xl border border-slate-200 bg-white/80 p-4">
                      <div className="space-y-1">
                        <p className="text-sm font-semibold text-slate-800">
                          Construye aquí la pauta exacta que verá el evaluador en esta estación.
                        </p>
                        <p className="text-xs leading-5 text-slate-500">
                          Esta pauta se guardará en el banco de instrumentos para que después puedas
                          reutilizarla o editarla con más calma.
                        </p>
                      </div>
                      <button
                        type="button"
                        className="rounded-full border border-slate-300 px-3 py-1 text-sm font-semibold text-slate-600 transition hover:border-slate-400 hover:text-slate-900"
                        onClick={() => {
                          setAssessmentMode("existing");
                          setInstrumentMessage(null);
                        }}
                        aria-label="Cerrar creación de pauta"
                      >
                        X
                      </button>
                    </div>

                    <FieldBlock
                      label="Nombre de la pauta"
                      description="Escribe un nombre claro para reconocer esta pauta después."
                    >
                      <input
                        value={instrumentDraft.name}
                        placeholder="Ejemplo: Lista de cotejo - dolor torácico"
                        onChange={(event) =>
                          setInstrumentDraft((current) => ({
                            ...current,
                            name: event.target.value,
                          }))
                        }
                      />
                    </FieldBlock>

                    <FieldBlock
                      label="Tipo de pauta"
                      description="Selecciona la forma en que el evaluador calificará el desempeño."
                    >
                      <select
                        value={instrumentDraft.tool_type}
                        onChange={(event) =>
                          setInstrumentDraft((current) => ({
                            ...current,
                            tool_type: event.target.value,
                          }))
                        }
                      >
                        {instrumentTypeOptions.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </FieldBlock>

                    <div className="rounded-2xl border border-slate-200 bg-white/80 p-4 text-sm text-slate-700">
                      {
                        instrumentTypeOptions.find(
                          (option) => option.value === instrumentDraft.tool_type,
                        )?.description
                      }
                    </div>

                    <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={instrumentDraft.free_observation}
                        onChange={(event) =>
                          setInstrumentDraft((current) => ({
                            ...current,
                            free_observation: event.target.checked,
                          }))
                        }
                      />
                      Permitir observación libre adicional para el evaluador
                    </label>

                    <div className="space-y-3">
                      <div>
                        <h5 className="text-sm font-semibold text-slate-800">
                          Criterios o ítems de evaluación
                        </h5>
                        <p className="mt-1 text-xs leading-5 text-slate-500">
                          Agrega aquí los pasos, conductas o criterios que deberá marcar el evaluador.
                        </p>
                      </div>

                      {instrumentDraft.items.map((item, index) => (
                        <div
                          key={`${index}-${instrumentDraft.tool_type}`}
                          className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 lg:grid-cols-[1.4fr_0.5fr_auto]"
                        >
                          <label className="space-y-2">
                            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                              Criterio {index + 1}
                            </span>
                            <input
                              value={item.label}
                              placeholder="Ejemplo: Identifica signos de alarma al inicio de la entrevista"
                              onChange={(event) =>
                                updateInstrumentItem(index, "label", event.target.value)
                              }
                            />
                          </label>
                          <label className="space-y-2">
                            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                              Puntaje
                            </span>
                            <input
                              type="number"
                              min="0.5"
                              step="0.5"
                              value={item.score_per_item}
                              onChange={(event) =>
                                updateInstrumentItem(index, "score_per_item", event.target.value)
                              }
                            />
                          </label>
                          <div className="flex items-end">
                            <button
                              type="button"
                              className="btn-secondary"
                              onClick={() => removeInstrumentItem(index)}
                              disabled={instrumentDraft.items.length === 1}
                            >
                              Quitar
                            </button>
                          </div>
                        </div>
                      ))}

                      <button type="button" className="btn-secondary" onClick={addInstrumentItem}>
                        Agregar criterio
                      </button>
                    </div>

                    <div className="flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={async () => {
                          setInstrumentMessage(null);
                          try {
                            await saveInstrumentDraft();
                          } catch (error) {
                            setInstrumentMessage(
                              error instanceof Error ? error.message : "No se pudo guardar la pauta.",
                            );
                          }
                        }}
                      >
                        Guardar pauta
                      </button>
                      <p className="text-sm text-slate-600">
                        Este paso guarda la pauta y la deja seleccionada para la estación.
                      </p>
                    </div>
                    {instrumentMessage ? (
                      <p className="text-sm text-slate-700">{instrumentMessage}</p>
                    ) : null}
                  </div>
                )}
              </div>
            </FieldBlock>
            <FieldBlock
              label="Paciente simulado asociado"
              description="Vincula un personaje solo si la estación requiere interacción con paciente simulado."
            >
              <select
                value={selectedPatientId}
                onChange={(event) => setSelectedPatientId(event.target.value)}
              >
                <option value="">No aplica para esta estación</option>
                {(patients ?? []).map((patient) => (
                  <option key={String(patient.id)} value={String(patient.id)}>
                    {String(patient.character_name)}
                  </option>
                ))}
              </select>
            </FieldBlock>
            <FieldBlock
              label={fieldConfig.max_score.label}
              description={
                assessmentMode === "create"
                  ? "Este puntaje se calcula automáticamente según la suma de los criterios de la pauta que estás creando."
                  : fieldConfig.max_score.description
              }
            >
              <input
                placeholder={fieldConfig.max_score.placeholder}
                value={form.max_score}
                onChange={(event) => updateField("max_score", event.target.value)}
                readOnly={assessmentMode === "create"}
                className={assessmentMode === "create" ? "bg-slate-100 text-slate-600" : ""}
              />
            </FieldBlock>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700 lg:col-span-2">
              {assessmentMode === "create"
                ? `El puntaje total de la estación se calcula automáticamente desde la pauta que estás construyendo: ${form.max_score} puntos.`
                : "Si reutilizas una pauta existente, revisa que el puntaje total de la estación coincida con el instrumento seleccionado."}
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-700 lg:col-span-2">
              Piensa este bloque como el puente entre el diseño docente y la ejecución real:
              aquí defines qué verá el evaluador, si el estudiante responderá en pantalla y si la
              estación dependerá de multimedia o paciente simulado.
            </div>
            <div className="lg:col-span-2 flex justify-end">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => openSection(3)}
              >
                Continuar a instrucciones
              </button>
            </div>
          </div>
        </BuilderSection>

        {templateUsesStudentForm ? (
          <section className="space-y-4 rounded-3xl border border-indigo-200 bg-indigo-50/70 p-5">
            <div>
              <h4 className="text-xl text-slate-900">Formulario que responderá el estudiante</h4>
              <p className="mt-1 text-sm text-slate-700">
                Esta mini ventana se activa porque la plantilla seleccionada requiere respuesta del
                estudiante en interfaz. Define aquí las preguntas que verá dentro de la estación.
              </p>
            </div>
            <div className="rounded-2xl border border-indigo-200 bg-white/90 px-4 py-3 text-sm leading-6 text-slate-700">
              Lo que escribas aquí es exactamente lo que luego aparecerá en la vista del
              estudiante. Conviene usar preguntas cortas, claras y sin dobles interpretaciones.
            </div>
            <div className="space-y-4">
              {studentQuestions.map((question, index) => (
                <div
                  key={`student-question-${index}`}
                  className="grid gap-4 rounded-2xl border border-indigo-200 bg-white/90 p-4 lg:grid-cols-[1.4fr_0.7fr_auto]"
                >
                  <FieldBlock
                    label={`Pregunta ${index + 1}`}
                    description="Escribe la pregunta o consigna exacta que debe responder el estudiante."
                  >
                    <textarea
                      rows={3}
                      value={question.prompt}
                      placeholder="Ejemplo: ¿Cuál es el diagnóstico sindromático más probable en este caso?"
                      onChange={(event) =>
                        updateStudentQuestion(index, "prompt", event.target.value)
                      }
                    />
                  </FieldBlock>
                  <div className="space-y-4">
                    <FieldBlock
                      label="Tipo de respuesta"
                      description="Selecciona el formato de respuesta que verá el estudiante."
                    >
                      <select
                        value={question.type}
                        onChange={(event) =>
                          updateStudentQuestion(index, "type", event.target.value)
                        }
                      >
                        <option value="single_choice">Selección única</option>
                        <option value="multiple_choice">Selección múltiple</option>
                        <option value="short_text">Respuesta breve</option>
                      </select>
                    </FieldBlock>
                    {question.type !== "short_text" ? (
                      <FieldBlock
                        label="Opciones de respuesta"
                        description="Escribe una opción por línea, en el orden en que deberían aparecer."
                      >
                        <textarea
                          rows={4}
                          value={question.optionsText}
                          placeholder={"Opción A\nOpción B\nOpción C"}
                          onChange={(event) =>
                            updateStudentQuestion(index, "optionsText", event.target.value)
                          }
                        />
                      </FieldBlock>
                    ) : null}
                  </div>
                  <div className="flex items-end">
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={() => removeStudentQuestion(index)}
                      disabled={studentQuestions.length === 1}
                    >
                      Quitar pregunta
                    </button>
                  </div>
                </div>
              ))}
              <div className="flex flex-wrap gap-3">
                <button type="button" className="btn-secondary" onClick={addStudentQuestion}>
                  Agregar pregunta
                </button>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={async () => {
                    if (!isEditing) {
                      setMessage(
                        "Para guardar solo el formulario del estudiante, primero guarda la estación y luego vuelve a editarla.",
                      );
                      return;
                    }
                    try {
                      const payload = buildStationPayload();
                      const updatedStation = (await api.updateStation(
                        editingStationId,
                        payload,
                        token!,
                      )) as Record<string, unknown>;
                      setStations((current) =>
                        (current ?? []).map((station) =>
                          Number(station.id) === editingStationId ? updatedStation : station,
                        ),
                      );
                      setMessage("Formulario del estudiante guardado correctamente.");
                      setSavedSnapshot(currentBuilderSnapshot);
                    } catch (error) {
                      setMessage(
                        error instanceof Error
                          ? error.message
                          : "No se pudo guardar el formulario del estudiante.",
                      );
                    }
                  }}
                >
                  Guardar formulario
                </button>
                <p className="text-sm text-slate-600">
                  Este formulario queda guardado dentro de la estación y se usará después en la
                  interfaz del estudiante.
                </p>
              </div>
            </div>
          </section>
        ) : null}

        <BuilderSection
          index={3}
          title="Instrucciones operativas"
          subtitle="Define lo que guiará al estudiante y al evaluador durante la ejecución real, sin mezclarlo con configuraciones generales del ECOE."
          expanded={expandedSection === 3}
          completed={stepCompletion[3]}
          onToggle={() => openSection(3)}
          sectionRef={(node) => {
            sectionRefs.current[3] = node;
          }}
        >
          <div className="grid gap-4 lg:grid-cols-2">
            {renderTextField("pre_entry_instruction")}
            {renderTextField("student_station_instruction")}
            <div className="lg:col-span-2">{renderTextField("evaluator_instruction")}</div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-700 lg:col-span-2">
              Regla práctica:
              {` `}
              `Instrucción previa de ingreso` es lo que orienta antes de entrar;
              {` `}
              `Instrucciones dentro de la estación` es la orden operativa principal del estudiante;
              {` `}
              `Guía para el evaluador` es lo que ordena la observación y el registro.
            </div>
            <div className="lg:col-span-2 flex justify-end">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => openSection(4)}
              >
                Continuar a recursos
              </button>
            </div>
          </div>
        </BuilderSection>

        <BuilderSection
          index={4}
          title="Recursos y contingencia"
          subtitle="Cierra aquí todo lo necesario para montar la estación sin incertidumbre el día del ECOE."
          expanded={expandedSection === 4}
          completed={stepCompletion[4]}
          onToggle={() => openSection(4)}
          sectionRef={(node) => {
            sectionRefs.current[4] = node;
          }}
        >
          <div className="grid gap-4 lg:grid-cols-2">
            {renderTextField("materials")}
            {renderTextField("multimedia_notes")}
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-700">
            Este bloque no solo documenta materiales: también ayuda a que coordinación, docente y
            evaluador sepan qué debe estar disponible, qué archivo se mostrará y qué hacer si falta
            algún recurso.
          </div>
          <div className="rounded-3xl border border-slate-200 bg-slate-50/80 p-5">
            <div>
              <h5 className="text-lg font-semibold text-slate-900">Archivos multimedia de la estación</h5>
              <p className="mt-1 text-sm text-slate-600">
                Puedes cargar audio, video, PDF, imágenes y documentos Word para usarlos en la
                estación. Si la estación aún no ha sido guardada, primero debes guardarla y luego
                volver a editarla para adjuntar archivos.
              </p>
            </div>

            {isEditing && builderScope === "ecoe" ? (
              <div className="mt-4 space-y-4">
                <div className="grid gap-4 md:grid-cols-[0.7fr_1.3fr]">
                  <FieldBlock
                    label="Visible para"
                    description="Indica a quién se le mostrará este recurso dentro del flujo."
                  >
                    <select
                      value={mediaTargetViewer}
                      onChange={(event) => setMediaTargetViewer(event.target.value)}
                    >
                      <option value="estudiante">Estudiante</option>
                      <option value="evaluador">Evaluador</option>
                      <option value="paciente_simulado">Paciente simulado</option>
                      <option value="coordinacion">Coordinación</option>
                    </select>
                  </FieldBlock>
                  <FieldBlock
                    label="Cargar archivo"
                    description="Formatos sugeridos: audio, video, PDF, imágenes y documentos .doc o .docx."
                  >
                    <input
                      type="file"
                      accept="audio/*,video/*,.pdf,image/*,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                      onChange={async (event) => {
                        const file = event.target.files?.[0];
                        if (!file) {
                          return;
                        }
                        setMediaMessage(null);
                        try {
                          const uploaded = (await api.uploadMedia(
                            {
                              ecoe_event_id: eventId,
                              station_id: editingStationId,
                              target_viewer: mediaTargetViewer,
                              file,
                            },
                            token!,
                          )) as Record<string, unknown>;
                          setMediaAssets((current) => [...(current ?? []), uploaded]);
                          setMediaMessage("Archivo multimedia cargado correctamente.");
                          event.currentTarget.value = "";
                        } catch (error) {
                          setMediaMessage(
                            error instanceof Error ? error.message : "No se pudo cargar el archivo.",
                          );
                        }
                      }}
                    />
                  </FieldBlock>
                </div>

                <div className="space-y-3">
                  {(mediaAssets ?? []).length ? (
                    (mediaAssets ?? []).map((asset) => (
                      <div
                        key={String(asset.id)}
                        className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
                      >
                        <div>
                          <p className="font-semibold text-slate-900">
                            {String(asset.original_name ?? asset.filename ?? "Archivo")}
                          </p>
                          <p className="text-slate-500">
                            {String(asset.content_type ?? "tipo no informado")} · visible para{" "}
                            {String(asset.target_viewer ?? "sin definir")}
                          </p>
                          <div className="mt-2 max-w-xs">
                            <MediaPreview
                              asset={asset as unknown as import("@/lib/types").MediaAsset}
                              token={token!}
                            />
                          </div>
                        </div>
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={async () => {
                            const confirmed = window.confirm(
                              "Vas a borrar este archivo multimedia de la estación. ¿Quieres continuar?",
                            );
                            if (!confirmed) {
                              return;
                            }
                            setMediaMessage(null);
                            try {
                              await api.deleteMedia(Number(asset.id), token!);
                              setMediaAssets((current) =>
                                (current ?? []).filter(
                                  (currentAsset) => Number(currentAsset.id) !== Number(asset.id),
                                ),
                              );
                              setMediaMessage("Archivo multimedia borrado correctamente.");
                            } catch (error) {
                              setMediaMessage(
                                error instanceof Error
                                  ? error.message
                                  : "No se pudo borrar el archivo.",
                              );
                            }
                          }}
                        >
                          Borrar
                        </button>
                      </div>
                    ))
                  ) : (
                    <p className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                      Aún no hay archivos multimedia cargados para esta estación.
                    </p>
                  )}
                </div>

                {mediaMessage ? <p className="text-sm text-slate-700">{mediaMessage}</p> : null}
              </div>
            ) : (
              <p className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                {builderScope === "bank"
                  ? "La carga multimedia sigue asociada a estaciones del ECOE. En el banco, deja aquí las indicaciones y define después los archivos concretos en la estación operativa."
                  : "Guarda primero la estación y luego vuelve a abrirla para cargar archivos multimedia."}
              </p>
            )}
          </div>
        </BuilderSection>

        <div className="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-4">
          <button
            className={`btn-primary transition-all ${
              isSaving
                ? "cursor-wait opacity-90"
                : hasUnsavedChanges
                  ? "shadow-[0_12px_30px_-18px_rgba(13,148,136,0.75)]"
                  : "border-emerald-600 bg-emerald-600 text-white hover:bg-emerald-700"
            }`}
            disabled={isSaving}
          >
            {saveButtonLabel}
          </button>
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              isSaving
                ? "bg-slate-100 text-slate-600"
                : hasUnsavedChanges
                  ? "bg-amber-100 text-amber-800"
                  : "bg-emerald-100 text-emerald-800"
            }`}
          >
            {isSaving
              ? "Guardando ahora"
              : hasUnsavedChanges
                ? "Hay cambios pendientes"
                : "Todo guardado"}
          </span>
          {builderScope === "ecoe" ? (
            <button
              type="button"
              className="btn-secondary"
              onClick={async () => {
                setMessage(null);
                try {
                  if (assessmentMode === "create") {
                    throw new Error(
                      "Debes guardar primero la pauta de evaluación antes de guardar esta estación en el banco.",
                    );
                  }
                  const createdBankStation = (await api.createStationBank(
                    buildStationBankPayload(),
                    token!,
                  )) as Record<string, unknown>;
                  setBankStations((current) => [createdBankStation, ...(current ?? [])]);
                  setMessage("La estación fue guardada también en el banco de estaciones.");
                } catch (error) {
                  setMessage(
                    error instanceof Error
                      ? error.message
                      : "No se pudo guardar la estación en el banco.",
                  );
                }
              }}
            >
              Guardar en banco
            </button>
          ) : null}
          <Link
            href={builderScope === "bank" ? "/station-bank" : "/stations"}
            className="btn-secondary"
            onClick={(event) => {
              if (confirmDiscardChanges()) {
                return;
              }
              event.preventDefault();
            }}
          >
            Volver al listado
          </Link>
          <p className="text-sm text-slate-500">
            {builderScope === "bank"
              ? "Las estaciones del banco quedan disponibles para reutilización posterior en ECOE reales y pueden marcarse como piloteadas o aprobadas."
              : isEditing
                ? "Los cambios se guardan sobre la estación existente, manteniendo su lugar en el circuito."
                : "La estación se crea en estado de diseño para que puedas seguir afinándola después."}
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm leading-6 text-slate-700">
          Antes de cerrar esta pantalla, confirma mentalmente estas cuatro preguntas:
          {` `}
          ¿el estudiante sabe exactamente qué debe hacer?;
          {` `}
          ¿el evaluador sabe exactamente qué debe observar?;
          {` `}
          ¿la pauta o el formulario quedaron guardados?;
          {` `}
          ¿y los recursos necesarios quedaron descritos o cargados?
        </div>
        <StatusNotice message={message} />
      </form>
    </SectionCard>
  );
}
