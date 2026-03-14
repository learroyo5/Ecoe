"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

import { Sidebar } from "@/components/sidebar";
import { useAuth } from "@/lib/auth";

export function AppShell({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  const { user, token, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!token && pathname !== "/login") {
      router.push("/login");
    }
  }, [pathname, router, token]);

  if (!token) {
    return null;
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
