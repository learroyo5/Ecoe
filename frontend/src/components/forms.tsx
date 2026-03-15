"use client";

import { useState } from "react";

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
        <label key={field.name} className="space-y-2">
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
      <div className="md:col-span-2">
        <button disabled={saving} className="btn-primary">
          {saving ? "Guardando..." : submitLabel}
        </button>
        {message ? <p className="mt-3 text-sm text-slate-600">{message}</p> : null}
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

  return (
    <div className="rounded-2xl border border-dashed border-slate-300 p-4">
      <p className="text-sm font-semibold">{label}</p>
      {helper ? <div className="mt-2 text-xs leading-5 text-slate-600">{helper}</div> : null}
      <input
        type="file"
        className="mt-3"
        onChange={async (event) => {
          const file = event.target.files?.[0];
          if (!file) return;
          try {
            const result = await onImport(file);
            setMessage(result ?? "Archivo cargado correctamente.");
          } catch (error) {
            setMessage(error instanceof Error ? error.message : "No se pudo importar.");
          }
        }}
      />
      {message ? <p className="mt-3 text-sm text-slate-600">{message}</p> : null}
    </div>
  );
}
