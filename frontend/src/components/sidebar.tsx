"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  ["Dashboard", "/dashboard"],
  ["Estudiantes", "/students"],
  ["Evaluadores", "/evaluators"],
  ["Estaciones", "/stations"],
  ["Constructor", "/stations/builder"],
  ["Plantillas", "/templates"],
  ["Instrumentos", "/instruments"],
  ["Paciente simulado", "/simulated-patient"],
  ["Validacion", "/validation"],
  ["Pilotaje", "/pilotage"],
  ["Publicacion", "/publication"],
  ["Panel en vivo", "/live"],
  ["Evaluador", "/evaluator"],
  ["Estudiante", "/student"],
  ["Resultados", "/results"],
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="panel-card sticky top-4 h-fit">
      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-teal-700">
        ECOE operaciones
      </p>
      <h1 className="mt-3 text-2xl">Proyecto Tecnologico ECOE</h1>
      <nav className="mt-6 space-y-2">
        {items.map(([label, href]) => {
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
