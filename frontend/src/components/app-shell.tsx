"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

import { Sidebar } from "@/components/sidebar";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { api } from "@/lib/api";

function defaultRouteForRole(role: string | undefined) {
  if (role === "evaluador") {
    return "/evaluator";
  }
  if (role === "estudiante") {
    return "/student";
  }
  return "/dashboard";
}

export function AppShell({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  const { user, token, logout, eventId, setEventId } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const { data: ecoeList } = useApi(
    () => api.listECOE(token!) as Promise<Record<string, unknown>[]>,
    [token],
  );
  const { data: currentECOE } = useApi(
    () => api.ecoe(eventId, token!) as Promise<Record<string, unknown>>,
    [eventId, token],
  );

  useEffect(() => {
    if (!token && pathname !== "/login") {
      router.push("/login");
    }
  }, [pathname, router, token]);

  useEffect(() => {
    if (!user) {
      return;
    }
    const targetPath = defaultRouteForRole(user.role);
    if ((user.role === "evaluador" || user.role === "estudiante") && pathname === "/dashboard") {
      router.replace(targetPath);
    }
  }, [pathname, router, user]);

  if (!token) {
    return null;
  }

  const isStationOperator = user?.role === "evaluador" || user?.role === "estudiante";

  if (isStationOperator) {
    return (
      <div className="mx-auto max-w-6xl px-3 py-3 sm:px-4 sm:py-4 lg:px-6">
        <main className="space-y-3 sm:space-y-4">
          <header className="panel-card z-20 flex flex-col gap-3 p-4 sm:sticky sm:top-4 sm:gap-4 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.22em] text-amber-700">
                  Modo operativo de estacion
                </p>
                <h2 className="mt-1 text-xl sm:mt-2 sm:text-2xl lg:text-3xl">{title}</h2>
                <p className="mt-1 max-w-2xl text-sm text-slate-600 sm:mt-2">{description}</p>
              </div>
              <div className="rounded-3xl bg-white/70 px-4 py-3 text-sm">
                <p className="font-semibold">{user?.full_name}</p>
                <p className="text-slate-500">{user?.role}</p>
              </div>
            </div>
            <div className="grid gap-3 md:grid-cols-[1.4fr_0.6fr]">
              <div className="rounded-2xl border border-slate-200 bg-white/80 p-3 sm:p-4">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  ECOE activo
                </p>
                <p className="mt-1 text-base font-semibold text-slate-900 sm:mt-2 sm:text-lg">
                  {String(currentECOE?.name ?? "ECOE sin nombre visible")}
                </p>
                <p className="text-sm text-slate-600">
                  {String(currentECOE?.course_name ?? "Curso sin definir")} ·{" "}
                  {String(currentECOE?.school_name ?? "Unidad academica sin definir")}
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-1">
                <button className="btn-secondary" onClick={logout}>
                  Cerrar sesion
                </button>
              </div>
            </div>
          </header>
          {children}
        </main>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-[1600px] gap-6 px-4 py-4 lg:px-6">
      <div className="hidden w-72 shrink-0 lg:block">
        <Sidebar />
      </div>
      <main className="min-w-0 flex-1 space-y-6">
        <header className="panel-card flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-amber-700">
              Plataforma operativa
            </p>
            <h2 className="mt-2 text-3xl">{title}</h2>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">{description}</p>
            <div className="mt-4 rounded-2xl border border-slate-200 bg-white/80 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                ECOE en edicion
              </p>
              <div className="mt-2 grid gap-3 md:grid-cols-[1.2fr_0.8fr]">
                <div>
                  <p className="text-lg font-semibold text-slate-900">
                    {String(currentECOE?.name ?? "ECOE sin nombre visible")}
                  </p>
                  <p className="text-sm text-slate-600">
                    {String(currentECOE?.course_name ?? "Curso sin definir")} ·{" "}
                    {String(currentECOE?.school_name ?? "Unidad academica sin definir")}
                  </p>
                </div>
                <label className="space-y-2 text-sm text-slate-700">
                  <span className="font-semibold">Cambiar de ECOE</span>
                  <select
                    value={String(eventId)}
                    onChange={(event) => setEventId(Number(event.target.value))}
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
          </div>
          <div className="rounded-3xl bg-white/70 p-4 text-sm">
            <p className="font-semibold">{user?.full_name}</p>
            <p className="text-slate-500">{user?.role}</p>
            <button className="btn-secondary mt-3 w-full" onClick={logout}>
              Cerrar sesion
            </button>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
