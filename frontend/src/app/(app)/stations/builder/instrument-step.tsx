"use client";

import {
  BuilderSection,
  FieldBlock,
  fieldConfig,
  instrumentTypeOptions,
  type AssessmentMode,
  type FormKey,
  type InstrumentDraft,
  type InstrumentDraftItem,
  type StationCapabilities,
  type StepScaffoldProps,
  type StudentQuestion,
} from "./shared";

export function InstrumentStep({
  scaffold,
  capabilities,
  templates,
  selectedTemplateId,
  setSelectedTemplateId,
  selectedTemplate,
  assessmentMode,
  setAssessmentMode,
  instrumentMessage,
  setInstrumentMessage,
  selectedAssessmentToolId,
  setSelectedAssessmentToolId,
  instruments,
  instrumentDraft,
  setInstrumentDraft,
  updateInstrumentItem,
  addInstrumentItem,
  removeInstrumentItem,
  saveInstrumentDraft,
  selectedPatientId,
  setSelectedPatientId,
  patients,
  maxScore,
  studentFormPointsTotal,
  updateField,
  onContinue,
  children,
}: {
  scaffold: StepScaffoldProps;
  capabilities: StationCapabilities;
  templates: Record<string, unknown>[] | null;
  selectedTemplateId: string;
  setSelectedTemplateId: (value: string) => void;
  selectedTemplate: Record<string, unknown> | null;
  assessmentMode: AssessmentMode;
  setAssessmentMode: (mode: AssessmentMode) => void;
  instrumentMessage: string | null;
  setInstrumentMessage: (message: string | null) => void;
  selectedAssessmentToolId: string;
  setSelectedAssessmentToolId: (value: string) => void;
  instruments: Record<string, unknown>[] | null;
  instrumentDraft: InstrumentDraft;
  setInstrumentDraft: React.Dispatch<React.SetStateAction<InstrumentDraft>>;
  updateInstrumentItem: (index: number, field: keyof InstrumentDraftItem, value: string) => void;
  addInstrumentItem: () => void;
  removeInstrumentItem: (index: number) => void;
  saveInstrumentDraft: () => Promise<Record<string, unknown>>;
  selectedPatientId: string;
  setSelectedPatientId: (value: string) => void;
  patients: Record<string, unknown>[] | null;
  maxScore: string;
  studentFormPointsTotal: number;
  updateField: (key: FormKey, value: string) => void;
  onContinue: () => void;
  children?: React.ReactNode;
}) {
  return (
    <BuilderSection
      index={2}
      title="Evaluación y puntaje"
      subtitle="Según los switches de arriba: pauta del evaluador, formulario del estudiante, paciente simulado y puntaje total."
      expanded={scaffold.expandedSection === 2}
      completed={scaffold.stepCompleted}
      pendingHint={scaffold.pendingHint}
      onToggle={() => scaffold.openSection(2)}
      sectionRef={scaffold.sectionRef}
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <FieldBlock
          label="Plantilla de referencia"
          description="Opcional: al elegirla, precarga los switches de capacidades con una configuración típica. Después puedes ajustarlos a mano."
        >
          <select
            value={selectedTemplateId}
            onChange={(event) => setSelectedTemplateId(event.target.value)}
          >
            <option value="">Crear sin plantilla</option>
            {(templates ?? []).map((template) => (
              <option key={String(template.id)} value={String(template.id)}>
                {String(template.name)}
              </option>
            ))}
          </select>
          {selectedTemplate ? (
            <p className="text-xs leading-5 text-slate-600">
              Plantilla seleccionada: {String(selectedTemplate.name)} · categoría{" "}
              {String(selectedTemplate.category ?? "sin categoría")}
            </p>
          ) : null}
        </FieldBlock>
        {!capabilities.requiresEvaluator ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm leading-6 text-slate-700">
            Esta estación <strong>no lleva evaluador presencial</strong>, así que no necesita
            pauta de evaluación ni guía del evaluador.
            {capabilities.requiresStudentForm
              ? " El puntaje sale del formulario del estudiante, que se autocorrige con su clave."
              : " Activa el formulario del estudiante si necesitas registrar y puntuar respuestas."}
          </div>
        ) : (
        <FieldBlock
          label="Instrumento de evaluación"
          description="Define aquí mismo la pauta que completará el evaluador o reutiliza una ya creada."
          wide
        >
          <div className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className={assessmentMode === "existing" ? "btn-primary" : "btn-secondary"}
                onClick={() => {
                  setAssessmentMode("existing");
                  setInstrumentMessage(null);
                }}
              >
                Usar pauta existente
              </button>
              <button
                type="button"
                className={assessmentMode === "create" ? "btn-primary" : "btn-secondary"}
                onClick={() => {
                  setAssessmentMode("create");
                  setInstrumentMessage(null);
                }}
              >
                Crear pauta en esta estación
              </button>
            </div>

            {assessmentMode === "existing" ? (
              <div className="space-y-3">
                <p className="text-sm text-slate-600">
                  Elige una pauta ya creada si quieres reutilizarla tal como está.
                </p>
                <select
                  name="assessment_tool_id"
                  value={selectedAssessmentToolId}
                  onChange={(event) => setSelectedAssessmentToolId(event.target.value)}
                >
                  <option value="">Aún sin instrumento asignado</option>
                  {(instruments ?? []).map((instrument) => (
                    <option key={String(instrument.id)} value={String(instrument.id)}>
                      {String(instrument.name)}
                    </option>
                  ))}
                </select>
                <p className="text-xs leading-5 text-slate-500">
                  Las pautas creadas para este ECOE quedan guardadas en el banco de instrumentos
                  y luego puedes reutilizarlas en otras estaciones.
                </p>
                <p className="text-xs leading-5 text-slate-500">
                  Si lo que necesitas es que el estudiante responda preguntas en pantalla, eso
                  no va en esta pauta: activa el switch «Formulario del estudiante» y completa
                  las preguntas más abajo.
                </p>
                {instrumentMessage ? (
                  <p className="text-sm text-[var(--color-primary)]">{instrumentMessage}</p>
                ) : null}
              </div>
            ) : (
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-3 rounded-2xl border border-slate-200 bg-white/80 p-4">
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-slate-800">
                      Construye aquí la pauta exacta que verá el evaluador en esta estación.
                    </p>
                    <p className="text-xs leading-5 text-slate-500">
                      Esta pauta se guardará en el banco de instrumentos para que después puedas
                      reutilizarla o editarla con más calma.
                    </p>
                  </div>
                  <button
                    type="button"
                    className="rounded-full border border-slate-300 px-3 py-1 text-sm font-semibold text-slate-600 transition hover:border-slate-400 hover:text-slate-900"
                    onClick={() => {
                      setAssessmentMode("existing");
                      setInstrumentMessage(null);
                    }}
                    aria-label="Cerrar creación de pauta"
                  >
                    X
                  </button>
                </div>

                <FieldBlock
                  label="Nombre de la pauta"
                  description="Escribe un nombre claro para reconocer esta pauta después."
                >
                  <input
                    value={instrumentDraft.name}
                    placeholder="Ejemplo: Lista de cotejo - dolor torácico"
                    onChange={(event) =>
                      setInstrumentDraft((current) => ({
                        ...current,
                        name: event.target.value,
                      }))
                    }
                  />
                </FieldBlock>

                <FieldBlock
                  label="Tipo de pauta"
                  description="Selecciona la forma en que el evaluador calificará el desempeño."
                >
                  <select
                    value={instrumentDraft.tool_type}
                    onChange={(event) =>
                      setInstrumentDraft((current) => ({
                        ...current,
                        tool_type: event.target.value,
                      }))
                    }
                  >
                    {instrumentTypeOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </FieldBlock>

                <div className="rounded-2xl border border-slate-200 bg-white/80 p-4 text-sm text-slate-700">
                  {
                    instrumentTypeOptions.find(
                      (option) => option.value === instrumentDraft.tool_type,
                    )?.description
                  }
                </div>

                <label className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 cursor-pointer hover:border-slate-300 transition">
                  <input
                    type="checkbox"
                    checked={instrumentDraft.free_observation}
                    onChange={(event) =>
                      setInstrumentDraft((current) => ({
                        ...current,
                        free_observation: event.target.checked,
                      }))
                    }
                    className="size-4 accent-[var(--color-primary)] shrink-0"
                  />
                  <span>Permitir observación libre adicional para el evaluador</span>
                </label>

                <div className="space-y-3">
                  <div>
                    <h5 className="text-sm font-semibold text-slate-800">
                      Criterios o ítems de evaluación
                    </h5>
                    <p className="mt-1 text-xs leading-5 text-slate-500">
                      Agrega aquí los pasos, conductas o criterios que deberá marcar el evaluador.
                    </p>
                  </div>

                  {instrumentDraft.items.map((item, index) => (
                    <div
                      key={`${index}-${instrumentDraft.tool_type}`}
                      className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 lg:grid-cols-[1.4fr_0.5fr_auto]"
                    >
                      <label className="space-y-2">
                        <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Criterio {index + 1}
                        </span>
                        <input
                          value={item.label}
                          placeholder="Ejemplo: Identifica signos de alarma al inicio de la entrevista"
                          onChange={(event) =>
                            updateInstrumentItem(index, "label", event.target.value)
                          }
                        />
                      </label>
                      <label className="space-y-2">
                        <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                          Puntaje
                        </span>
                        <input
                          type="number"
                          min="0.5"
                          step="0.5"
                          value={item.score_per_item}
                          onChange={(event) =>
                            updateInstrumentItem(index, "score_per_item", event.target.value)
                          }
                        />
                      </label>
                      <div className="flex items-end">
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={() => removeInstrumentItem(index)}
                          disabled={instrumentDraft.items.length === 1}
                        >
                          Quitar
                        </button>
                      </div>
                    </div>
                  ))}

                  <button type="button" className="btn-secondary" onClick={addInstrumentItem}>
                    Agregar criterio
                  </button>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    className="btn-primary"
                    onClick={async () => {
                      setInstrumentMessage(null);
                      try {
                        await saveInstrumentDraft();
                      } catch (error) {
                        setInstrumentMessage(
                          error instanceof Error ? error.message : "No se pudo guardar la pauta.",
                        );
                      }
                    }}
                  >
                    Guardar pauta
                  </button>
                  <p className="text-sm text-slate-600">
                    Este paso guarda la pauta y la deja seleccionada para la estación.
                  </p>
                </div>
                {instrumentMessage ? (
                  <p className="text-sm text-slate-700">{instrumentMessage}</p>
                ) : null}
              </div>
            )}
          </div>
        </FieldBlock>
        )}
        {children ? <div className="lg:col-span-2">{children}</div> : null}
        {capabilities.usesSimulatedPatient ? (
          <FieldBlock
            label="Paciente simulado asociado"
            description="Esta estación declara paciente simulado: necesita un personaje asociado."
          >
            <select
              value={selectedPatientId}
              onChange={(event) => setSelectedPatientId(event.target.value)}
            >
              <option value="">Aún sin personaje asociado</option>
              {(patients ?? []).map((patient) => (
                <option key={String(patient.id)} value={String(patient.id)}>
                  {String(patient.character_name)}
                </option>
              ))}
            </select>
          </FieldBlock>
        ) : null}
        <FieldBlock
          label={fieldConfig.max_score.label}
          description={
            assessmentMode === "create" && capabilities.requiresEvaluator
              ? "Este puntaje se calcula automáticamente según la suma de los criterios de la pauta que estás creando."
              : fieldConfig.max_score.description
          }
        >
          <input
            placeholder={fieldConfig.max_score.placeholder}
            value={maxScore}
            onChange={(event) => updateField("max_score", event.target.value)}
            readOnly={assessmentMode === "create" && capabilities.requiresEvaluator}
            className={
              assessmentMode === "create" && capabilities.requiresEvaluator
                ? "bg-slate-100 text-slate-600"
                : ""
            }
          />
          {!capabilities.requiresEvaluator &&
          capabilities.requiresStudentForm &&
          studentFormPointsTotal > 0 &&
          Number(maxScore) !== studentFormPointsTotal ? (
            <button
              type="button"
              className="btn-secondary px-3 py-1.5 text-xs"
              onClick={() => updateField("max_score", String(studentFormPointsTotal))}
            >
              Usar la suma del formulario ({studentFormPointsTotal} pts)
            </button>
          ) : null}
        </FieldBlock>
        <div className="lg:col-span-2 flex justify-end">
          <button
            type="button"
            className="btn-primary animate-pulse-soft"
            onClick={onContinue}
          >
            Continuar a instrucciones
          </button>
        </div>
      </div>
    </BuilderSection>
  );
}

