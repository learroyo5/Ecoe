"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useECOE } from "@/lib/auth";

// Flujo real de la plataforma: es lo que le importa a un docente o
// coordinador, no las métricas de implementación.
const STAGES: { name: string; description: string; path: string }[] = [
  {
    name: "Planificar",
    description: "Diseña estaciones, pautas e instrumentos, y reutilízalos desde un banco.",
    path:
      "M3.75 6A2.25 2.25 0 0 1 6 3.75h2.25A2.25 2.25 0 0 1 10.5 6v2.25a2.25 2.25 0 0 1-2.25 2.25H6a2.25 2.25 0 0 1-2.25-2.25V6ZM3.75 15.75A2.25 2.25 0 0 1 6 13.5h2.25a2.25 2.25 0 0 1 2.25 2.25V18a2.25 2.25 0 0 1-2.25 2.25H6A2.25 2.25 0 0 1 3.75 18v-2.25ZM13.5 6a2.25 2.25 0 0 1 2.25-2.25H18A2.25 2.25 0 0 1 20.25 6v2.25A2.25 2.25 0 0 1 18 10.5h-2.25a2.25 2.25 0 0 1-2.25-2.25V6ZM13.5 15.75a2.25 2.25 0 0 1 2.25-2.25H18a2.25 2.25 0 0 1 2.25 2.25V18A2.25 2.25 0 0 1 18 20.25h-2.25a2.25 2.25 0 0 1-2.25-2.25v-2.25Z",
  },
  {
    name: "Pilotar",
    description: "Ensaya el circuito completo en un entorno aislado, sin tocar los datos reales.",
    path:
      "M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 0-6.23-.693L5 14.5m14.8.8 1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0 1 12 21a48.25 48.25 0 0 1-8.135-.687c-1.718-.293-2.3-2.379-1.067-3.61L5 14.5",
  },
  {
    name: "Ejecutar",
    description: "Cronómetro central, tablets por estación y control en vivo el día del examen.",
    path: "M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
  },
  {
    name: "Consolidar",
    description: "Corrección, trazabilidad y resultados exportables por estudiante y estación.",
    path:
      "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z",
  },
];

function StageIcon({ path }: { path: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="size-5"
      aria-hidden="true"
    >
      <path d={path} />
    </svg>
  );
}

export default function LoginPage() {
  const { login, authenticated, user, ready } = useECOE();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready || !authenticated || !user) {
      return;
    }
    if (user.role === "evaluador") {
      router.replace("/evaluator");
      return;
    }
    if (user.role === "estudiante") {
      router.replace("/student");
      return;
    }
    router.replace("/dashboard");
  }, [ready, router, authenticated, user]);

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-8">
      <div className="grid w-full max-w-6xl gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        {/* Presentación institucional */}
        <section className="order-2 panel-card p-8 lg:order-1 lg:p-10">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--color-primary)]">
            DRNOTUS · Red académica clínica
          </p>
          <h1 className="mt-4 text-4xl leading-tight lg:text-5xl">
            Gestión integral para ECOE y OSCE
          </h1>
          <p className="mt-4 max-w-xl text-lg leading-relaxed text-slate-600">
            La plataforma académica para conducir el examen clínico estructurado de principio a
            fin, en escuelas de medicina y ciencias de la salud.
          </p>

          <div className="mt-8 grid gap-3 sm:grid-cols-2">
            {STAGES.map((stage, index) => (
              <div
                key={stage.name}
                className="rounded-2xl border border-slate-200 bg-white/70 p-4"
              >
                <div className="flex items-center gap-3">
                  <span className="flex size-9 items-center justify-center rounded-xl bg-[var(--color-bg-soft)] text-[var(--color-primary)]">
                    <StageIcon path={stage.path} />
                  </span>
                  <span className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                    Fase {index + 1}
                  </span>
                </div>
                <h2 className="mt-3 text-base font-semibold text-slate-900">{stage.name}</h2>
                <p className="mt-1 text-sm leading-6 text-slate-600">{stage.description}</p>
              </div>
            ))}
          </div>

          <div className="mt-6 flex items-start gap-3 rounded-2xl border border-slate-200 bg-[var(--color-bg-soft)] px-4 py-3">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.6}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="mt-0.5 size-5 shrink-0 text-[var(--color-primary)]"
              aria-hidden="true"
            >
              <path d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
            <p className="text-sm leading-6 text-slate-600">
              Pilotaje y ejecución real quedan estrictamente separados: los ensayos nunca alteran
              las notas oficiales.
            </p>
          </div>
        </section>

        {/* Ingreso */}
        <section className="order-1 panel-card flex flex-col justify-center p-8 lg:order-2 lg:p-10">
          <p className="pill pill-ok w-fit">Acceso protegido</p>
          <h2 className="mt-4 text-3xl">Ingresar</h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            Usa tu correo institucional y tu contraseña para entrar al entorno operativo del ECOE.
          </p>
          <form
            className="mt-6 space-y-4"
            onSubmit={async (event) => {
              event.preventDefault();
              setError(null);
              try {
                await login(email, password);
              } catch (err) {
                setError(err instanceof Error ? err.message : "No se pudo iniciar sesión.");
              }
            }}
          >
            <label className="space-y-2">
              <span className="text-sm font-semibold">Correo</span>
              <input
                type="email"
                name="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </label>
            <label className="space-y-2">
              <span className="text-sm font-semibold">Contraseña</span>
              <input
                type="password"
                name="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <button className="btn-primary w-full text-base">Iniciar sesión</button>
            {error ? (
              <p role="alert" className="text-sm text-[var(--color-error)]">{error}</p>
            ) : null}
          </form>
          <p className="mt-6 border-t border-slate-200 pt-4 text-xs leading-5 text-slate-400">
            El acceso está reservado a cuentas habilitadas por la coordinación de cada ECOE. Si no
            puedes ingresar, contacta al equipo responsable de tu evento.
          </p>
        </section>
      </div>
    </div>
  );
}
