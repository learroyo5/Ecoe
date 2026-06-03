"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { FileImport, QuickForm, StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";

export default function StudentsPage() {
  const { token, eventId } = useECOE();
  const [page, setPage] = useState(1);
  const { data, loading, error, setData } = useApi(
    () => api.students(eventId, token!) as unknown as Promise<Record<string, unknown>>,
    [eventId, token, page],
  );
  const [message, setMessage] = useState<string | null>(null);
  const [processingAction, setProcessingAction] = useState<string | null>(null);

  const refresh = async () => {
    const result = await api.students(eventId, token!) as unknown as Record<string, unknown>;
    setData(result);
  };

  return (
    <div className="space-y-6">
      <SectionCard title="Gestion de estudiantes" subtitle="Carga masiva por Excel/CSV y alta manual">
        <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <FileImport
            label="Importar estudiantes desde archivo"
            helper={
              <div className="space-y-4">
                <div className="rounded-2xl border border-blue-200 bg-blue-50/60 p-4">
                  <p className="text-sm font-semibold text-blue-900">Como preparar tu archivo</p>
                  <ol className="mt-2 list-inside list-decimal space-y-1 text-xs leading-5 text-blue-800">
                    <li>Descarga la plantilla Excel o CSV usando los botones de abajo.</li>
                    <li>Abre el archivo y completa una fila por cada estudiante.</li>
                    <li>Los unicos campos obligatorios son: <strong>nombre, apellidos, rut, correo</strong>.</li>
                    <li>El <strong>Numero ECOE</strong> se asigna automaticamente; puedes dejarlo vacio.</li>
                    <li>El <strong>correo</strong> es el email del estudiante (no necesita ser un usuario del sistema).</li>
                    <li>Los estudiantes con <strong>RUT duplicado</strong> dentro del mismo ECOE seran omitidos.</li>
                  </ol>
                </div>

                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Columnas del archivo</p>
                  <div className="mt-2 overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-slate-100 text-left text-slate-500">
                          <th className="pb-1 pr-3 font-semibold">Columna</th>
                          <th className="pb-1 pr-3 font-semibold">Obligatorio</th>
                          <th className="pb-1 font-semibold">Descripcion</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50">
                        <tr><td className="py-1 pr-3 font-mono text-slate-700">nombre</td><td className="py-1 pr-3 text-emerald-600">Si</td><td className="py-1 text-slate-500">Nombre del estudiante</td></tr>
                        <tr><td className="py-1 pr-3 font-mono text-slate-700">apellidos</td><td className="py-1 pr-3 text-emerald-600">Si</td><td className="py-1 text-slate-500">Apellidos completos</td></tr>
                        <tr><td className="py-1 pr-3 font-mono text-slate-700">rut</td><td className="py-1 pr-3 text-emerald-600">Si</td><td className="py-1 text-slate-500">RUT con guion y digito verificador (ej: 11111111-1)</td></tr>
                        <tr><td className="py-1 pr-3 font-mono text-slate-700">correo</td><td className="py-1 pr-3 text-emerald-600">Si</td><td className="py-1 text-slate-500">Correo electronico del estudiante</td></tr>
                        <tr><td className="py-1 pr-3 font-mono text-slate-700">numero_ecoe</td><td className="py-1 pr-3 text-slate-400">No</td><td className="py-1 text-slate-500">Se asigna automaticamente de forma correlativa</td></tr>
                        <tr><td className="py-1 pr-3 font-mono text-slate-700">grupo</td><td className="py-1 pr-3 text-slate-400">No</td><td className="py-1 text-slate-500">Nombre del grupo (default: Grupo 1)</td></tr>
                        <tr><td className="py-1 pr-3 font-mono text-slate-700">circuito</td><td className="py-1 pr-3 text-slate-400">No</td><td className="py-1 text-slate-500">Nombre del circuito (default: Circuito A)</td></tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <a
                    href="/plantilla_estudiantes.xlsx"
                    download
                    className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-emerald-700"
                  >
                    <svg className="size-4" viewBox="0 0 20 20" fill="currentColor"><path d="M10 2a1 1 0 011 1v7.586l2.293-2.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L9 10.586V3a1 1 0 011-1z"/><path fillRule="evenodd" d="M3 14a2 2 0 012-2h10a2 2 0 012 2v2a2 2 0 01-2 2H5a2 2 0 01-2-2v-2zm2 0v2h10v-2H5z" clipRule="evenodd"/></svg>
                    Plantilla Excel
                  </a>
                  <a
                    href="/plantilla_estudiantes.csv"
                    download
                    className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
                  >
                    <svg className="size-4" viewBox="0 0 20 20" fill="currentColor"><path d="M10 2a1 1 0 011 1v7.586l2.293-2.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L9 10.586V3a1 1 0 011-1z"/><path fillRule="evenodd" d="M3 14a2 2 0 012-2h10a2 2 0 012 2v2a2 2 0 01-2 2H5a2 2 0 01-2-2v-2zm2 0v2h10v-2H5z" clipRule="evenodd"/></svg>
                    Plantilla CSV
                  </a>
                </div>
              </div>
            }
            onImport={async (file) => {
              const response = (await api.importStudents(eventId, file, token!)) as {
                imported?: number;
                skipped?: number;
                skipped_rut_duplicate?: number;
                skipped_missing_data?: number;
              };
              await refresh();
              const imported = response.imported ?? 0;
              const dupes = response.skipped_rut_duplicate ?? 0;
              const missing = response.skipped_missing_data ?? 0;
              const parts: string[] = [`${imported} estudiantes importados.`];
              if (dupes > 0) parts.push(`${dupes} omitidos por RUT duplicado.`);
              if (missing > 0) parts.push(`${missing} omitidos por falta de datos (rut o correo vacio).`);
              setMessage(parts.join(" "));
              return parts.join(" ");
            }}
          />
          <QuickForm
            fields={[
              { name: "name", label: "Nombre" },
              { name: "last_name", label: "Apellidos" },
              { name: "rut", label: "RUT" },
              { name: "email", label: "Correo", type: "email", description: "Email del estudiante (no requiere cuenta en el sistema)." },
              {
                name: "group_name",
                label: "Grupo",
                description: "El número ECOE se asigna automáticamente en forma correlativa.",
              },
              { name: "circuit_name", label: "Circuito", description: "Ejemplo: Circuito A" },
            ]}
            onSubmit={async (values) => {
              await api.createStudent(
                {
                  ecoe_event_id: eventId,
                  circuit_name: values.circuit_name ?? "Circuito A",
                  ...values,
                },
                token!,
              );
              await refresh();
              setMessage("Estudiante guardado correctamente.");
            }}
          />
        </div>
        <StatusNotice message={message} />
      </SectionCard>
      <SectionCard title="Nomina actual" subtitle="Vista operativa para revisar correlativos, estados y consistencia de la carga estudiantil.">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="btn-secondary"
            onClick={async () => {
              const confirmed = window.confirm(
                "Se reasignara el Numero ECOE de todos los estudiantes en forma correlativa segun el orden de carga. ¿Quieres continuar?",
              );
              if (!confirmed) {
                setMessage("La reasignación de Número ECOE fue cancelada.");
                return;
              }
              setProcessingAction("renumber-students");
              setMessage(null);
              try {
                const response = (await api.renumberStudents(eventId, token!)) as {
                  updated?: number;
                };
                await refresh();
                setMessage(
                  `Renumeración completada: ${response.updated ?? 0} estudiantes quedaron con Número ECOE correlativo.`,
                );
              } catch (actionError) {
                setMessage(
                  actionError instanceof Error
                    ? actionError.message
                    : "No se pudo reasignar el Número ECOE.",
                );
              } finally {
                setProcessingAction(null);
              }
            }}
            disabled={processingAction === "renumber-students"}
          >
            {processingAction === "renumber-students"
              ? "Reasignando..."
              : "Reasignar Número ECOE"}
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={async () => {
              const confirmed = window.confirm(
                "Se revisaran los estudiantes de este ECOE y se borraran los duplicados por RUT, conservando el primer registro cargado. ¿Quieres continuar?",
              );
              if (!confirmed) {
                setMessage("La limpieza de duplicados por RUT fue cancelada.");
                return;
              }
              setProcessingAction("deduplicate-students");
              setMessage(null);
              try {
                const response = (await api.deduplicateStudentsByRut(eventId, token!)) as {
                  removed?: number;
                };
                await refresh();
                setMessage(
                  `Limpieza completada: ${response.removed ?? 0} registros duplicados fueron eliminados.`,
                );
              } catch (actionError) {
                setMessage(
                  actionError instanceof Error
                    ? actionError.message
                    : "No se pudo completar la limpieza de duplicados.",
                );
              } finally {
                setProcessingAction(null);
              }
            }}
            disabled={processingAction === "deduplicate-students"}
          >
            {processingAction === "deduplicate-students"
              ? "Limpiando duplicados..."
              : "Limpiar duplicados por RUT"}
          </button>
          <p className="text-sm text-slate-600">
            El sistema ahora asigna el Numero ECOE en forma correlativa para nuevas cargas y altas manuales.
          </p>
        </div>
        <StatusNotice message={message} />
        {loading ? (
          <p>Cargando estudiantes...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={(data?.items as Record<string, unknown>[]) ?? (Array.isArray(data) ? data as Record<string, unknown>[] : [])}
            searchKeys={["name", "last_name", "rut", "email", "ecoe_number"]}
            paginated={!!data?.items}
            onPageChange={setPage}
            columns={[
              { key: "ecoe_number", label: "N ECOE" },
              { key: "name", label: "Nombre" },
              { key: "last_name", label: "Apellidos" },
              { key: "rut", label: "RUT" },
              { key: "email", label: "Correo" },
              { key: "group_name", label: "Grupo" },
              {
                key: "is_active",
                label: "Estado",
                render: (row) => {
                  const isActive = Boolean((row as { is_active?: boolean }).is_active);
                  return (
                    <span
                      className={`pill ${
                        isActive
                          ? "pill-ok"
                          : "border border-amber-300 bg-[var(--color-warning-soft)] text-amber-900"
                      }`}
                    >
                      {isActive ? "Activo" : "Suspendido"}
                    </span>
                  );
                },
              },
              {
                key: "actions",
                label: "Acciones",
                render: (row) => {
                  const student = row as { id?: number; is_active?: boolean };
                  const isActive = Boolean(student.is_active);
                  return (
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={async () => {
                          const confirmed = window.confirm(
                            isActive
                              ? "Este estudiante cambiara de estado a Suspendido y dejara de contarse como activo. ¿Quieres continuar?"
                              : "Este estudiante volvera a estado Activo. ¿Quieres continuar?",
                          );
                          if (!confirmed) {
                            setMessage("El cambio de estado del estudiante fue cancelado.");
                            return;
                          }
                          setProcessingAction(`status-${String(student.id ?? "")}`);
                          setMessage(null);
                          try {
                            await api.updateStudentStatus(
                              Number(student.id),
                              { is_active: !isActive },
                              token!,
                            );
                            await refresh();
                            setMessage(
                              isActive
                                ? "Estudiante suspendido correctamente."
                                : "Estudiante reactivado correctamente.",
                            );
                          } catch (actionError) {
                            setMessage(
                              actionError instanceof Error
                                ? actionError.message
                                : "No se pudo actualizar el estado del estudiante.",
                            );
                          } finally {
                            setProcessingAction(null);
                          }
                        }}
                        disabled={processingAction === `status-${String(student.id ?? "")}`}
                      >
                        {processingAction === `status-${String(student.id ?? "")}`
                          ? "Guardando..."
                          : isActive
                            ? "Suspender"
                            : "Reactivar"}
                      </button>
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={async () => {
                          const confirmed = window.confirm(
                            "Vas a borrar este estudiante de forma permanente. Esta accion no se puede deshacer. ¿Quieres continuar?",
                          );
                          if (!confirmed) {
                            setMessage("El borrado del estudiante fue cancelado.");
                            return;
                          }
                          setProcessingAction(`delete-${String(student.id ?? "")}`);
                          setMessage(null);
                          try {
                            await api.deleteStudent(Number(student.id), token!);
                            await refresh();
                            setMessage("Estudiante borrado correctamente.");
                          } catch (actionError) {
                            setMessage(
                              actionError instanceof Error
                                ? actionError.message
                                : "No se pudo borrar el estudiante.",
                            );
                          } finally {
                            setProcessingAction(null);
                          }
                        }}
                        disabled={processingAction === `delete-${String(student.id ?? "")}`}
                      >
                        {processingAction === `delete-${String(student.id ?? "")}`
                          ? "Borrando..."
                          : "Borrar"}
                      </button>
                    </div>
                  );
                },
              },
            ]}
          />
        )}
      </SectionCard>
    </div>
  );
}
