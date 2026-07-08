import { describe, expect, it, vi, afterEach } from "vitest";
import { clockOffsetMs, parseServerUtc } from "@/lib/time";

describe("parseServerUtc", () => {
  it("treats a naive backend timestamp (no timezone) as UTC", () => {
    const naive = "2026-07-08T12:00:00";
    const withZ = "2026-07-08T12:00:00Z";
    expect(parseServerUtc(naive)).toBe(parseServerUtc(withZ));
  });

  it("respects an explicit timezone offset if present", () => {
    const utc = parseServerUtc("2026-07-08T12:00:00Z");
    const offset = parseServerUtc("2026-07-08T09:00:00-03:00");
    expect(offset).toBe(utc);
  });

  it("returns NaN for an empty string", () => {
    expect(Number.isNaN(parseServerUtc(""))).toBe(true);
  });
});

describe("clockOffsetMs", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns 0 when the server clock matches the local clock", () => {
    const now = new Date("2026-07-08T12:00:00Z");
    vi.useFakeTimers();
    vi.setSystemTime(now);
    expect(clockOffsetMs(now.toISOString())).toBe(0);
  });

  it("returns a positive offset when the server is ahead of the local clock", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-08T12:00:00Z"));
    const serverNow = "2026-07-08T12:00:30Z"; // 30s ahead
    expect(clockOffsetMs(serverNow)).toBe(30_000);
  });

  it("returns a negative offset when the server is behind the local clock", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-08T12:00:30Z"));
    const serverNow = "2026-07-08T12:00:00Z"; // 30s behind
    expect(clockOffsetMs(serverNow)).toBe(-30_000);
  });

  it("returns 0 for an unparseable server timestamp instead of NaN", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-08T12:00:00Z"));
    expect(clockOffsetMs("")).toBe(0);
  });
});
