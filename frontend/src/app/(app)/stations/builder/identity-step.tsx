"use client";

import Link from "next/link";

import {
  BuilderSection,
  FieldBlock,
  builderOriginOptions,
  circuitOptions,
  fieldConfig,
  stationTypeOptions,
  type FormKey,
  type StepScaffoldProps,
} from "./shared";

export function StationIdentityStep({
  scaffold,
  builderScope,
  isUsingBankStation,
  confirmDiscardChanges,
  isEditing,
  form,
  nextStationNumber,
  bankStatus,
  setBankStatus,
  bankStatusOptions,
  updateField,
  renderTextField,
  onContinue,
}: {
  scaffold: StepScaffoldProps;
  builderScope: "bank" | "ecoe";
  isUsingBankStation: boolean;
  confirmDiscardChanges: () => boolean;
  isEditing: boolean;
  form: { station_number: string; station_type: string; circuit_name: string };
  nextStationNumber: string;
  bankStatus: string;
  setBankStatus: (value: string) => void;
  bankStatusOptions: { value: string; label: string }[];
  updateField: (key: FormKey, value: string) => void;
  renderTextField: (key: FormKey) => React.ReactNode;
  onContinue: () => void;
}) {
  return (
    <BuilderSection
      index={1}
      title="Origen y base de la estación"
      subtitle="Primero define desde dónde nace esta estación y luego completa su identidad pedagógica central."
      expanded={scaffold.expandedSection === 1}
      completed={scaffold.stepCompleted}
      onToggle={() => scaffold.openSection(1)}
      sectionRef={scaffold.sectionRef}
    >
      <div className="mb-5 space-y-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
        <div>
          <p className="text-sm font-semibold text-slate-900">Origen de la estación</p>
          <p className="mt-1 text-xs leading-5 text-slate-600">
            Esta decisión ordena el resto del trabajo. Elige desde dónde quieres construir.
          </p>
        </div>
        <div className="grid gap-3 lg:grid-cols-3">
          {builderOriginOptions.map((option) => {
            const isActive =
              (option.href === "/stations/builder" && builderScope === "ecoe" && !isUsingBankStation) ||
              (option.href === "/station-bank" && isUsingBankStation) ||
              (option.href.includes("scope=bank") && builderScope === "bank");

            return (
              <Link
                key={option.label}
                href={option.href}
                onClick={(event) => {
                  if (confirmDiscardChanges()) {
                    return;
                  }
                  event.preventDefault();
                }}
                className={`rounded-2xl border px-4 py-4 transition ${
                  isActive
                    ? "border-teal-600 bg-white text-slate-900"
                    : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                }`}
              >
                <p className="text-sm font-semibold">{option.label}</p>
                <p className="mt-2 text-xs leading-5 text-slate-600">{option.description}</p>
              </Link>
            );
          })}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {builderScope === "ecoe" ? (
          <FieldBlock
            label={fieldConfig.station_number.label}
            description={fieldConfig.station_number.description}
          >
            <input
              value={isEditing ? form.station_number : nextStationNumber}
              readOnly
              className="bg-slate-100 text-slate-600"
            />
          </FieldBlock>
        ) : (
          <FieldBlock
            label="Estado de la estación en el banco"
            description="Indica si esta estación aún está en diseño, si ya fue piloteada o si ya está aprobada para reutilización."
          >
            <select
              value={bankStatus}
              onChange={(event) => setBankStatus(event.target.value)}
            >
              {bankStatusOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </FieldBlock>
        )}
        {renderTextField("name")}
        <FieldBlock
          label={fieldConfig.station_type.label}
          description={fieldConfig.station_type.description}
          wide
        >
          <div className="grid items-stretch gap-3 md:grid-cols-3">
            {stationTypeOptions.map((option) => {
              const checked = form.station_type === option.value;
              return (
                <label
                  key={option.value}
                  className={`flex w-full min-w-0 cursor-pointer items-center gap-3 rounded-2xl border px-4 py-4 transition ${
                    checked
                      ? "border-[var(--color-primary)] bg-[var(--color-bg-soft)] shadow-sm"
                      : "border-slate-200 bg-white hover:border-slate-300"
                  }`}
                >
                  <span
                    className={`flex size-5 shrink-0 items-center justify-center rounded-full border-2 transition ${
                      checked
                        ? "border-[var(--color-primary)] bg-[var(--color-primary)]"
                        : "border-slate-300"
                    }`}
                  >
                    {checked ? (
                      <span className="size-2 rounded-full bg-white" />
                    ) : null}
                  </span>
                  <span className="min-w-0 break-words text-sm font-semibold text-slate-800">
                    {option.label}
                  </span>
                  <input
                    type="radio"
                    name="station_type"
                    value={option.value}
                    checked={checked}
                    onChange={(event) => updateField("station_type", event.target.value)}
                    className="sr-only"
                  />
                </label>
              );
            })}
          </div>
        </FieldBlock>
        {builderScope === "ecoe" ? (
          <FieldBlock
            label={fieldConfig.circuit_name.label}
            description={fieldConfig.circuit_name.description}
          >
            <select
              value={form.circuit_name}
              onChange={(event) => updateField("circuit_name", event.target.value)}
            >
              {circuitOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </FieldBlock>
        ) : (
          <FieldBlock
            label="Circuito sugerido"
            description="Puedes dejar un circuito de referencia, aunque después el ECOE concreto lo cambie."
          >
            <select
              value={form.circuit_name}
              onChange={(event) => updateField("circuit_name", event.target.value)}
            >
              {circuitOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </FieldBlock>
        )}
        {renderTextField("expected_outcomes")}
        {renderTextField("student_activity")}
        <div className="lg:col-span-2 flex justify-end">
          <button
            type="button"
            className="btn-primary animate-pulse-soft"
            onClick={onContinue}
          >
            Continuar a configuración
          </button>
        </div>
      </div>
    </BuilderSection>
  );
}
