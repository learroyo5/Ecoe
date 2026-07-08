"use client";

import { BuilderSection, type StepScaffoldProps } from "./shared";

export function InstructionsStep({
  scaffold,
  renderTextField,
  onContinue,
}: {
  scaffold: StepScaffoldProps;
  renderTextField: (key: "pre_entry_instruction" | "student_station_instruction" | "evaluator_instruction") => React.ReactNode;
  onContinue: () => void;
}) {
  return (
    <BuilderSection
      index={3}
      title="Instrucciones operativas"
      subtitle="Define lo que guiará al estudiante y al evaluador durante la ejecución real, sin mezclarlo con configuraciones generales del ECOE."
      expanded={scaffold.expandedSection === 3}
      completed={scaffold.stepCompleted}
      onToggle={() => scaffold.openSection(3)}
      sectionRef={scaffold.sectionRef}
    >
      <div className="grid gap-4 lg:grid-cols-2">
        {renderTextField("pre_entry_instruction")}
        {renderTextField("student_station_instruction")}
        <div className="lg:col-span-2">{renderTextField("evaluator_instruction")}</div>
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-700 lg:col-span-2">
          Regla práctica:
          {` `}
          `Instrucción previa de ingreso` es lo que orienta antes de entrar;
          {` `}
          `Instrucciones dentro de la estación` es la orden operativa principal del estudiante;
          {` `}
          `Guía para el evaluador` es lo que ordena la observación y el registro.
        </div>
        <div className="lg:col-span-2 flex justify-end">
          <button
            type="button"
            className="btn-primary animate-pulse-soft"
            onClick={onContinue}
          >
            Continuar a recursos
          </button>
        </div>
      </div>
    </BuilderSection>
  );
}