function CorrectAnswerPicker({
  question,
  index,
  onChange,
}: {
  question: StudentQuestion;
  index: number;
  onChange: (index: number, field: keyof StudentQuestion, value: string) => void;
}) {
  const options = question.optionsText
    .split("\n")
    .map((option) => option.trim())
    .filter(Boolean);
  const correct = question.correctText
    .split("\n")
    .map((option) => option.trim())
    .filter(Boolean);

  if (!options.length) {
    return (
      <p className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
        Escribe primero las opciones para poder marcar la clave de respuesta.
      </p>
    );
  }

  if (question.type === "single_choice") {
    return (
      <FieldBlock
        label="Respuesta correcta"
        description="La opción que otorga el puntaje completo; el resto vale 0."
      >
        <select
          value={correct[0] ?? ""}
          onChange={(event) => onChange(index, "correctText", event.target.value)}
        >
          <option value="">Sin clave definida</option>
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </FieldBlock>
    );
  }

  return (
    <FieldBlock
      label="Respuestas correctas"
      description="El puntaje se otorga solo si el estudiante marca exactamente este conjunto."
    >
      <div className="space-y-2">
        {options.map((option) => {
          const checked = correct.includes(option);
          return (
            <label key={option} className="flex items-center gap-2 text-sm text-slate-800">
              <input
                type="checkbox"
                checked={checked}
                onChange={(event) => {
                  const next = event.target.checked
                    ? [...correct, option]
                    : correct.filter((item) => item !== option);
                  onChange(index, "correctText", next.join("\n"));
                }}
              />
              <span>{option}</span>
            </label>
          );
        })}
      </div>
    </FieldBlock>
  );
}


