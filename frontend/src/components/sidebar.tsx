"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useECOE } from "@/lib/auth";
import { NAV_ITEMS, type RoleCode } from "@/lib/routes";

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { user, eventRoles } = useECOE();
  const effectiveRoles = user?.role === "admin_global"
    ? ["admin_global"]
    : eventRoles.length > 0
      ? eventRoles
      : [user?.role ?? ""];
  const visibleItems = NAV_ITEMS.filter(
    (item) => effectiveRoles.some((role) => item.allowedFor.includes(role as RoleCode)),
  );

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
