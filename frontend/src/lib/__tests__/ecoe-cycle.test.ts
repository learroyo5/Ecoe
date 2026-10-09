import { describe, expect, it } from "vitest";

import { CYCLE_PHASES, nextStepFor, phaseIndexForStatus } from "@/lib/ecoe-cycle";

const ALL_STATUSES = [
  "borrador",
  "en_configuracion",
  "listo_para_pilotaje",
  "en_pilotaje",
  "pilotaje_validado",
  "publicado",
  "en_ejecucion",
  "cerrado",
  "archivado",
];

describe("phaseIndexForStatus", () => {
  it("ubica cada estado del ciclo en exactamente una fase", () => {
    for (const status of ALL_STATUSES) {
      expect(CYCLE_PHASES.filter((phase) => phase.statuses.includes(status))).toHaveLength(1);
    }
    expect(phaseIndexForStatus("borrador")).toBe(0);
    expect(phaseIndexForStatus("pilotaje_validado")).toBe(1);
    expect(phaseIndexForStatus("archivado")).toBe(4);
  });

  it("devuelve -1 para un estado desconocido", () => {
    expect(phaseIndexForStatus("inventado")).toBe(-1);
  });
});

describe("nextStepFor", () => {
  it("propone un paso para todo estado conocido y ninguno para uno desconocido", () => {
    for (const status of ALL_STATUSES) expect(nextStepFor(status)).not.toBeNull();
    expect(nextStepFor("inventado")).toBeNull();
  });

  it("en configuración prioriza estaciones, luego nómina, luego validación", () => {
    expect(nextStepFor("en_configuracion", { station_count: 0, students_count: 0 })?.href).toBe("/stations");
    expect(nextStepFor("en_configuracion", { station_count: 4, students_count: 0 })?.href).toBe("/students");
    const pending = nextStepFor("en_configuracion", {
      station_count: 4,
      students_count: 20,
      can_pilot: false,
      blockers: ["a", "b"],
    });
    expect(pending?.href).toBe("/validation");
    expect(pending?.detail).toContain("2 pendientes");
    expect(nextStepFor("en_configuracion", { station_count: 4, students_count: 20, can_pilot: true })?.href).toBe("/ecoe");
  });

  it("no manda a publicar mientras la validación no lo permita", () => {
    expect(nextStepFor("pilotaje_validado", { can_publish: false, blockers: ["x"] })?.href).toBe("/validation");
    expect(nextStepFor("pilotaje_validado", { can_publish: true })?.href).toBe("/publication");
  });

  it("en ejecución lleva al panel en vivo y al cerrar a resultados", () => {
    expect(nextStepFor("en_ejecucion")?.href).toBe("/live");
    expect(nextStepFor("cerrado")?.href).toBe("/results");
  });
});
