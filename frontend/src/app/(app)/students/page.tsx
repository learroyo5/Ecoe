"use client";

import Link from "next/link";
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
            label="Importar estudiantes"
            helper={
              <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-3">
                <p>
                  Usa un archivo Excel o CSV con estos encabezados:
                </p>
                <p className="font-semibold text-slate-800">
                  nombre | apellidos | rut | correo | numero_ecoe | grupo | circuito
                </p>
                <p>
                  El orden puede cambiar, pero los nombres de columna deben coincidir.
                </p>
                <p>
                  El correo debe corresponder a una cuenta existente del sistema con rol estudiante.
                </p>
                <Link
                  href="/plantilla_estudiantes.csv"
                  className="inline-block font-semibold text-[var(--color-primary)] underline-offset-4 hover:underline"
                >
                  Descargar plantilla base CSV
                </Link>
              </div>
            }
            onImport={async (file) => {
              const response = (await api.importStudents(eventId, file, token!)) as {
                imported?: number;
                skipped?: number;
              };
              await refresh();
              setMessage(
                `Carga completada: ${response.imported ?? 0} estudiantes importados y ${response.skipped ?? 0} omitidos por RUT duplicado.`,
              );
              return `Carga completada: ${response.imported ?? 0} estudiantes importados y ${response.skipped ?? 0} omitidos por RUT duplicado.`;
            }}
          />
          <QuickForm
            fields={[
              { name: "name", label: "Nombre" },
              { name: "last_name", label: "Apellidos" },
              { name: "rut", label: "RUT" },
              { name: "email", label: "Correo", type: "email" },
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