export function StudentFormSection({
  studentQuestions,
  updateStudentQuestion,
  addStudentQuestion,
  removeStudentQuestion,
  isEditing,
  onSaveStudentForm,
}: {
  studentQuestions: StudentQuestion[];
  updateStudentQuestion: (index: number, field: keyof StudentQuestion, value: string) => void;
  addStudentQuestion: () => void;
  removeStudentQuestion: (index: number) => void;
  isEditing: boolean;
  onSaveStudentForm: () => Promise<void>;
}) {
  return (
    <section className="space-y-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
      <div>
        <h4 className="text-base font-semibold text-slate-900">
          Formulario que responderá el estudiante
        </h4>
        <p className="mt-1 text-sm text-slate-600">
          Activado por el switch «Formulario del estudiante». Lo que escribas aquí es
          exactamente lo que verá el estudiante en pantalla: preguntas cortas, claras y sin
          dobles interpretaciones. Con puntaje y clave, se autocorrige.
        </p>
      </div>
      <div className="space-y-4">
        {studentQuestions.map((question, index) => (
          <div
            key={`student-question-${index}`}
            className="grid gap-4 rounded-2xl border border-slate-200 bg-white p-4 lg:grid-cols-[1.4fr_0.7fr_auto]"
          >
            <FieldBlock
              label={`Pregunta ${index + 1}`}
              description="Escribe la pregunta o consigna exacta que debe responder el estudiante."
            >
              <textarea
                rows={3}
                value={question.prompt}
                placeholder="Ejemplo: ¿Cuál es el diagnóstico sindromático más probable en este caso?"
                onChange={(event) =>
                  updateStudentQuestion(index, "prompt", event.target.value)
                }
              />
            </FieldBlock>
            <div className="space-y-4">
              <FieldBlock
                label="Tipo de respuesta"
                description="Selecciona el formato de respuesta que verá el estudiante."
              >
                <select
                  value={question.type}
                  onChange={(event) =>
                    updateStudentQuestion(index, "type", event.target.value)
                  }
                >
                  <option value="single_choice">Selección única</option>
                  <option value="multiple_choice">Selección múltiple</option>
                  <option value="short_text">Respuesta breve</option>
                </select>
              </FieldBlock>
              {question.type !== "short_text" ? (
                <FieldBlock
                  label="Opciones de respuesta"
                  description="Escribe una opción por línea, en el orden en que deberían aparecer."
                >
                  <textarea
                    rows={4}
                    value={question.optionsText}
                    placeholder={"Opción A\nOpción B\nOpción C"}
                    onChange={(event) =>
                      updateStudentQuestion(index, "optionsText", event.target.value)
                    }
                  />
                </FieldBlock>
              ) : null}
              <FieldBlock
                label="Puntaje de la pregunta"
                description={
                  question.type === "short_text"
                    ? "Con puntaje > 0, la respuesta breve pasa a corrección manual y luego suma al consolidado."
                    : "Con puntaje > 0, la pregunta se autocorrige con la clave y suma al consolidado. 0 = solo registro."
                }
              >
                <input
                  type="number"
                  min="0"
                  step="0.5"
                  value={question.points}
                  onChange={(event) =>
                    updateStudentQuestion(index, "points", event.target.value)
                  }
                />
              </FieldBlock>
              {question.type !== "short_text" && Number(question.points) > 0 ? (
                <CorrectAnswerPicker question={question} index={index} onChange={updateStudentQuestion} />
              ) : null}
            </div>
            <div className="flex items-end">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => removeStudentQuestion(index)}
                disabled={studentQuestions.length === 1}
              >
                Quitar pregunta
              </button>
            </div>
          </div>
        ))}
        <div className="flex flex-wrap gap-3">
          <button type="button" className="btn-secondary" onClick={addStudentQuestion}>
            Agregar pregunta
          </button>
          <button
            type="button"
            className="btn-primary"
            disabled={!isEditing}
            onClick={onSaveStudentForm}
          >
            Guardar formulario
          </button>
          <p className="text-sm text-slate-600">
            {isEditing
              ? "Este formulario queda guardado dentro de la estación y se usará después en la interfaz del estudiante."
              : "Guarda primero la estación con el botón principal de abajo. Luego podrás editar el formulario aquí."}
          </p>
        </div>
      </div>
    </section>
  );
}
