import { describe, expect, it } from "vitest";

import {
  canAccessStationArea,
  canDuplicateEcoe,
  canEditStations,
} from "@/lib/permissions";

describe("canDuplicateEcoe", () => {
  it("permite a admin_global aunque no tenga rol de evento", () => {
    expect(canDuplicateEcoe("admin_global", [])).toBe(true);
  });

  it("permite a admin_ecoe delegado por evento", () => {
    expect(canDuplicateEcoe("evaluador", ["admin_ecoe"])).toBe(true);
  });

  it("no permite a coeditor_docente ni a roles operativos", () => {
    expect(canDuplicateEcoe("coeditor_docente", ["coeditor_docente"])).toBe(false);
    expect(canDuplicateEcoe("evaluador", ["evaluador"])).toBe(false);
    expect(canDuplicateEcoe(undefined, [])).toBe(false);
  });
});

describe("canEditStations", () => {
  it("permite a admin_global", () => {
    expect(canEditStations("admin_global", [])).toBe(true);
  });

  it("permite a una cuenta cuyo rol global es evaluador pero es coeditor_docente en el evento", () => {
    expect(canEditStations("evaluador", ["coeditor_docente"])).toBe(true);
    expect(canEditStations("evaluador", ["admin_ecoe"])).toBe(true);
  });

  it("no permite a coordinador_operativo (solo lectura del área)", () => {
    expect(canEditStations("coordinador_operativo", ["coordinador_operativo"])).toBe(false);
  });

  it("no permite a un evaluador sin rol de edición en el evento", () => {
    expect(canEditStations("evaluador", ["evaluador"])).toBe(false);
  });
});

describe("canAccessStationArea", () => {
  it("permite a los tres roles administrativos de evento y a admin_global", () => {
    expect(canAccessStationArea("admin_global", [])).toBe(true);
    expect(canAccessStationArea("evaluador", ["admin_ecoe"])).toBe(true);
    expect(canAccessStationArea("evaluador", ["coeditor_docente"])).toBe(true);
    expect(canAccessStationArea("evaluador", ["coordinador_operativo"])).toBe(true);
  });

  it("no permite a un evaluador puro", () => {
    expect(canAccessStationArea("evaluador", ["evaluador"])).toBe(false);
    expect(canAccessStationArea(null, [])).toBe(false);
  });
});
