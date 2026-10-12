import { describe, expect, it } from "vitest";

import { describeDistribution, describeSource } from "@/app/(app)/students/student-import";
import type { StudentImportPlan } from "@/lib/types";

const base: StudentImportPlan = {
  dry_run: true,
  imported: 0,
  skipped: 0,
  skipped_rut_duplicate: 0,
  skipped_missing_data: 0,
  with_warnings: 0,
  per_circuit: {},
};

describe("vista previa de la carga de estudiantes", () => {
  it("explica cada forma de repartir en circuitos", () => {
    expect(describeDistribution("halves", ["Circuito A", "Circuito B"])).toContain("Circuito A y Circuito B");
    expect(describeDistribution("first", ["Piso 4"])).toBe("Todos a Piso 4");
    expect(describeDistribution("first", [])).toBe("Todos a Circuito A");
    expect(describeDistribution("file", ["Circuito A"])).toContain("archivo");
  });

  it("resume el curso del listado oficial", () => {
    expect(
      describeSource({
        ...base,
        source: { format: "listado_oficial", course: "MED1118 - CLINICA I", section: "Seccion 1", year: "2026", semester: "Semestre 1" },
      }),
    ).toBe("MED1118 - CLINICA I · Seccion 1 · Semestre 1 2026");
    expect(describeSource({ ...base, source: { format: "plantilla" } })).toBe("Plantilla de la plataforma");
    expect(describeSource(base)).toBe("");
  });
});
