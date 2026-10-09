"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";

import { ConfirmDialog } from "@/components/confirm-dialog";

export type ConfirmOptions = {
  title?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  severity?: "info" | "danger";
};

type ConfirmFn = (message: string, options?: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = createContext<ConfirmFn | null>(null);

/**
 * Confirmación imperativa con el modal propio: `if (!(await confirm("…"))) return;`.
 * Reemplaza a window.confirm en los handlers async de las pantallas de gestión,
 * sin obligar a cada una a mantener su propio estado de diálogo.
 */
export function ConfirmProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<{ message: string; options: ConfirmOptions } | null>(null);
  const resolverRef = useRef<((value: boolean) => void) | null>(null);

  const settle = useCallback((value: boolean) => {
    resolverRef.current?.(value);
    resolverRef.current = null;
    setPending(null);
  }, []);

  const confirm = useCallback<ConfirmFn>((message, options = {}) => {
    // Un diálogo a la vez: si quedaba uno abierto se resuelve como cancelado.
    resolverRef.current?.(false);
    return new Promise<boolean>((resolve) => {
      resolverRef.current = resolve;
      setPending({ message, options });
    });
  }, []);

  const handleCancel = useCallback(() => settle(false), [settle]);
  const handleConfirm = useCallback(() => settle(true), [settle]);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <ConfirmDialog
        open={pending !== null}
        title={pending?.options.title ?? "Confirmar acción"}
        message={pending?.message}
        confirmLabel={pending?.options.confirmLabel ?? "Continuar"}
        cancelLabel={pending?.options.cancelLabel}
        severity={pending?.options.severity}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    </ConfirmContext.Provider>
  );
}

// Sin provider (tests unitarios que montan la página suelta) cae al confirm
// nativo, así el comportamiento sigue siendo bloqueante y mockeable.
const nativeConfirm: ConfirmFn = (message) =>
  Promise.resolve(typeof window === "undefined" ? false : window.confirm(message));

export function useConfirm(): ConfirmFn {
  return useContext(ConfirmContext) ?? nativeConfirm;
}
