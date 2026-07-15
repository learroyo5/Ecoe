"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";
import { StationIdentityStep } from "./identity-step";
import { InstrumentStep, StudentFormSection } from "./instrument-step";
import { InstructionsStep } from "./instructions-step";
import { ResourcesStep } from "./resources-step";
import {
  FieldBlock,
  createBuilderSnapshot,
  defaultForm,
  defaultInstrumentDraft,
  defaultStudentQuestions,
  fieldConfig,
  useNavigationGuard,
  type AssessmentMode,
  type FormKey,
  type InstrumentDraft,
  type InstrumentDraftItem,
  type StepIndex,
  type StudentQuestion,
} from "./shared";

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

const bankStatusOptions = [
  { value: "en_diseno", label: "En diseño" },
  { value: "piloteada", label: "Piloteada" },
  { value: "aprobada", label: "Aprobada" },
  { value: "archivada", label: "Archivada" },
];

export default function StationBuilderPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { authenticated, eventId, user } = useECOE();
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
    () => api.templates(eventId) as Promise<Record<string, unknown>[]>,
    [authenticated, eventId],
  );
  const { data: instruments, setData: setInstruments } = useApi(
    () => api.instruments(eventId) as Promise<Record<string, unknown>[]>,
    [authenticated, eventId],
  );
  const { data: stations, setData: setStations } = useApi(
    () => api.stations(eventId) as Promise<Record<string, unknown>[]>,
    [eventId, authenticated],
  );
  const { data: bankStations, setData: setBankStations } = useApi(
    () => api.stationBank(eventId) as Promise<Record<string, unknown>[]>,
    [authenticated, eventId],
  );
  const { data: patients } = useApi(
    () => api.simulatedPatients(eventId) as Promise<Record<string, unknown>[]>,
    [authenticated, eventId],
  );
  const { data: mediaAssets, setData: setMediaAssets } = useApi(
    () =>
      isEditing
        ? (api.media(editingStationId) as Promise<Record<string, unknown>[]>)
        : Promise.resolve([] as Record<string, unknown>[]),
    [editingStationId, isEditing, authenticated],
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
  const [expandedSection, setExpandedSection] = useState<StepIndex>(1);
  const [mediaTargetViewer, setMediaTargetViewer] = useState("estudiante");
  const [mediaMessage, setMediaMessage] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [instrumentMessage, setInstrumentMessage] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const sectionRefs = useRef<Record<StepIndex, HTMLElement | null>>({
    1: null,
    2: null,
    3: null,
    4: null,
  });
  const pendingScrollSectionRef = useRef<StepIndex | null>(null);
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

  const stepCompletion: Record<StepIndex, boolean> = {
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
      eventId,
      buildInstrumentPayload(),
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

  const openSection = useCallback((section: StepIndex) => {
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

  // Plain function (not memoized), matching every other handler in this
  // component: it must always close over the current render's form/state,
  // not a stale snapshot from whenever a useCallback last recreated it.
  const handleSaveStudentForm = async () => {
    try {
      const payload = buildStationPayload();
      const updatedStation = (await api.updateStation(
        editingStationId,
        payload,
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
  };

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
                            ? "bg-teal-100 text-teal-700 animate-pulse-soft"
                            : "bg-orange-50 text-orange-600"
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
            let newInstrumentId: number | null = null;
            // If creating a new instrument, save it first automatically
            if (assessmentMode === "create") {
              setMessage("Guardando la pauta de evaluación primero...");
              const created = await saveInstrumentDraft();
              newInstrumentId = Number(created.id);
            }

            if (builderScope === "bank") {
              const bankPayload = buildStationBankPayload();
              if (newInstrumentId) bankPayload.assessment_tool_id = newInstrumentId;

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
                  eventId,
                  editingBankStationId,
                  bankPayload,
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
                eventId,
                bankPayload,
              )) as Record<string, unknown>;
              setBankStations((current) => [createdBankStation, ...(current ?? [])]);
              setMessage("Estación del banco guardada correctamente.");
              setSavedSnapshot(currentBuilderSnapshot);
              router.replace(`/stations/builder?scope=bank&bankStationId=${String(createdBankStation.id)}`);
              return;
            }

            const payload = buildStationPayload();
            if (newInstrumentId) payload.assessment_tool_id = newInstrumentId;

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
        <StationIdentityStep
          scaffold={{
            expandedSection,
            stepCompleted: stepCompletion[1],
            openSection,
            sectionRef: (node) => { sectionRefs.current[1] = node; },
          }}
          builderScope={builderScope}
          isUsingBankStation={isUsingBankStation}
          confirmDiscardChanges={confirmDiscardChanges}
          isEditing={isEditing}
          form={form}
          nextStationNumber={nextStationNumber}
          bankStatus={bankStatus}
          setBankStatus={setBankStatus}
          bankStatusOptions={bankStatusOptions}
          updateField={updateField}
          renderTextField={renderTextField}
          onContinue={() => openSection(2)}
        />

        <InstrumentStep
          scaffold={{
            expandedSection,
            stepCompleted: stepCompletion[2],
            openSection,
            sectionRef: (node) => { sectionRefs.current[2] = node; },
          }}
          templates={templates}
          selectedTemplateId={selectedTemplateId}
          setSelectedTemplateId={setSelectedTemplateId}
          selectedTemplate={selectedTemplate}
          assessmentMode={assessmentMode}
          setAssessmentMode={setAssessmentMode}
          instrumentMessage={instrumentMessage}
          setInstrumentMessage={setInstrumentMessage}
          selectedAssessmentToolId={selectedAssessmentToolId}
          setSelectedAssessmentToolId={setSelectedAssessmentToolId}
          instruments={instruments}
          instrumentDraft={instrumentDraft}
          setInstrumentDraft={setInstrumentDraft}
          updateInstrumentItem={updateInstrumentItem}
          addInstrumentItem={addInstrumentItem}
          removeInstrumentItem={removeInstrumentItem}
          saveInstrumentDraft={saveInstrumentDraft}
          selectedPatientId={selectedPatientId}
          setSelectedPatientId={setSelectedPatientId}
          patients={patients}
          maxScore={form.max_score}
          updateField={updateField}
          onContinue={() => openSection(3)}
        />

        {templateUsesStudentForm ? (
          <StudentFormSection
            studentQuestions={studentQuestions}
            updateStudentQuestion={updateStudentQuestion}
            addStudentQuestion={addStudentQuestion}
            removeStudentQuestion={removeStudentQuestion}
            isEditing={isEditing}
            onSaveStudentForm={handleSaveStudentForm}
          />
        ) : null}

        <InstructionsStep
          scaffold={{
            expandedSection,
            stepCompleted: stepCompletion[3],
            openSection,
            sectionRef: (node) => { sectionRefs.current[3] = node; },
          }}
          renderTextField={renderTextField}
          onContinue={() => openSection(4)}
        />

        <ResourcesStep
          scaffold={{
            expandedSection,
            stepCompleted: stepCompletion[4],
            openSection,
            sectionRef: (node) => { sectionRefs.current[4] = node; },
          }}
          renderTextField={renderTextField}
          isEditing={isEditing}
          builderScope={builderScope}
          eventId={eventId}
          editingStationId={editingStationId}
          mediaTargetViewer={mediaTargetViewer}
          setMediaTargetViewer={setMediaTargetViewer}
          mediaMessage={mediaMessage}
          setMediaMessage={setMediaMessage}
          mediaAssets={mediaAssets}
          setMediaAssets={setMediaAssets}
        />

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
                    setMessage("Guardando la pauta primero...");
                    await saveInstrumentDraft();
                  }
                  const createdBankStation = (await api.createStationBank(
                    eventId,
                    buildStationBankPayload(),
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
