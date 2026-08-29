"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { api } from "@/lib/api";
import type { AssessmentTool } from "@/lib/types";
import { useECOE } from "@/lib/auth";
import { canEditStations } from "@/lib/permissions";
import { defaultRouteForRole } from "@/lib/routes";
import { useApi } from "@/hooks/use-api";
import { StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";
import { StationIdentityStep } from "./identity-step";
import { InstrumentStep, StudentFormSection } from "./instrument-step";
import { InstructionsStep } from "./instructions-step";
import { ResourcesStep } from "./resources-step";
import {
  FieldBlock,
  capabilityConfig,
  createBuilderSnapshot,
  defaultCapabilities,
  defaultForm,
  defaultInstrumentDraft,
  defaultStudentQuestions,
  fieldConfig,
  useNavigationGuard,
  type AssessmentMode,
  type FormKey,
  type InstrumentDraft,
  type InstrumentDraftItem,
  type StationCapabilities,
  type StepIndex,
  type StudentQuestion,
} from "./shared";

const builderFlowSteps = [
  { index: 1 as const, title: "Identidad" },
  { index: 2 as const, title: "Evaluación" },
  { index: 3 as const, title: "Instrucciones" },
  { index: 4 as const, title: "Recursos" },
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
  const { authenticated, eventId, user, eventRoles, eventRolesLoaded } = useECOE();
  // El constructor es solo edición: espeja require_roles("admin_ecoe",
  // "coeditor_docente") del backend, contra el rol EFECTIVO del evento (OPT-3).
  const canEdit = canEditStations(user?.role, eventRoles);
  const accessDenied = eventRolesLoaded && !canEdit;
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
  // Pauta completa (con items[].id y reference_count) de la que hoy referencia
  // la estación. Se carga sin cambiar de modo: habilita el botón "Editar esta
  // pauta" (OPT-7c). null = sin tool seleccionado o no se pudo cargar.
  const [loadedTool, setLoadedTool] = useState<AssessmentTool | null>(null);
  const loadedToolIdRef = useRef<number | null>(null);
  // Se enciende cuando un PATCH de pauta devuelve 409 (la pauta ya no es
  // editable porque un ECOE que la usa está en etapa avanzada). Dispara el
  // fallback "Guardar como copia nueva" en el paso de instrumento.
  const [instrumentConflict, setInstrumentConflict] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [selectedPatientId, setSelectedPatientId] = useState("");
  const [instrumentDraft, setInstrumentDraft] = useState<InstrumentDraft>(defaultInstrumentDraft);
  const [studentQuestions, setStudentQuestions] =
    useState<StudentQuestion[]>(defaultStudentQuestions);
  const [bankStatus, setBankStatus] = useState("en_diseno");
  const [capabilities, setCapabilities] = useState<StationCapabilities>(defaultCapabilities);
  // Al editar, todo parte comprimido: se viene a ajustar algo puntual.
  // Al crear, el paso 1 parte abierto para no exigir un clic extra.
  const [expandedSection, setExpandedSection] = useState<StepIndex | null>(
    isEditing || isEditingBankStation ? null : 1,
  );
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
  const selectedBankStation =
    (bankStations ?? []).find((station) => String(station.id) === String(useBankStationId)) ?? null;

  // La plantilla solo PRECARGA las capacidades; los switches mandan después.
  const applyTemplatePreset = (templateId: string) => {
    setSelectedTemplateId(templateId);
    const template = (templates ?? []).find((item) => String(item.id) === templateId);
    if (!template) {
      return;
    }
    const config = (template.default_configuration as Record<string, unknown> | undefined) ?? {};
    const category = String(template.category ?? "").toLowerCase();
    const base: StationCapabilities = {
      requiresEvaluator: !(category.includes("formulario") || category.includes("multimedia")),
      requiresStudentForm:
        category.includes("formulario") || category.includes("multimedia") || category.includes("hibrid"),
      requiresDeferredGrading: false,
      usesMultimedia: category.includes("multimedia") || category.includes("hibrid"),
      usesSimulatedPatient: category.includes("paciente"),
    };
    setCapabilities({
      requiresEvaluator: Boolean(config.requires_evaluator ?? base.requiresEvaluator),
      requiresStudentForm: Boolean(config.requires_student_form ?? base.requiresStudentForm),
      requiresDeferredGrading: Boolean(config.requires_deferred_grading ?? base.requiresDeferredGrading),
      usesMultimedia: Boolean(config.uses_multimedia ?? base.usesMultimedia),
      usesSimulatedPatient: Boolean(config.uses_simulated_patient ?? base.usesSimulatedPatient),
    });
  };
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

  const studentFormPointsTotal = studentQuestions.reduce((sum, question) => {
    const points = Number(question.points);
    return Number.isFinite(points) && points > 0 && question.prompt.trim() ? sum + points : sum;
  }, 0);

  // Corrección diferida: exige el formulario del estudiante con al menos una
  // pregunta de respuesta breve puntuada (el backend valida lo mismo).
  const hasManualScoredQuestion = studentQuestions.some(
    (question) =>
      question.type === "short_text" &&
      question.prompt.trim() &&
      Number(question.points) > 0,
  );
  const deferredGradingReady =
    !capabilities.requiresDeferredGrading ||
    (capabilities.requiresStudentForm && hasManualScoredQuestion);

  const stepCompletion: Record<StepIndex, boolean> = {
    1:
      Boolean(form.name.trim()) &&
      Boolean(form.station_type.trim()) &&
      Boolean(form.expected_outcomes.trim()) &&
      Boolean(form.student_activity.trim()),
    2:
      (!capabilities.requiresEvaluator || Boolean(selectedAssessmentToolId)) &&
      (!capabilities.usesSimulatedPatient || Boolean(selectedPatientId)) &&
      (!capabilities.requiresStudentForm || hasStudentQuestions) &&
      deferredGradingReady &&
      Number(form.max_score) > 0,
    3:
      Boolean(form.pre_entry_instruction.trim()) &&
      Boolean(form.student_station_instruction.trim()) &&
      (!capabilities.requiresEvaluator || Boolean(form.evaluator_instruction.trim())),
    4:
      Boolean(form.materials.trim()) &&
      (!capabilities.usesMultimedia ||
        Boolean(form.multimedia_notes.trim()) ||
        Boolean((mediaAssets ?? []).length)),
  };
  const stepPendingHints: Record<StepIndex, string> = {
    1: "Pendiente: nombre, tipo, desempeños esperados o actividad del estudiante",
    2: [
      capabilities.requiresEvaluator && !selectedAssessmentToolId ? "pauta de evaluación" : null,
      capabilities.requiresStudentForm && !hasStudentQuestions ? "preguntas del formulario" : null,
      !deferredGradingReady ? "pregunta de respuesta breve con puntaje (corrección diferida)" : null,
      capabilities.usesSimulatedPatient && !selectedPatientId ? "paciente simulado" : null,
      Number(form.max_score) > 0 ? null : "puntaje máximo",
    ]
      .filter(Boolean)
      .map((item, index) => (index === 0 ? `Pendiente: ${item}` : item))
      .join(" · "),
    3: [
      form.pre_entry_instruction.trim() ? null : "instrucción previa",
      form.student_station_instruction.trim() ? null : "instrucciones internas",
      capabilities.requiresEvaluator && !form.evaluator_instruction.trim() ? "guía del evaluador" : null,
    ]
      .filter(Boolean)
      .map((item, index) => (index === 0 ? `Pendiente: ${item}` : item))
      .join(" · "),
    4: [
      form.materials.trim() ? null : "materiales",
      capabilities.usesMultimedia && !form.multimedia_notes.trim() && !(mediaAssets ?? []).length
        ? "archivos o indicaciones multimedia"
        : null,
    ]
      .filter(Boolean)
      .map((item, index) => (index === 0 ? `Pendiente: ${item}` : item))
      .join(" · "),
  };
  const completedSteps = (Object.values(stepCompletion).filter(Boolean).length);
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
        capabilities,
      }),
    [
      assessmentMode,
      bankStatus,
      builderScope,
      capabilities,
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
      { prompt: "", type: "single_choice", optionsText: "", points: "0", correctText: "" },
    ]);
  };

  const removeStudentQuestion = (index: number) => {
    setStudentQuestions((current) =>
      current.length === 1 ? current : current.filter((_, questionIndex) => questionIndex !== index),
    );
  };

  // `mode` explícito para que los handlers que primero llaman a
  // `setAssessmentMode` (p. ej. "guardar como copia") no dependan del estado
  // que aún no se refrescó en este render.
  const buildInstrumentPayload = (mode: AssessmentMode = assessmentMode) => {
    const cleanItems = instrumentDraft.items
      .map((item, index) => ({
        // El PATCH in-place identifica los ítems existentes por `id`; los
        // nuevos van sin `id` (alta) y los que se quitaron del draft no se
        // envían (baja). En "create" el backend ignora cualquier `id`.
        ...(mode === "edit" && typeof item.id === "number" ? { id: item.id } : {}),
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

  const upsertInstrumentInList = (tool: Record<string, unknown>) => {
    setInstruments((current) => {
      const existing = current ?? [];
      if (existing.some((instrument) => Number(instrument.id) === Number(tool.id))) {
        return existing.map((instrument) =>
          Number(instrument.id) === Number(tool.id) ? tool : instrument,
        );
      }
      return [...existing, tool];
    });
  };

  // Carga los ítems reales del tool en el editor de pauta y entra en modo
  // "edit". El usuario lo pide explícitamente con "Editar esta pauta".
  const startEditingInstrument = () => {
    if (!loadedTool) {
      return;
    }
    setInstrumentDraft({
      name: loadedTool.name,
      tool_type: loadedTool.tool_type,
      free_observation: loadedTool.free_observation,
      items: (loadedTool.items ?? [])
        .slice()
        .sort((a, b) => a.order_index - b.order_index)
        .map((item) => ({
          id: item.id,
          label: item.label,
          score_per_item: String(item.score_per_item),
        })),
    });
    setInstrumentConflict(false);
    setInstrumentMessage(null);
    setAssessmentMode("edit");
  };

  const persistInstrumentDraft = async (mode: AssessmentMode) => {
    if (mode === "edit" && selectedAssessmentToolId) {
      const updated = (await api.updateInstrument(
        eventId,
        Number(selectedAssessmentToolId),
        buildInstrumentPayload("edit"),
      )) as Record<string, unknown>;
      upsertInstrumentInList(updated);
      setLoadedTool(updated as unknown as AssessmentTool);
      loadedToolIdRef.current = Number(updated.id);
      setInstrumentConflict(false);
      setAssessmentMode("existing");
      setInstrumentMessage(
        "Pauta actualizada. El cambio se aplica a todas las estaciones que la usan.",
      );
      return updated;
    }

    const createdInstrument = (await api.createInstrument(
      eventId,
      buildInstrumentPayload("create"),
    )) as Record<string, unknown>;
    upsertInstrumentInList(createdInstrument);
    setSelectedAssessmentToolId(String(createdInstrument.id));
    setInstrumentConflict(false);
    setAssessmentMode("existing");
    setInstrumentMessage("Pauta guardada correctamente y asociada a esta estación.");
    return createdInstrument;
  };

  const saveInstrumentDraft = async (mode: AssessmentMode = assessmentMode) => {
    try {
      return await persistInstrumentDraft(mode);
    } catch (error) {
      if (
        mode === "edit" &&
        (error as { status?: number }).status === 409
      ) {
        // La pauta dejó de ser editable entre que se abrió y se guardó. Se
        // ofrece crear una copia (POST) con los ítems ya cargados.
        setInstrumentConflict(true);
      }
      throw error;
    }
  };

  const saveInstrumentAsCopy = async () => {
    setInstrumentMessage(null);
    await saveInstrumentDraft("create");
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
      .map((question) => {
        const options =
          question.type === "short_text"
            ? []
            : question.optionsText
                .split("\n")
                .map((option) => option.trim())
                .filter(Boolean);
        const correctLines = question.correctText
          .split("\n")
          .map((option) => option.trim())
          .filter(Boolean);
        return {
          type: question.type,
          label: question.prompt.trim(),
          options,
          points: Number(question.points) || 0,
          ...(question.type === "single_choice"
            ? { correct_option: correctLines[0] ?? null }
            : {}),
          ...(question.type === "multiple_choice" ? { correct_options: correctLines } : {}),
        };
      })
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
    requires_evaluator: capabilities.requiresEvaluator,
    requires_student_form: capabilities.requiresStudentForm,
    requires_deferred_grading: capabilities.requiresDeferredGrading,
    uses_multimedia: capabilities.usesMultimedia,
    uses_simulated_patient: capabilities.usesSimulatedPatient,
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
    requires_evaluator: capabilities.requiresEvaluator,
    requires_student_form: capabilities.requiresStudentForm,
    requires_deferred_grading: capabilities.requiresDeferredGrading,
    uses_multimedia: capabilities.usesMultimedia,
    uses_simulated_patient: capabilities.usesSimulatedPatient,
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
    const nextCapabilities: StationCapabilities = {
      requiresEvaluator: Boolean(station.requires_evaluator ?? true),
      requiresStudentForm: Boolean(station.requires_student_form),
      requiresDeferredGrading: Boolean(station.requires_deferred_grading),
      usesMultimedia: Boolean(station.uses_multimedia),
      usesSimulatedPatient: Boolean(station.uses_simulated_patient),
    };
    setAssessmentMode("existing");
    setInstrumentConflict(false);
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
            points: String(question.points ?? "0"),
            correctText: Array.isArray(question.correct_options)
              ? (question.correct_options as unknown[]).map((option) => String(option)).join("\n")
              : question.correct_option
                ? String(question.correct_option)
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
    setCapabilities(nextCapabilities);
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
        capabilities: nextCapabilities,
      }),
    );
  }, [builderScope, nextStationNumber]);

  // Un clic sobre la sección ya abierta la comprime; los botones "Continuar"
  // siempre apuntan a otra sección, así que el toggle no los afecta.
  const openSection = useCallback((section: StepIndex) => {
    setExpandedSection((current) => {
      if (current === section) {
        pendingScrollSectionRef.current = null;
        return null;
      }
      pendingScrollSectionRef.current = section;
      return section;
    });
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
    if (accessDenied) {
      router.replace(defaultRouteForRole(user?.role ?? ""));
    }
  }, [router, accessDenied, user?.role]);

  useNavigationGuard(hasUnsavedChanges);

  useEffect(() => {
    setForm((current) =>
      current.station_number === nextStationNumber
        ? current
        : { ...current, station_number: nextStationNumber },
    );
  }, [nextStationNumber]);

  useEffect(() => {
    // Se recalcula el puntaje máximo mientras se construye la pauta (crear o
    // editar in-place); en "existing" el puntaje lo manda el campo.
    if (assessmentMode === "existing") {
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

  // Carga la pauta referenciada por la estación (o la recién elegida en el
  // <select>) para tener sus items[].id disponibles si el usuario decide
  // "Editar esta pauta". No cambia el modo: seguir en "existing" hasta que el
  // usuario lo pida explícitamente (OPT-7c, decisión del usuario).
  useEffect(() => {
    const toolId = Number(selectedAssessmentToolId);
    if (!selectedAssessmentToolId || !Number.isFinite(toolId) || toolId <= 0) {
      loadedToolIdRef.current = null;
      setLoadedTool(null);
      return;
    }
    if (loadedToolIdRef.current === toolId) {
      return;
    }
    loadedToolIdRef.current = toolId;
    let cancelled = false;
    api
      .instrument(eventId, toolId)
      .then((tool) => {
        if (!cancelled) setLoadedTool(tool as AssessmentTool);
      })
      .catch(() => {
        if (!cancelled) {
          loadedToolIdRef.current = null;
          setLoadedTool(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedAssessmentToolId, eventId]);

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
    if (expandedSection === null || pendingScrollSectionRef.current !== expandedSection) {
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

  if (accessDenied) {
    return (
      <SectionCard
        title="Acceso restringido"
        subtitle="Tu rol en este ECOE no permite editar estaciones."
      >
        <p>Te estamos redirigiendo a tu interfaz operativa.</p>
      </SectionCard>
    );
  }

  const contextModeLabel =
    builderScope === "bank"
      ? isEditingBankStation
        ? "Editando estación del banco"
        : "Nueva estación del banco"
      : isUsingBankStation
        ? "Desde banco hacia ECOE"
        : isEditing
          ? "Editando estación del ECOE"
          : "Nueva estación del ECOE";
  const contextStationLabel =
    builderScope === "ecoe"
      ? `Estación ${isEditing ? form.station_number : nextStationNumber} · ${form.name.trim() || "sin nombre aún"}`
      : form.name.trim() || "Estación del banco sin nombre aún";

  return (
    <SectionCard>
      {/* Barra fija de contexto: siempre se ve qué estación se edita,
          el avance y el estado de guardado, sin importar el scroll. */}
      <div className="sticky top-2 z-30 mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-2xl border border-slate-200 bg-white/95 px-4 py-2.5 shadow-sm backdrop-blur">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--color-primary)]">
            {contextModeLabel}
          </p>
          <p className="truncate text-sm font-semibold text-slate-900">{contextStationLabel}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs text-slate-500">{completedSteps}/4 pasos</span>
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              isSaving
                ? "bg-slate-100 text-slate-600"
                : hasUnsavedChanges
                  ? "bg-amber-100 text-amber-800"
                  : "bg-emerald-100 text-emerald-800"
            }`}
          >
            {isSaving ? "Guardando..." : hasUnsavedChanges ? "Sin guardar" : "Guardado"}
          </span>
          <button
            type="submit"
            form="station-builder-form"
            className="btn-primary px-3 py-2 text-xs"
            disabled={isSaving || !hasUnsavedChanges}
          >
            Guardar
          </button>
        </div>
      </div>

      {/* Stepper compacto: estado de cada paso en una sola línea. */}
      <div className="mb-4 flex flex-wrap items-center gap-2">
        {builderFlowSteps.map((step) => (
          <button
            key={step.title}
            type="button"
            onClick={() => openSection(step.index)}
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition ${
              expandedSection === step.index
                ? "border-teal-600 bg-teal-50 font-semibold text-teal-900"
                : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
            }`}
          >
            <span
              className={`flex size-5 items-center justify-center rounded-full text-[11px] font-semibold ${
                stepCompletion[step.index]
                  ? "bg-emerald-600 text-white"
                  : "bg-slate-200 text-slate-600"
              }`}
            >
              {stepCompletion[step.index] ? "✓" : step.index}
            </span>
            {step.title}
          </button>
        ))}
      </div>

      {/* Capacidades: los switches que definen qué necesita la estación. */}
      <section className="mb-6 rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="text-sm font-semibold text-slate-900">¿Qué necesita esta estación?</p>
          <p className="text-xs text-slate-500">
            La plantilla del paso Evaluación solo precarga estos switches; aquí mandan ellos.
          </p>
        </div>
        <div className="mt-3 grid gap-2 md:grid-cols-2 xl:grid-cols-4">
          {capabilityConfig.map((capability) => {
            const checked = capabilities[capability.key];
            return (
              <label
                key={capability.key}
                className={`flex cursor-pointer flex-col gap-1 rounded-2xl border px-3 py-2.5 transition ${
                  checked
                    ? "border-[var(--color-primary)] bg-white shadow-sm"
                    : "border-slate-200 bg-white/70 hover:border-slate-300"
                }`}
              >
                <span className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={(event) =>
                      setCapabilities((current) => ({
                        ...current,
                        [capability.key]: event.target.checked,
                      }))
                    }
                    className="size-4 shrink-0 accent-[var(--color-primary)]"
                  />
                  {capability.label}
                </span>
                <span className="text-xs leading-5 text-slate-500">{capability.requirement}</span>
              </label>
            );
          })}
        </div>
      </section>

      <form
        id="station-builder-form"
        className="space-y-4"
        onSubmit={async (event) => {
          event.preventDefault();
          setMessage(null);
          setIsSaving(true);
          try {
            let newInstrumentId: number | null = null;
            // Si se está construyendo la pauta (crear una nueva o editar la
            // referenciada in-place), se persiste antes que la estación.
            if (assessmentMode === "create" || assessmentMode === "edit") {
              setMessage(
                assessmentMode === "edit"
                  ? "Guardando los cambios de la pauta primero..."
                  : "Guardando la pauta de evaluación primero...",
              );
              const saved = await saveInstrumentDraft();
              newInstrumentId = Number(saved.id);
            }

            if (builderScope === "bank") {
              const bankPayload = buildStationBankPayload();
              if (newInstrumentId) bankPayload.assessment_tool_id = newInstrumentId;

              if (
                capabilities.requiresStudentForm &&
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
              capabilities.requiresStudentForm &&
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
            pendingHint: stepPendingHints[1],
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
            pendingHint: stepPendingHints[2],
            openSection,
            sectionRef: (node) => { sectionRefs.current[2] = node; },
          }}
          capabilities={capabilities}
          templates={templates}
          selectedTemplateId={selectedTemplateId}
          setSelectedTemplateId={applyTemplatePreset}
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
          loadedTool={loadedTool}
          startEditingInstrument={startEditingInstrument}
          instrumentConflict={instrumentConflict}
          saveInstrumentAsCopy={saveInstrumentAsCopy}
          selectedPatientId={selectedPatientId}
          setSelectedPatientId={setSelectedPatientId}
          patients={patients}
          maxScore={form.max_score}
          studentFormPointsTotal={studentFormPointsTotal}
          updateField={updateField}
          onContinue={() => openSection(3)}
        >
          {capabilities.requiresStudentForm ? (
            <StudentFormSection
              studentQuestions={studentQuestions}
              updateStudentQuestion={updateStudentQuestion}
              addStudentQuestion={addStudentQuestion}
              removeStudentQuestion={removeStudentQuestion}
              isEditing={isEditing}
              onSaveStudentForm={handleSaveStudentForm}
            />
          ) : null}
        </InstrumentStep>

        <InstructionsStep
          scaffold={{
            expandedSection,
            stepCompleted: stepCompletion[3],
            pendingHint: stepPendingHints[3],
            openSection,
            sectionRef: (node) => { sectionRefs.current[3] = node; },
          }}
          requiresEvaluator={capabilities.requiresEvaluator}
          renderTextField={renderTextField}
          onContinue={() => openSection(4)}
        />

        <ResourcesStep
          scaffold={{
            expandedSection,
            stepCompleted: stepCompletion[4],
            pendingHint: stepPendingHints[4],
            openSection,
            sectionRef: (node) => { sectionRefs.current[4] = node; },
          }}
          usesMultimedia={capabilities.usesMultimedia}
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
                  if (assessmentMode === "create" || assessmentMode === "edit") {
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
