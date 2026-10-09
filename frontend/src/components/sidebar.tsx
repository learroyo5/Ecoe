"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useECOE } from "@/lib/auth";
import { NAV_GROUPS, NAV_ITEMS, navItemForPath, type NavItem, type RoleCode } from "@/lib/routes";

function NavIcon({ path }: { path: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-[18px] shrink-0"
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  );
}

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { user, eventRoles } = useECOE();
  const effectiveRoles = user?.role === "admin_global"
    ? ["admin_global"]
    : eventRoles.length > 0
      ? eventRoles
      : [user?.role ?? ""];
  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.hidden && effectiveRoles.some((role) => item.allowedFor.includes(role as RoleCode)),
  );
  // Activo = item visible de prefijo más largo: /ecoe/12 marca "Datos del ECOE"
  // y /stations/builder (sin entrada propia) marca "Estaciones".
  const activeHref = navItemForPath(pathname, visibleItems)?.href;

  const renderItem = ({ label, href, icon }: NavItem) => {
    const active = href === activeHref;
    return (
      <Link
        key={href}
        href={href}
        onClick={onNavigate}
        aria-current={active ? "page" : undefined}
        className={`flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition ${
          active
            ? "bg-[linear-gradient(135deg,var(--color-primary),var(--color-primary-dark))] font-semibold text-white shadow-sm"
            : "text-slate-700 hover:bg-[var(--color-bg-soft)]"
        }`}
      >
        <NavIcon path={icon} />
        <span className="truncate">{label}</span>
      </Link>
    );
  };

  const ungrouped = visibleItems.filter((item) => !item.group);
  const groups = NAV_GROUPS.map((group) => ({
    ...group,
    items: visibleItems.filter((item) => item.group === group.key),
  })).filter((group) => group.items.length > 0);

  return (
    <aside className="panel-card flex h-full flex-col overflow-y-auto lg:sticky lg:top-4 lg:h-auto lg:max-h-[calc(100vh-2rem)]">
      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--color-primary)]">
        DRNOTUS
      </p>
      <p className="mt-1 font-[family-name:var(--font-display)] text-xl text-[var(--color-primary-dark)]">
        Plataforma ECOE
      </p>
      <nav className="mt-5 space-y-5" aria-label="Navegación principal">
        {ungrouped.length > 0 ? <div className="space-y-1">{ungrouped.map(renderItem)}</div> : null}
        {groups.map((group) => (
          <div key={group.key} role="group" aria-label={group.label}>
            <p className="px-3 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              {group.label}
            </p>
            <div className="mt-1.5 space-y-1">{group.items.map(renderItem)}</div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
