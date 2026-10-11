import { beforeEach, describe, expect, it } from "vitest";

import {
  composeGuideMaterials,
  describeGuideSources,
  guideStationToStationLike,
  loadGuideSession,
  markGuideStationCreated,
  saveGuideSession,
  type GuideStationSuggestion,
} from "@/lib/guide-draft";

const station: GuideStationSuggestion = {
  name: "Higiene de manos con alcohol gel",
  station_type: "procedimental",
  rationale: "",
  suggested_minutes: 3,
  expected_outcomes: "Realiza higienización.",
  student_activity: "Realiza la técnica.",
  pre_entry_instruction: "Higieniza tus manos.",
  student_station_instruction: "",
  evaluator_instruction: "Observa sin guiar.",
  materials: "Alcohol gel: 1",
  clinical_equipment: "",
  simulator: "",
  ambience: "Mesa con dispensador.",
  requires_evaluator: true,
  requires_student_form: false,
  requires_deferred_grading: false,
  uses_simulated_patient: false,
  max_score: 10,
  instrument: {
    name: "Pauta",
    tool_type: "lista_cotejo",
    max_score: 10,
    items: [{ label: "Retira joyas", score_per_item: 1 }],
  },
  student_form_definition: { questions: [] },
  field_sources: {
    expected_outcomes: "guia",
    evaluator_instruction: "ia",
    student_station_instruction: "falta",
  },
  missing: ["instrucciones dentro de la estación"],
  warnings: [],
};

const result = { guide_title: "Manos", summary: "", warnings: [], stations: [station] };

describe("guide-draft", () => {
  beforeEach(() => window.sessionStorage.clear());

  it("arma los recursos por secciones y omite las vacías", () => {
    expect(composeGuideMaterials(station)).toBe(
      "Insumos:\nAlcohol gel: 1\n\nAmbientación:\nMesa con dispensador.",
    );
  });

  it("convierte la propuesta a la forma que carga el Constructor", () => {
    const like = guideStationToStationLike(station);
    expect(like.name).toBe(station.name);
    expect(like.max_score).toBe(10);
    expect(like.requires_evaluator).toBe(true);
    // Nunca apunta a una pauta existente: la pauta se crea al guardar.
    expect(like.assessment_tool_id).toBeUndefined();
  });

  it("separa lo tomado de la guía de lo redactado por la IA", () => {
    const sources = describeGuideSources(station);
    expect(sources.fromGuide).toEqual(["desempeños esperados", "pauta (1 criterios)"]);
    expect(sources.fromAi).toEqual(["guía del evaluador"]);
    expect(sources.missing).toEqual(["instrucciones dentro de la estación"]);
  });

  it("la propuesta no se muestra en otro ECOE", () => {
    saveGuideSession({ eventId: 1, filename: "g.docx", result, created: [] });
    expect(loadGuideSession(1)?.result.stations).toHaveLength(1);
    expect(loadGuideSession(2)).toBeNull();
  });

  it("marca una propuesta como creada una sola vez", () => {
    saveGuideSession({ eventId: 1, filename: "g.docx", result, created: [] });
    markGuideStationCreated(1, 0);
    markGuideStationCreated(1, 0);
    expect(loadGuideSession(1)?.created).toEqual([0]);
  });

  it("tolera contenido corrupto en sessionStorage", () => {
    window.sessionStorage.setItem("ecoe.guideSuggestions", "{no es json");
    expect(loadGuideSession(1)).toBeNull();
  });
});
