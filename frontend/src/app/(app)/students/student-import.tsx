"use client";

import { useRef, useState } from "react";

import { api } from "@/lib/api";
import type { StudentImportPlan, StudentImportRow } from "@/lib/types";

const statusLabels: Record<StudentImportRow["status"], { label: string; className: string }> = {
  nuevo: { label: "Se carga", className: "bg-emerald-100 text-emerald-800" },
  ya_cargado: { label: "Ya está en el ECOE", className: "bg-slate-100 text-slate-600" },
  repetido: { label: "Repetido en el archivo", className: "bg-slate-100 text-slate-600" },
  sin_rut: { label: "Sin RUT", className: "bg-rose-100 text-rose-800" },
  sin_correo: { label: "Correo vacío o inválido", className: "bg-rose-100 text-rose-800" },
  sin_nombre: { label: "Sin nombre", className: "bg-rose-100 text-rose-800" },
};

export function describeDistribution(option: string, circuits: string[]): string {
  if (option === "halves") {
    return `Repartir en partes iguales entre ${circuits.join(" y ")}, según el orden de la lista`;
  }
  if (option === "file") return "Usar el circuito que indica el archivo";
  return `Todos a ${circuits[0] ?? "Circuito A"}`;
}

export function describeSource(plan: StudentImportPlan): string {
  const source = plan.source;
  if (!source) return "";
  const parts = [source.course, source.section, [source.semester, source.year].filter(Boolean).join(" ")]
    .filter(Boolean);
  if (parts.length) return parts.join(" · ");
  return source.format === "listado_oficial" ? "Listado oficial de curso" : "Plantilla de la plataforma";
}

/**
 * Carga de la nómina en dos pasos: el archivo se analiza primero (vista
 * previa, sin guardar) y sólo se carga cuando la persona lo confirma.
 */
