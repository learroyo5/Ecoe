"use client";

import { api } from "@/lib/api";
import { MediaPreview } from "@/components/media-preview";
import { BuilderSection, FieldBlock, type StepScaffoldProps } from "./shared";

export function ResourcesStep({
  scaffold,
  usesMultimedia,
  renderTextField,
  isEditing,
  builderScope,
  eventId,
  editingStationId,
  mediaTargetViewer,
  setMediaTargetViewer,
  mediaMessage,
  setMediaMessage,
  mediaAssets,
  setMediaAssets,
}: {
  scaffold: StepScaffoldProps;
  usesMultimedia: boolean;
  renderTextField: (key: "materials" | "multimedia_notes") => React.ReactNode;
  isEditing: boolean;
  builderScope: "bank" | "ecoe";
  eventId: number;
  editingStationId: number;
  mediaTargetViewer: string;
  setMediaTargetViewer: (value: string) => void;
  mediaMessage: string | null;
  setMediaMessage: (message: string | null) => void;
  mediaAssets: Record<string, unknown>[] | null;
  setMediaAssets: React.Dispatch<React.SetStateAction<Record<string, unknown>[] | null>>;
}) {
  return (
    <BuilderSection
      index={4}
      title="Recursos y contingencia"
      subtitle="Cierra aquí todo lo necesario para montar la estación sin incertidumbre el día del ECOE."
      expanded={scaffold.expandedSection === 4}
      completed={scaffold.stepCompleted}
      pendingHint={scaffold.pendingHint}
      onToggle={() => scaffold.openSection(4)}
      sectionRef={scaffold.sectionRef}
    >
      <div className="grid gap-4 lg:grid-cols-2">
        {renderTextField("materials")}
        {usesMultimedia ? renderTextField("multimedia_notes") : null}
      </div>
      <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
        <div>
          <h5 className="text-base font-semibold text-slate-900">
            Archivos multimedia de la estación
          </h5>
          {usesMultimedia ? (
            <p className="mt-1 text-sm text-slate-600">
              Esta estación <strong>declara uso de multimedia</strong>: necesita al menos un
              archivo cargado (imagen, audio, video o PDF) para quedar lista. Si aún no has
              guardado la estación, guárdala primero y vuelve a abrirla para adjuntar.
            </p>
          ) : (
            <p className="mt-1 text-sm text-slate-600">
              Esta estación no declara multimedia. Puedes cargar archivos igualmente como apoyo,
              o activar el switch «Multimedia» si el recurso es parte esencial de la estación.
            </p>
          )}
        </div>

        {isEditing && builderScope === "ecoe" ? (
          <div className="mt-4 space-y-4">
            <div className="grid gap-4 md:grid-cols-[0.7fr_1.3fr]">
              <FieldBlock
                label="Visible para"
                description="Indica a quién se le mostrará este recurso dentro del flujo."
              >
                <select
                  value={mediaTargetViewer}
                  onChange={(event) => setMediaTargetViewer(event.target.value)}
                >
                  <option value="estudiante">Estudiante</option>
                  <option value="evaluador">Evaluador</option>
                  <option value="paciente_simulado">Paciente simulado</option>
                  <option value="coordinacion">Coordinación</option>
                </select>
              </FieldBlock>
              <FieldBlock
                label="Cargar archivo"
                description="Formatos sugeridos: audio, video, PDF, imágenes y documentos .doc o .docx."
              >
                <input
                  type="file"
                  accept="audio/*,video/*,.pdf,image/*,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={async (event) => {
                    const file = event.target.files?.[0];
                    if (!file) {
                      return;
                    }
                    setMediaMessage(null);
                    try {
                      const uploaded = (await api.uploadMedia(
                        {
                          ecoe_event_id: eventId,
                          station_id: editingStationId,
                          target_viewer: mediaTargetViewer,
                          file,
                        },
                      )) as Record<string, unknown>;
                      setMediaAssets((current) => [...(current ?? []), uploaded]);
                      setMediaMessage("Archivo multimedia cargado correctamente.");
                      event.currentTarget.value = "";
                    } catch (error) {
                      setMediaMessage(
                        error instanceof Error ? error.message : "No se pudo cargar el archivo.",
                      );
                    }
                  }}
                />
              </FieldBlock>
            </div>

            <div className="space-y-3">
              {(mediaAssets ?? []).length ? (
                (mediaAssets ?? []).map((asset) => (
                  <div
                    key={String(asset.id)}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm"
                  >
                    <div>
                      <p className="font-semibold text-slate-900">
                        {String(asset.original_name ?? asset.filename ?? "Archivo")}
                      </p>
                      <p className="text-slate-500">
                        {String(asset.content_type ?? "tipo no informado")} · visible para{" "}
                        {String(asset.target_viewer ?? "sin definir")}
                      </p>
                      <div className="mt-2 max-w-xs">
                        <MediaPreview
                          asset={asset as unknown as import("@/lib/types").MediaAsset}
                        />
                      </div>
                    </div>
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={async () => {
                        const confirmed = window.confirm(
                          "Vas a borrar este archivo multimedia de la estación. ¿Quieres continuar?",
                        );
                        if (!confirmed) {
                          return;
                        }
                        setMediaMessage(null);
                        try {
                          await api.deleteMedia(Number(asset.id));
                          setMediaAssets((current) =>
                            (current ?? []).filter(
                              (currentAsset) => Number(currentAsset.id) !== Number(asset.id),
                            ),
                          );
                          setMediaMessage("Archivo multimedia borrado correctamente.");
                        } catch (error) {
                          setMediaMessage(
                            error instanceof Error
                              ? error.message
                              : "No se pudo borrar el archivo.",
                          );
                        }
                      }}
                    >
                      Borrar
                    </button>
                  </div>
                ))
              ) : (
                <p className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
                  Aún no hay archivos multimedia cargados para esta estación.
                </p>
              )}
            </div>

            {mediaMessage ? <p className="text-sm text-slate-700">{mediaMessage}</p> : null}
          </div>
        ) : (
          <p className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            {builderScope === "bank"
              ? "La carga multimedia sigue asociada a estaciones del ECOE. En el banco, deja aquí las indicaciones y define después los archivos concretos en la estación operativa."
              : "Guarda primero la estación y luego vuelve a abrirla para cargar archivos multimedia."}
          </p>
        )}
      </div>
    </BuilderSection>
  );
}
