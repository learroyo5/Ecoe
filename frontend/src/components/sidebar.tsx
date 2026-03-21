"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth";

const items = [
  { label: "Dashboard", href: "/dashboard" },
  { label: "Estudiantes", href: "/students", hiddenFor: ["evaluador"] },
  { label: "Evaluadores", href: "/evaluators", hiddenFor: ["evaluador"] },
  { label: "Estaciones", href: "/stations", hiddenFor: ["evaluador"] },
  { label: "Banco de estaciones", href: "/station-bank", hiddenFor: ["evaluador"] },
  { label: "Constructor", href: "/stations/builder", hiddenFor: ["evaluador"] },
  { label: "Plantillas", href: "/templates", hiddenFor: ["evaluador"] },
  { label: "Instrumentos", href: "/instruments", hiddenFor: ["evaluador"] },
  { label: "Paciente simulado", href: "/simulated-patient", hiddenFor: ["evaluador"] },
  { label: "Validacion", href: "/validation", hiddenFor: ["evaluador"] },
  { label: "Pilotaje", href: "/pilotage", hiddenFor: ["evaluador"] },
  { label: "Publicacion", href: "/publication", hiddenFor: ["evaluador"] },
  { label: "Panel en vivo", href: "/live", hiddenFor: ["evaluador"] },
  { label: "Evaluador", href: "/evaluator" },
  { label: "Estudiante", href: "/student", hiddenFor: ["evaluador"] },
  { label: "Resultados", href: "/results", hiddenFor: ["evaluador"] },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuth();
  const visibleItems = items.filter((item) => !item.hiddenFor?.includes(user?.role ?? ""));

  return (
    <aside className="panel-card sticky top-4 h-fit">
      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-teal-700">
        ECOE operaciones
      </p>
      <h1 className="mt-3 text-2xl">Proyecto ECOE Digital</h1>
      <nav className="mt-6 space-y-2">
        {visibleItems.map(({ label, href }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`block rounded-2xl px-4 py-3 text-sm ${
                active
                  ? "bg-teal-700 font-semibold text-white shadow-sm"
                  : "bg-white/60 text-slate-700 hover:bg-white"
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
