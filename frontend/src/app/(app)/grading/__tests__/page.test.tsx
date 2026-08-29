import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import GradingPage from "@/app/(app)/grading/page";
import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";

vi.mock("@/lib/auth", () => ({
  useECOE: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    gradingList: vi.fn(),
    gradeResponse: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);
const mockedUseECOE = vi.mocked(useECOE);

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.gradingList.mockResolvedValue({ responses: [], pending_count: 0 } as never);
});

describe("GradingPage — gate de ECOE cerrado (OPT-1)", () => {
  it("oculta el formulario y muestra el aviso cuando el evento está cerrado", async () => {
    mockedUseECOE.mockReturnValue({
      authenticated: true,
      eventId: 1,
      ecoeEvent: { id: 1, status: "cerrado" },
    } as never);

    render(<GradingPage />);

    const notice = await screen.findByTestId("grading-closed-notice");
    expect(notice.textContent).toContain("ECOE cerrado");
    expect(screen.queryByText(/Pendientes de corrección/)).not.toBeInTheDocument();
    expect(mockedApi.gradingList).not.toHaveBeenCalled();
  });

  it("también bloquea la corrección cuando el evento está archivado", async () => {
    mockedUseECOE.mockReturnValue({
      authenticated: true,
      eventId: 1,
      ecoeEvent: { id: 1, status: "archivado" },
    } as never);

    render(<GradingPage />);

    expect(await screen.findByTestId("grading-closed-notice")).toBeInTheDocument();
  });

  it("muestra la cola de corrección normal cuando el evento está en ejecución", async () => {
    mockedUseECOE.mockReturnValue({
      authenticated: true,
      eventId: 1,
      ecoeEvent: { id: 1, status: "en_ejecucion" },
    } as never);

    render(<GradingPage />);

    await waitFor(() => expect(mockedApi.gradingList).toHaveBeenCalled());
    expect(screen.queryByTestId("grading-closed-notice")).not.toBeInTheDocument();
  });
});
