"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useECOE } from "@/lib/auth";

const items = [
  { label: "Dashboard", href: "/dashboard", hiddenFor: ["evaluador", "estudiante"] },
  { label: "ECOE", href: "/ecoe", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Usuarios", href: "/users", hiddenFor: ["coeditor_docente", "coordinador_operativo", "evaluador", "estudiante", "cronometrador"] },
  { label: "Estudiantes", href: "/students", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Evaluadores", href: "/evaluators", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Estaciones", href: "/stations", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Banco de estaciones", href: "/station-bank", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Constructor", href: "/stations/builder", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Plantillas", href: "/templates", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Instrumentos", href: "/instruments", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Paciente simulado", href: "/simulated-patient", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Validacion", href: "/validation", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Pilotaje", href: "/pilotage", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Publicacion", href: "/publication", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Panel en vivo", href: "/live", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Evaluador", href: "/evaluator", hiddenFor: ["admin_ecoe", "coeditor_docente", "coordinador_operativo", "cronometrador", "estudiante"] },
  { label: "Estudiante", href: "/student", hiddenFor: ["admin_ecoe", "coeditor_docente", "coordinador_operativo", "cronometrador", "evaluador"] },
  { label: "Resultados", href: "/results", hiddenFor: ["evaluador", "estudiante"] },
];

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { user } = useECOE();
  const visibleItems = items.filter((item) => !item.hiddenFor?.includes(user?.role ?? ""));

  return (
    <aside className="panel-card h-full lg:h-fit lg:sticky lg:top-4 overflow-y-auto">
      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--color-primary)]">
        DRNOTUS · ECOE
      </p>
      <h1 className="mt-3 text-2xl text-[var(--color-primary-dark)]">Proyecto ECOE Digital</h1>
      <p className="mt-2 text-sm leading-6 text-slate-600">
        Plataforma academica para planificar, pilotar y ejecutar evaluacion clinica estructurada.
      </p>
      <nav className="mt-6 space-y-2">
        {visibleItems.map(({ label, href }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              onClick={onNavigate}
              className={`block rounded-2xl px-4 py-3 text-sm transition ${
                active
                  ? "bg-[linear-gradient(135deg,var(--color-primary),var(--color-primary-dark))] font-semibold text-white shadow-sm"
                  : "bg-white/70 text-slate-700 hover:bg-[var(--color-bg-soft)]"
              }`}
            >
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
