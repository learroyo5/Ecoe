"use client";

import { useEffect, useState } from "react";

type ToastType = "success" | "error" | "info";

export function Toast({
  message,
  type = "info",
  onDismiss,
  durationMs = 4000,
}: {
  message: string | null;
  type?: ToastType;
  onDismiss: () => void;
  durationMs?: number;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!message) {
      setVisible(false);
      return;
    }
    setVisible(true);
    const timer = setTimeout(() => {
      setVisible(false);
      setTimeout(onDismiss, 300); // wait for fade-out
    }, durationMs);
    return () => clearTimeout(timer);
  }, [message, durationMs, onDismiss]);

  if (!message && !visible) return null;

  const colors = {
    success: "border-green-400 bg-green-50 text-green-800",
    error: "border-red-400 bg-red-50 text-red-800",
    info: "border-[var(--color-primary)] bg-blue-50 text-slate-800",
  };

  const icons = {
    success: "✓",
    error: "✗",
    info: "ℹ",
  };

  return (
    <div
      role="status"
      aria-live="polite"
      className={`animate-fade-in fixed bottom-6 right-6 z-50 max-w-sm rounded-2xl border px-5 py-3 text-sm font-medium shadow-lg ${colors[type]} ${
        visible ? "opacity-100" : "opacity-0 transition-opacity duration-300"
      }`}
    >
      <span className="mr-2 font-bold">{icons[type]}</span>
      {message}
    </div>
  );
}

/** Simple banner for empty states */
export function EmptyState({
  icon = "📋",
  title,
  description,
  action,
}: {
  icon?: string;
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-3xl border-2 border-dashed border-slate-200 bg-white/50 px-6 py-12 text-center">
      <span className="text-4xl">{icon}</span>
      <h3 className="mt-4 text-lg font-semibold text-slate-700">{title}</h3>
      <p className="mt-2 max-w-md text-sm text-slate-500">{description}</p>
      {action ? (
        <button className="btn-primary mt-6" onClick={action.onClick}>
          {action.label}
        </button>
      ) : null}
    </div>
  );
}

/** Error state with retry */
export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-3xl border-2 border-red-200 bg-red-50/50 px-6 py-10 text-center">
      <span className="text-3xl">⚠️</span>
      <h3 className="mt-3 font-semibold text-red-700">Error al cargar</h3>
      <p className="mt-2 max-w-md text-sm text-red-600">{message}</p>
      {onRetry ? (
        <button className="btn-secondary mt-4" onClick={onRetry}>
          Reintentar
        </button>
      ) : null}
    </div>
  );
}
