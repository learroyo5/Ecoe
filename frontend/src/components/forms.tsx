"use client";

import { useEffect, useMemo, useState } from "react";

export function getMessageTone(message: string | null) {
  if (!message) {
    return "info" as const;
  }
  if (/guardad|cread|actualizad|cargad|importad|publicad|enviad|verificad|confirmad|borrad/i.test(message)) {
    return "success" as const;
  }
  if (/no se pudo|debes|error|cancelad|bloque/i.test(message)) {
    return "warning" as const;
  }
  return "info" as const;
}

export function StatusNotice({
  message,
  className = "",
}: {
  message: string | null;
  className?: string;
}) {
  if (!message) {
    return null;
  }

  const tone = getMessageTone(message);
  return (
    <div
      role={tone === "warning" ? "alert" : "status"}
      aria-live={tone === "warning" ? "assertive" : "polite"}
      className={`rounded-2xl border px-4 py-4 text-sm font-medium ${
        tone === "success"
          ? "border-emerald-200 bg-emerald-50 text-emerald-900"
          : tone === "warning"
            ? "border-amber-200 bg-amber-50 text-amber-900"
            : "border-sky-200 bg-sky-50 text-sky-900"
      } ${className}`.trim()}
    >
      {message}
    </div>
  );
}

export function QuickForm({
  fields,
  onSubmit,
  submitLabel = "Guardar",
}: {
  fields: Array<{
    name: string;
    label: string;
    type?: string;
    placeholder?: string;
    description?: string;
    multiline?: boolean;
    rows?: number;
  }>;
  onSubmit: (values: Record<string, string>) => Promise<void>;
  submitLabel?: string;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const emptySnapshot = useMemo(
    () => JSON.stringify(Object.fromEntries(fields.map((field) => [field.name, ""]))),
    [fields],
  );
  const currentSnapshot = useMemo(
    () =>
      JSON.stringify(
        Object.fromEntries(fields.map((field) => [field.name, values[field.name] ?? ""])),
      ),
    [fields, values],
  );
  const hasUnsavedChanges = currentSnapshot !== emptySnapshot;
  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsavedChanges || saving) {
        return;
      }
      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedChanges, saving]);

  return (
    <form
      className="grid gap-4 md:grid-cols-2"
      onSubmit={async (event) => {
        event.preventDefault();
        setSaving(true);
        setMessage(null);
        try {
          await onSubmit(values);
          setMessage("Guardado correctamente.");
          setValues({});
        } catch (error) {
          setMessage(error instanceof Error ? error.message : "No se pudo guardar.");
        } finally {
          setSaving(false);
        }
      }}
    >
      {fields.map((field) => (
        <label key={field.name} className="space-y-2 rounded-[22px] border border-slate-200 bg-white/80 p-4">
          <span className="text-sm font-semibold text-slate-700">{field.label}</span>
          {field.description ? <p className="text-xs leading-5 text-slate-500">{field.description}</p> : null}
          {field.multiline ? (
            <textarea
              rows={field.rows ?? 4}
              placeholder={field.placeholder}
              value={values[field.name] ?? ""}
              onChange={(event) =>
                setValues((current) => ({ ...current, [field.name]: event.target.value }))
              }
            />
          ) : (
            <input
              type={field.type ?? "text"}
              placeholder={field.placeholder}
              value={values[field.name] ?? ""}
              onChange={(event) =>
                setValues((current) => ({ ...current, [field.name]: event.target.value }))
              }
            />
          )}
        </label>
      ))}
      <div className="space-y-3 md:col-span-2">
        <div className="flex flex-wrap items-center gap-3">
          <button
            disabled={saving}
            className={`btn-primary transition-all ${
              saving
                ? "cursor-wait opacity-90"
                : hasUnsavedChanges
                  ? "shadow-[0_12px_30px_-18px_rgba(13,148,136,0.75)]"
                  : "border-emerald-600 bg-emerald-600 text-white hover:bg-emerald-700"
            }`}
          >
            {saving ? "Guardando..." : hasUnsavedChanges ? submitLabel : "Cambios guardados"}
          </button>
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              saving
                ? "bg-slate-100 text-slate-600"
                : hasUnsavedChanges
                  ? "bg-amber-100 text-amber-800"
                  : "bg-emerald-100 text-emerald-800"
            }`}
          >
            {saving
              ? "Guardando ahora"
              : hasUnsavedChanges
                ? "Hay cambios pendientes"
                : "Todo guardado"}
          </span>
        </div>
        <StatusNotice message={message} />
      </div>
    </form>
  );
}

export function FileImport({
  onImport,
  label,
  helper,
}: {
  onImport: (file: File) => Promise<string | void>;
  label: string;
  helper?: React.ReactNode;
}) {
  const [message, setMessage] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [lastImportSucceeded, setLastImportSucceeded] = useState(false);

  return (
    <div className="clinical-panel border-dashed">
      <p className="text-sm font-semibold text-slate-900">{label}</p>
      {helper ? <div className="mt-2 text-xs leading-5 text-slate-600">{helper}</div> : null}
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <span
          className={`rounded-full px-3 py-1 text-xs font-semibold ${
            importing
              ? "bg-slate-100 text-slate-600"
              : lastImportSucceeded
                ? "bg-emerald-100 text-emerald-800"
                : "bg-sky-100 text-sky-800"
          }`}
        >
          {importing
            ? "Importando ahora"
            : lastImportSucceeded
              ? "Carga completada"
              : "Esperando archivo"}
        </span>
      </div>
      <input
        type="file"
        className="mt-3"
        disabled={importing}
        onChange={async (event) => {
          const file = event.target.files?.[0];
          if (!file) return;
          setImporting(true);
          setMessage(null);
          try {
            const result = await onImport(file);
            setLastImportSucceeded(true);
            setMessage(result ?? "Archivo cargado correctamente.");
          } catch (error) {
            setLastImportSucceeded(false);
            setMessage(error instanceof Error ? error.message : "No se pudo importar.");
          } finally {
            setImporting(false);
            event.target.value = "";
          }
        }}
      />
      <StatusNotice message={message} className="mt-3" />
    </div>
  );
}
