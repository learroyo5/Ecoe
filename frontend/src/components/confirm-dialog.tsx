"use client";

import { useEffect, type ReactNode } from "react";

/**
 * Modal de confirmación propio: reemplaza a window.confirm en los flujos
 * operativos. Permite mostrar un resumen de lo que se va a enviar (algo que
 * el confirm nativo no puede) y se ve consistente en tablets.
 */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  severity = "info",
  busy = false,
  onConfirm,
  onCancel,
  children,
}: {
  open: boolean;
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  severity?: "info" | "danger";
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  children?: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={onCancel}
    >
      <div
        className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <h3 className="text-xl font-semibold text-slate-900">{title}</h3>
        {message ? (
          <p className="mt-3 text-sm leading-6 text-slate-600">{message}</p>
        ) : null}
        {children ? <div className="mt-4">{children}</div> : null}
        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <button type="button" className="btn-secondary" onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={
              severity === "danger"
                ? "rounded-full bg-red-600 px-5 py-2 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-60"
                : "btn-primary"
            }
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? "Procesando..." : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * Tono del semáforo de tiempo: verde mientras hay holgura, ámbar bajo el
 * 25% restante, rojo bajo 60 segundos (o expirado).
 */
export function timerTone(remainingSeconds: number | null, totalSeconds: number): "ok" | "warn" | "danger" {
  if (remainingSeconds === null) return "ok";
  if (remainingSeconds <= 60) return "danger";
  if (totalSeconds > 0 && remainingSeconds <= totalSeconds * 0.25) return "warn";
  return "ok";
}

export const TIMER_TONE_CLASSES: Record<ReturnType<typeof timerTone>, string> = {
  ok: "text-slate-900",
  warn: "text-amber-600",
  danger: "text-red-600 animate-pulse",
};
