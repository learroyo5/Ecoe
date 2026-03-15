"use client";

import Link from "next/link";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { FileImport, QuickForm } from "@/components/forms";
import { SectionCard } from "@/components/section-card";

export default function StudentsPage() {
  const { token, eventId } = useAuth();
  const { data, loading, error, setData } = useApi(
    () => api.students(eventId, token!) as Promise<Record<string, unknown>[]>,
    [eventId, token],
  );

  const refresh = async () => setData((await api.students(eventId, token!)) as Record<string, unknown>[]);

  return (
    <div className="space-y-6">
      <SectionCard title="Gestion de estudiantes" subtitle="Carga masiva por Excel/CSV y alta manual">
        <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <FileImport
            label="Importar estudiantes"
            helper={
              <div className="space-y-3 rounded-2xl bg-slate-50 p-3">
                <p>
                  Usa un archivo Excel o CSV con estos encabezados:
                </p>
                <p className="font-semibold text-slate-800">
                  nombre | apellidos | rut | correo | numero_ecoe | grupo | circuito
                </p>
                <p>
                  El orden puede cambiar, pero los nombres de columna deben coincidir.
                </p>
                <Link
                  href="/plantilla_estudiantes.csv"
                  className="inline-block font-semibold text-teal-700 underline-offset-4 hover:underline"
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
                label: "Grupo/circuito",
                description: "El numero ECOE se asigna automaticamente en forma correlativa.",
              },
            ]}
            onSubmit={async (values) => {
              await api.createStudent(
                {
                  ecoe_event_id: eventId,
                  circuit_name: values.group_name ?? "Circuito A",
                  ...values,
                },
                token!,
              );
              await refresh();
            }}
          />
        </div>
      </SectionCard>
      <SectionCard title="Nomina actual">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="btn-secondary"
            onClick={async () => {
              const confirmed = window.confirm(
                "Se reasignara el Numero ECOE de todos los estudiantes en forma correlativa segun el orden de carga. ¿Quieres continuar?",
              );
              if (!confirmed) {
                return;
              }
              const response = (await api.renumberStudents(eventId, token!)) as {
                updated?: number;
              };
              await refresh();
              window.alert(
                `Renumeracion completada: ${response.updated ?? 0} estudiantes quedaron con Numero ECOE correlativo.`,
              );
            }}
          >
            Reasignar Numero ECOE
          </button>
          <button
            type="button"
            className="btn-secondary"
            onClick={async () => {
              const confirmed = window.confirm(
                "Se revisaran los estudiantes de este ECOE y se borraran los duplicados por RUT, conservando el primer registro cargado. ¿Quieres continuar?",
              );
              if (!confirmed) {
                return;
              }
              const response = (await api.deduplicateStudentsByRut(eventId, token!)) as {
                removed?: number;
              };
              await refresh();
              window.alert(
                `Limpieza completada: ${response.removed ?? 0} registros duplicados fueron eliminados.`,
              );
            }}
          >
            Limpiar duplicados por RUT
          </button>
          <p className="text-sm text-slate-600">
            El sistema ahora asigna el Numero ECOE en forma correlativa para nuevas cargas y altas manuales.
          </p>
        </div>
        {loading ? (
          <p>Cargando estudiantes...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={data ?? []}
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
                          : "border border-amber-300 bg-amber-100 text-amber-900"
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
                            return;
                          }
                          await api.updateStudentStatus(
                            Number(student.id),
                            { is_active: !isActive },
                            token!,
                          );
                          await refresh();
                        }}
                      >
                        {isActive ? "Suspender" : "Reactivar"}
                      </button>
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={async () => {
                          const confirmed = window.confirm(
                            "Vas a borrar este estudiante de forma permanente. Esta accion no se puede deshacer. ¿Quieres continuar?",
                          );
                          if (!confirmed) {
                            return;
                          }
                          await api.deleteStudent(Number(student.id), token!);
                          await refresh();
                        }}
                      >
                        Borrar
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
