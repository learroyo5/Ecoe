"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { Sidebar } from "@/components/sidebar";
import { StatusNotice } from "@/components/forms";
import { useECOE } from "@/lib/auth";
import { roleLabel } from "@/lib/labels";

export function AppShell({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  const { user, eventRoles, authenticated, ready, logout, eventId, setEventId, ecoeList, ecoeEvent, loadError } = useECOE();
  const router = useRouter();
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const closeSidebar = useCallback(() => setSidebarOpen(false), []);

  const hasManagerRole = eventRoles.some((role) =>
    ["admin_ecoe", "coeditor_docente", "coordinador_operativo"].includes(role),
  );
  const effectiveOperatorRole = !hasManagerRole
    ? eventRoles.find((role) => role === "evaluador" || role === "estudiante" || role === "cronometrador")
    : undefined;

  useEffect(() => {
    if (!ready || !authenticated || !effectiveOperatorRole || pathname !== "/dashboard") return;
    if (effectiveOperatorRole === "evaluador") router.replace("/evaluator");
    if (effectiveOperatorRole === "estudiante") router.replace("/student");
    if (effectiveOperatorRole === "cronometrador") router.replace("/live");
  }, [authenticated, effectiveOperatorRole, pathname, ready, router]);

  if (!ready || !authenticated) return null;

  const isStationOperator = effectiveOperatorRole === "evaluador" || effectiveOperatorRole === "estudiante";

  // ── Evaluator / Student layout ──────────────────────────────────────
  if (isStationOperator) {
    return (
      <div className="mx-auto max-w-6xl px-3 py-3 sm:px-4 sm:py-4 lg:px-6">
        <main className="space-y-3 sm:space-y-4">
          <header className="panel-card z-20 flex flex-col gap-3 p-4 sm:sticky sm:top-4 sm:gap-4 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--color-primary)]">
                  Modo operativo de estación
                </p>
                <h2 className="mt-1 text-xl sm:mt-2 sm:text-2xl lg:text-3xl">{title}</h2>
                <p className="mt-1 max-w-2xl text-sm text-slate-600 sm:mt-2">{description}</p>
              </div>
              <div className="clinical-panel px-4 py-3 text-sm">
                <p className="font-semibold">{user?.full_name}</p>
                <p className="text-slate-500">{roleLabel(user?.role)}</p>
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-[1.4fr_0.6fr]">
              <div className="clinical-panel p-3 sm:p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">ECOE activo</p>
                <div className="mt-1 flex items-center gap-2">
                  <p className="text-base font-semibold text-slate-900 sm:text-lg truncate">
                    {String(ecoeEvent?.name ?? "ECOE sin nombre visible")}
                  </p>
                  {ecoeEvent?.status === "en_ejecucion" ? (
                    <span className="shrink-0 rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-700">EN VIVO</span>
                  ) : null}
                </div>
                <p className="text-sm text-slate-600">
                  {String(ecoeEvent?.course_name ?? "Curso sin definir")} ·{" "}
                  {String(ecoeEvent?.school_name ?? "Unidad académica sin definir")}
                </p>
                {(ecoeList?.length ?? 0) > 1 ? (
                  <label className="mt-2 flex items-center gap-2 text-sm">
                    <span className="text-slate-500">Cambiar:</span>
                    <select
                      value={String(eventId)}
                      disabled={ecoeEvent?.status === "en_ejecucion"}
                      onChange={(e) => setEventId(Number(e.target.value))}
                      className="text-sm"
                      title={ecoeEvent?.status === "en_ejecucion" ? "No puedes cambiar de ECOE durante la ejecución en vivo" : "Seleccionar ECOE"}
                    >
                      {(ecoeList ?? []).map((ecoe: Record<string, unknown>) => (
                        <option key={String(ecoe.id)} value={String(ecoe.id)}>
                          {String(ecoe.name)}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
              </div>
              <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-1">
                <button className="btn-secondary" onClick={logout} aria-label="Cerrar sesión">
                  Cerrar sesión
                </button>
              </div>
            </div>
          </header>
          <StatusNotice message={loadError} />
          {children}
        </main>
      </div>
    );
  }

  // ── Admin layout with hamburger sidebar ─────────────────────────────
  return (
    <div className="mx-auto flex max-w-[1600px] gap-6 px-4 py-4 lg:px-6">
      {/* Desktop sidebar */}
      <div className="hidden w-72 shrink-0 lg:block">
        <Sidebar />
      </div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm"
            onClick={closeSidebar}
            aria-hidden="true"
          />
          <div className="absolute inset-y-0 left-0 w-80 max-w-[85vw] animate-slide-in bg-white p-4 shadow-2xl">
            <div className="mb-3 flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--color-primary)]">
                Menú
              </span>
              <button
                onClick={closeSidebar}
                className="rounded-xl p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                aria-label="Cerrar menú"
              >
                <svg className="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <Sidebar onNavigate={closeSidebar} />
          </div>
        </div>
      )}

      <main className="min-w-0 flex-1 space-y-6">
        <header className="panel-card flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-3">
            {/* Hamburger button — visible only on mobile */}
            <button
              className="rounded-xl p-2 text-slate-500 hover:bg-slate-100 lg:hidden"
              onClick={() => setSidebarOpen(true)}
              aria-label="Abrir menú"
            >
              <svg className="size-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--color-primary)]">
                Plataforma operativa
              </p>
              <h2 className="mt-1 text-2xl">{title}</h2>
            </div>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <div className="text-right">
              <p className="font-semibold">{user?.full_name}</p>
              <p className="text-slate-500">{roleLabel(user?.role)}</p>
            </div>
            <button className="btn-secondary" onClick={logout} aria-label="Cerrar sesión">
              Cerrar sesión
            </button>
          </div>
        </header>

        {/* ECOE selector bar */}
        <div className="clinical-panel p-4">
          <div className="flex flex-wrap items-end gap-4">
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">ECOE en edición</p>
              <p className="mt-1 text-lg font-semibold text-slate-900 truncate">
                {String(ecoeEvent?.name ?? "ECOE sin nombre visible")}
              </p>
              <p className="text-sm text-slate-600">
                {String(ecoeEvent?.course_name ?? "Curso sin definir")} ·{" "}
                {String(ecoeEvent?.school_name ?? "Unidad académica sin definir")}
              </p>
            </div>
            <label className="space-y-1 text-sm text-slate-700">
              <span className="font-semibold">Cambiar de ECOE</span>
              <select
                value={String(eventId)}
                onChange={(event) => setEventId(Number(event.target.value))}
                aria-label="Seleccionar ECOE activo"
              >
                {(ecoeList ?? []).map((ecoe) => (
                  <option key={String(ecoe.id)} value={String(ecoe.id)}>
                    {String(ecoe.name)} · {String(ecoe.course_name ?? "")}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        <StatusNotice message={loadError} />
        {children}
      </main>
    </div>
  );
}
