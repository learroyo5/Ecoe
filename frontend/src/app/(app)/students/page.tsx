"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { useConfirm } from "@/components/confirm-provider";
import { DataTable } from "@/components/data-table";
import { QuickForm, StatusNotice } from "@/components/forms";
import { StudentImport } from "./student-import";
import { StructureLockNotice } from "@/components/structure-lock-notice";
import { SectionCard } from "@/components/section-card";

export default function StudentsPage() {
  const { authenticated, eventId } = useECOE();
  const [page, setPage] = useState(1);
  const { data, loading, error, setData } = useApi(
    () => api.students(eventId, page),
    [eventId, authenticated, page],
  );
  const confirm = useConfirm();
  const [message, setMessage] = useState<string | null>(null);
  const [processingAction, setProcessingAction] = useState<string | null>(null);

  const refresh = async () => {
    const result = await api.students(eventId, page);
    setData(result);
  };
  const totalStudents = data?.total ?? 0;

  return (
    <div className="space-y-6">
      <SectionCard title="Gestión de estudiantes" subtitle="Carga masiva por Excel/CSV y alta manual">
        <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <StudentImport
            eventId={eventId}
            helper={
              <div className="space-y-4">
                <div className="rounded-2xl border border-blue-200 bg-blue-50/60 p-4">
                  <p className="text-sm font-semibold text-blue-900">Qué archivo subir</p>
                  <ul className="mt-2 list-inside list-disc space-y-1 text-xs leading-5 text-blue-800">
                    <li>
                      El <strong>listado oficial de curso</strong> de la universidad, tal como se descarga
                      (Excel con RUT, DV, registro, apellidos, nombres y email). No hay que modificarlo.
                    </li>
                    <li>
                      O la <strong>plantilla</strong> de abajo, con las columnas nombre, apellidos, rut y
                      correo (grupo y circuito son opcionales).
                    </li>
                    <li>
                      Antes de guardar verás una <strong>vista previa</strong>: quiénes se cargan, con qué
                      número y en qué circuito, y qué filas se omiten.
                    </li>
                    <li>Quien ya está en el ECOE (mismo RUT) no se duplica.</li>
                  </ul>
                </div>
                <div className="flex flex-wrap gap-2">
                  <a href="/plantilla_estudiantes.xlsx" download className="btn-secondary px-3 py-2 text-xs">
                    Plantilla Excel
                  </a>
                  <a href="/plantilla_estudiantes.csv" download className="btn-secondary px-3 py-2 text-xs">
                    Plantilla CSV
                  </a>
                </div>
              </div>
            }
            onImported={async (summary) => {
              await refresh();
              setMessage(summary);
            }}
          />
          <QuickForm
            fields={[
              { name: "name", label: "Nombre" },
              { name: "last_name", label: "Apellidos" },
              { name: "rut", label: "RUT" },
              { name: "registration_number", label: "Matrícula", description: "Opcional." },
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
              );
              await refresh();
              setMessage("Estudiante guardado correctamente.");
            }}
          />
        </div>
        <StatusNotice message={message} />
      </SectionCard>
      <StructureLockNotice what="Borrar, depurar y renumerar estudiantes" />
      <SectionCard title="Nómina actual" subtitle={`${totalStudents} estudiantes cargados en este ECOE.`}>
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="btn-secondary"
            onClick={async () => {
              const confirmed = await confirm(
                "Se reasignará el Número ECOE de todos los estudiantes en forma correlativa según el orden de carga. ¿Quieres continuar?",
              );
              if (!confirmed) {
                setMessage("La reasignación de Número ECOE fue cancelada.");
                return;
              }
              setProcessingAction("renumber-students");
              setMessage(null);
              try {
                const response = (await api.renumberStudents(eventId)) as {
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
              const confirmed = await confirm(
                "Se revisarán los estudiantes de este ECOE y se borrarán los duplicados por RUT, conservando el primer registro cargado. ¿Quieres continuar?",
              );
              if (!confirmed) {
                setMessage("La limpieza de duplicados por RUT fue cancelada.");
                return;
              }
              setProcessingAction("deduplicate-students");
              setMessage(null);
              try {
                const response = (await api.deduplicateStudentsByRut(eventId)) as {
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
            El sistema ahora asigna el Número ECOE en forma correlativa para nuevas cargas y altas manuales.
          </p>
        </div>
        <StatusNotice message={message} />
        {loading ? (
          <p>Cargando estudiantes...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={data ?? []}
            searchKeys={["name", "last_name", "rut", "email", "ecoe_number"]}
            paginated={!!data}
            onPageChange={setPage}
            columns={[
              { key: "ecoe_number", label: "N ECOE" },
              { key: "name", label: "Nombre" },
              { key: "last_name", label: "Apellidos" },
              { key: "rut", label: "RUT" },
              { key: "registration_number", label: "Matrícula" },
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
                          const confirmed = await confirm(
                            isActive
                              ? "Este estudiante cambiará de estado a Suspendido y dejará de contarse como activo. ¿Quieres continuar?"
                              : "Este estudiante volverá a estado Activo. ¿Quieres continuar?",
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
                          const confirmed = await confirm(
                            "Vas a borrar este estudiante de forma permanente. Esta acción no se puede deshacer.",
                            { title: "Borrar estudiante", confirmLabel: "Borrar", severity: "danger" },
                          );
                          if (!confirmed) {
                            setMessage("El borrado del estudiante fue cancelado.");
                            return;
                          }
                          setProcessingAction(`delete-${String(student.id ?? "")}`);
                          setMessage(null);
                          try {
                            await api.deleteStudent(Number(student.id));
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