export function StudentImport({
  eventId,
  helper,
  onImported,
}: {
  eventId: number;
  helper?: React.ReactNode;
  onImported: (message: string) => Promise<void> | void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [plan, setPlan] = useState<StudentImportPlan | null>(null);
  const [busy, setBusy] = useState<"preview" | "import" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const preview = async (
    target: File,
    options: { distribution?: string; useListNumbers?: boolean } = {},
  ) => {
    setBusy("preview");
    setError(null);
    try {
      setPlan(await api.importStudents(eventId, target, { dryRun: true, ...options }));
    } catch (caught) {
      setPlan(null);
      setFile(null);
      setError(caught instanceof Error ? caught.message : "No se pudo leer el archivo.");
    } finally {
      setBusy(null);
    }
  };

  const reset = () => {
    setFile(null);
    setPlan(null);
    setError(null);
  };

  const confirmImport = async () => {
    if (!file || !plan) return;
    setBusy("import");
    setError(null);
    try {
      const result = await api.importStudents(eventId, file, {
        distribution: plan.distribution,
        useListNumbers: plan.use_list_numbers,
      });
      const parts = [`${result.imported} estudiantes importados.`];
      const circuits = Object.entries(result.per_circuit ?? {});
      if (circuits.length > 1) {
        parts.push(circuits.map(([name, count]) => `${name}: ${count}`).join(" · ") + ".");
      }
      if (result.skipped_rut_duplicate) parts.push(`${result.skipped_rut_duplicate} omitidos porque ya estaban.`);
      if (result.skipped_missing_data) parts.push(`${result.skipped_missing_data} omitidos por datos faltantes.`);
      if (result.with_warnings) parts.push(`${result.with_warnings} con RUT por revisar.`);
      reset();
      await onImported(parts.join(" "));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo importar.");
    } finally {
      setBusy(null);
    }
  };

  const rows = plan?.rows ?? [];
  const toImport = plan?.to_import ?? 0;
  const omitted = (plan?.total_rows ?? 0) - toImport;
  const circuits = plan?.circuits?.length ? plan.circuits : ["Circuito A"];

  return (
    // Con la vista previa abierta ocupa las dos columnas de la grilla: la tabla
    // necesita el ancho y no debe aplastar el formulario de alta manual.
    <div className={`clinical-panel min-w-0 border-dashed ${plan ? "lg:col-span-2" : ""}`}>
      <p className="text-sm font-semibold text-slate-900">Importar estudiantes desde archivo</p>
      {!plan && helper ? <div className="mt-2 text-xs leading-5 text-slate-600">{helper}</div> : null}

      {!plan ? (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="btn-secondary"
            disabled={busy !== null}
            onClick={() => inputRef.current?.click()}
          >
            {busy === "preview" ? "Leyendo el archivo…" : "Elegir archivo Excel o CSV"}
          </button>
          <span className="text-sm text-slate-500">{file?.name ?? "Ningún archivo seleccionado"}</span>
        </div>
      ) : null}
      <input
        ref={inputRef}
        type="file"
        aria-label="Archivo de estudiantes"
        accept=".xlsx,.xls,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        className="sr-only"
        disabled={busy !== null}
        onChange={async (event) => {
          const selected = event.target.files?.[0];
          event.target.value = "";
          if (!selected) return;
          setFile(selected);
          await preview(selected);
        }}
      />

      {plan && file ? (
        <div className="mt-3 space-y-4" role="region" aria-label="Vista previa de la carga">
          <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-950">
            <p className="font-semibold">
              {toImport} {toImport === 1 ? "estudiante se cargará" : "estudiantes se cargarán"}
              {omitted > 0 ? ` · ${omitted} ${omitted === 1 ? "fila se omite" : "filas se omiten"}` : ""}
            </p>
            <p className="mt-1 text-xs text-sky-900">
              {file.name} · {describeSource(plan)}
            </p>
            <p className="mt-1 text-xs text-sky-900">Todavía no se ha guardado nada.</p>
          </div>

          {(plan.distribution_options?.length ?? 0) > 1 ? (
            <fieldset className="space-y-1.5 text-sm">
              <legend className="font-semibold text-slate-800">Circuito de cada estudiante</legend>
              {plan.distribution_options!.map((option) => (
                <label key={option} className="flex items-center gap-2 text-slate-700">
                  <input
                    type="radio"
                    name="student-import-distribution"
                    className="size-4 accent-[var(--color-primary)]"
                    checked={plan.distribution === option}
                    disabled={busy !== null}
                    onChange={() =>
                      preview(file, { distribution: option, useListNumbers: plan.use_list_numbers })
                    }
                  />
                  {describeDistribution(option, circuits)}
                </label>
              ))}
              {Object.keys(plan.per_circuit).length > 1 ? (
                <p className="text-xs text-slate-500">
                  {Object.entries(plan.per_circuit)
                    .map(([name, count]) => `${name}: ${count}`)
                    .join(" · ")}
                </p>
              ) : null}
            </fieldset>
          ) : null}

          {plan.can_use_list_numbers ? (
            <label className="flex items-start gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                className="mt-0.5 size-4 accent-[var(--color-primary)]"
                checked={Boolean(plan.use_list_numbers)}
                disabled={busy !== null}
                onChange={(event) =>
                  preview(file, { distribution: plan.distribution, useListNumbers: event.target.checked })
                }
              />
              <span>
                Usar el correlativo de la lista como Número ECOE
                <span className="block text-xs text-slate-500">
                  El estudiante 7 de la lista oficial será el E007, así la lista impresa sirve el día del examen.
                </span>
              </span>
            </label>
          ) : (plan.existing_students ?? 0) > 0 && toImport > 0 ? (
            <p className="text-xs text-slate-500">
              Este ECOE ya tiene {plan.existing_students} estudiantes: los nuevos continúan la numeración
              existente.
            </p>
          ) : null}

          <div className="max-h-80 overflow-auto rounded-2xl border border-slate-200">
            <table className="w-full min-w-[640px] text-left text-xs">
              <thead className="sticky top-0 bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-3 py-2 font-semibold">N° ECOE</th>
                  <th className="px-3 py-2 font-semibold">Estudiante</th>
                  <th className="px-3 py-2 font-semibold">RUT</th>
                  <th className="px-3 py-2 font-semibold">Matrícula</th>
                  <th className="px-3 py-2 font-semibold">Circuito</th>
                  <th className="px-3 py-2 font-semibold">Resultado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row) => {
                  const status = statusLabels[row.status];
                  const loads = row.status === "nuevo";
                  return (
                    <tr key={row.row} className={loads ? "" : "bg-slate-50/60 text-slate-400"}>
                      <td className="whitespace-nowrap px-3 py-1.5 font-mono">{row.ecoe_number || "—"}</td>
                      <td className="px-3 py-1.5">
                        {[row.last_name, row.name].filter(Boolean).join(", ") || `Fila ${row.row}`}
                        <span className="block text-[11px] text-slate-400">{row.email}</span>
                      </td>
                      <td className="whitespace-nowrap px-3 py-1.5 font-mono">{row.rut || "—"}</td>
                      <td className="px-3 py-1.5 font-mono">{row.registration_number || "—"}</td>
                      <td className="whitespace-nowrap px-3 py-1.5">{loads ? row.circuit_name : "—"}</td>
                      <td className="px-3 py-1.5">
                        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${status.className}`}>
                          {status.label}
                        </span>
                        {row.warnings.map((warning) => (
                          <span key={warning} className="mt-1 block text-[11px] text-amber-700">
                            ⚠ {warning}
                          </span>
                        ))}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              className="btn-primary disabled:opacity-50"
              disabled={busy !== null || toImport === 0}
              onClick={confirmImport}
            >
              {busy === "import"
                ? "Cargando…"
                : toImport === 0
                  ? "Nada que cargar"
                  : `Cargar ${toImport} ${toImport === 1 ? "estudiante" : "estudiantes"}`}
            </button>
            <button type="button" className="btn-secondary" disabled={busy !== null} onClick={reset}>
              Cancelar
            </button>
          </div>
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          {error}
        </p>
      ) : null}
    </div>
  );
}
