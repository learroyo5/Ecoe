import { describe, it, expect } from "vitest";
import { armAudio, chime } from "@/lib/chime";

// jsdom no implementa AudioContext: el aviso debe degradar en silencio
// sin lanzar, para no romper la vista proyector / el kiosco.
describe("chime", () => {
  it("armAudio no lanza cuando AudioContext no existe", () => {
    expect(() => armAudio()).not.toThrow();
  });

  it("chime('end') y chime('start') no lanzan y son no-op sin audio", () => {
    expect(() => chime("end")).not.toThrow();
    expect(() => chime("start")).not.toThrow();
  });
});
