import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ECOEProvider, useECOE } from "@/lib/auth";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    me: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    listECOE: vi.fn(),
    ecoe: vi.fn(),
    dashboard: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

function Probe() {
  const { ready, authenticated, user, loadError } = useECOE();
  return (
    <div>
      <span data-testid="ready">{String(ready)}</span>
      <span data-testid="authenticated">{String(authenticated)}</span>
      <span data-testid="user-email">{user?.email ?? ""}</span>
      <span data-testid="load-error">{loadError ?? ""}</span>
    </div>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe("ECOEProvider", () => {
  it("marks the session unauthenticated when /auth/me fails (no session cookie)", async () => {
    mockedApi.me.mockRejectedValue(new Error("401"));

    render(
      <ECOEProvider>
        <Probe />
      </ECOEProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("ready").textContent).toBe("true"));
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(mockedApi.listECOE).not.toHaveBeenCalled();
  });

  it("marks the session authenticated and loads ECOE data when /auth/me succeeds", async () => {
    mockedApi.me.mockResolvedValue({
      id: 1,
      email: "admin@ecoe.cl",
      full_name: "Admin",
      role: "admin_ecoe",
    });
    mockedApi.listECOE.mockResolvedValue([
      { id: 1, name: "ECOE Demo" } as never,
    ]);
    mockedApi.ecoe.mockResolvedValue({ id: 1, name: "ECOE Demo" } as never);
    mockedApi.dashboard.mockResolvedValue({} as never);

    render(
      <ECOEProvider>
        <Probe />
      </ECOEProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("authenticated").textContent).toBe("true"));
    expect(screen.getByTestId("user-email").textContent).toBe("admin@ecoe.cl");
    await waitFor(() => expect(mockedApi.listECOE).toHaveBeenCalled());
  });

  it("surfaces a loadError instead of silently failing when listECOE rejects", async () => {
    mockedApi.me.mockResolvedValue({
      id: 1,
      email: "admin@ecoe.cl",
      full_name: "Admin",
      role: "admin_ecoe",
    });
    mockedApi.listECOE.mockRejectedValue(new Error("network down"));
    mockedApi.ecoe.mockResolvedValue({ id: 1, name: "ECOE Demo" } as never);
    mockedApi.dashboard.mockResolvedValue({} as never);

    render(
      <ECOEProvider>
        <Probe />
      </ECOEProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("load-error").textContent).toContain("network down"),
    );
  });

  it("clears a previous loadError once the retry succeeds", async () => {
    mockedApi.me.mockResolvedValue({
      id: 1,
      email: "admin@ecoe.cl",
      full_name: "Admin",
      role: "admin_ecoe",
    });
    mockedApi.listECOE
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValue([{ id: 1, name: "ECOE Demo" } as never]);
    mockedApi.ecoe.mockResolvedValue({ id: 1, name: "ECOE Demo" } as never);
    mockedApi.dashboard.mockResolvedValue({} as never);

    function RetryProbe() {
      const { loadError, refreshECOE } = useECOE();
      return (
        <div>
          <span data-testid="load-error">{loadError ?? ""}</span>
          <button onClick={() => refreshECOE()}>retry</button>
        </div>
      );
    }

    render(
      <ECOEProvider>
        <RetryProbe />
      </ECOEProvider>,
    );

    await waitFor(() =>
      expect(screen.getByTestId("load-error").textContent).toContain("network down"),
    );

    await act(async () => {
      screen.getByText("retry").click();
    });

    await waitFor(() => expect(screen.getByTestId("load-error").textContent).toBe(""));
  });
});
