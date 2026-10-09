import { afterEach, describe, expect, it, vi } from "vitest";

import { nextDraftSeq } from "@/lib/draft-seq";

afterEach(() => vi.useRealTimers());

describe("nextDraftSeq", () => {
  it("es estrictamente creciente aunque se pida varias veces en el mismo milisegundo", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-23T12:00:00Z"));
    const a = nextDraftSeq();
    const b = nextDraftSeq();
    const c = nextDraftSeq();
    expect(b).toBeGreaterThan(a);
    expect(c).toBeGreaterThan(b);
  });

  it("no retrocede si el reloj del dispositivo se atrasa", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-23T12:00:00Z"));
    const before = nextDraftSeq();
    vi.setSystemTime(new Date("2026-11-23T11:00:00Z"));
    expect(nextDraftSeq()).toBeGreaterThan(before);
  });
});
