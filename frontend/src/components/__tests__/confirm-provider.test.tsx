import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ConfirmProvider, useConfirm } from "@/components/confirm-provider";

function Probe({ onResult }: { onResult: (value: boolean) => void }) {
  const confirm = useConfirm();
  return (
    <button
      onClick={async () =>
        onResult(await confirm("Vas a borrar este registro.", { title: "Borrar", confirmLabel: "Borrar", severity: "danger" }))
      }
    >
      abrir
    </button>
  );
}

describe("ConfirmProvider", () => {
  it("resuelve true al confirmar en el modal propio", async () => {
    const onResult = vi.fn();
    render(<ConfirmProvider><Probe onResult={onResult} /></ConfirmProvider>);
    await userEvent.click(screen.getByText("abrir"));
    expect(screen.getByRole("dialog")).toHaveTextContent("Vas a borrar este registro.");
    await userEvent.click(screen.getByRole("button", { name: "Borrar" }));
    expect(onResult).toHaveBeenCalledWith(true);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("resuelve false al cancelar y no deja el modal abierto", async () => {
    const onResult = vi.fn();
    render(<ConfirmProvider><Probe onResult={onResult} /></ConfirmProvider>);
    await userEvent.click(screen.getByText("abrir"));
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onResult).toHaveBeenCalledWith(false);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("sin provider cae al confirm nativo", async () => {
    const native = vi.spyOn(window, "confirm").mockReturnValue(false);
    const onResult = vi.fn();
    render(<Probe onResult={onResult} />);
    await userEvent.click(screen.getByText("abrir"));
    expect(native).toHaveBeenCalledWith("Vas a borrar este registro.");
    expect(onResult).toHaveBeenCalledWith(false);
    native.mockRestore();
  });
});
