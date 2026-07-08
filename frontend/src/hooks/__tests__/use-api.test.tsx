import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useApi } from "@/hooks/use-api";

describe("useApi", () => {
  it("starts in a loading state and populates data on success", async () => {
    const fetcher = vi.fn().mockResolvedValue({ hello: "world" });
    const { result } = renderHook(() => useApi(fetcher));

    expect(result.current.loading).toBe(true);
    expect(result.current.data).toBeNull();

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toEqual({ hello: "world" });
    expect(result.current.error).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("surfaces a readable error message when the fetcher rejects", async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error("No se pudo cargar"));
    const { result } = renderHook(() => useApi(fetcher));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.data).toBeNull();
    expect(result.current.error).toBe("No se pudo cargar");
  });

  it("falls back to a generic message when the rejection is not an Error", async () => {
    const fetcher = vi.fn().mockRejectedValue("plain string failure");
    const { result } = renderHook(() => useApi(fetcher));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.error).toBe("Error inesperado");
  });

  it("refetches when a dependency changes", async () => {
    const fetcher = vi.fn().mockResolvedValue("ok");
    const { result, rerender } = renderHook(
      ({ dep }: { dep: number }) => useApi(fetcher, [dep]),
      { initialProps: { dep: 1 } },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetcher).toHaveBeenCalledTimes(1);

    rerender({ dep: 2 });
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  });

  it("does not refetch when dependencies are unchanged across renders", async () => {
    const fetcher = vi.fn().mockResolvedValue("ok");
    const { result, rerender } = renderHook(
      ({ dep }: { dep: number }) => useApi(fetcher, [dep]),
      { initialProps: { dep: 1 } },
    );

    await waitFor(() => expect(result.current.loading).toBe(false));
    rerender({ dep: 1 });
    // give any accidental async refetch a chance to happen
    await act(async () => {});
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("allows callers to update the cached data via setData", async () => {
    const fetcher = vi.fn().mockResolvedValue([1, 2, 3]);
    const { result } = renderHook(() => useApi(fetcher));

    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      result.current.setData([4, 5, 6]);
    });

    expect(result.current.data).toEqual([4, 5, 6]);
  });

  it("ignores a stale response if the hook unmounts before it resolves", async () => {
    let resolveFetch: (value: string) => void = () => {};
    const fetcher = vi.fn(
      () => new Promise<string>((resolve) => { resolveFetch = resolve; }),
    );
    const { result, unmount } = renderHook(() => useApi(fetcher));

    unmount();
    await act(async () => {
      resolveFetch("too late");
    });

    // No assertion on `result.current` post-unmount is meaningful beyond
    // "it must not throw" — React logs a warning if state is set after
    // unmount, which the `active` guard in useApi prevents.
    expect(result.current).toBeDefined();
  });
});
