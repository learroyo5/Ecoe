"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login, token, user } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !user) {
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
  }, [router, token, user]);

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-8">
      <div className="grid w-full max-w-6xl gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <section className="panel-card overflow-hidden p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--color-primary)]">
            DRNOTUS · Red academica clinica
          </p>
          <h1 className="mt-4 text-5xl">Gestion integral para ECOE y OSCE</h1>
          <p className="mt-4 max-w-2xl text-lg text-slate-600">
            Disena estaciones, pilota circuitos, ejecuta evaluaciones en vivo y consolida
            resultados con una sola plataforma.
          </p>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <div className="rounded-3xl bg-[linear-gradient(135deg,var(--color-primary-dark),var(--color-primary))] p-5 text-white">
              <p className="text-sm uppercase tracking-[0.16em] text-slate-100/85">MVP operativo</p>
              <p className="mt-3 text-3xl font-semibold">16</p>
              <p className="mt-2 text-sm text-slate-100/85">pantallas funcionales conectadas a API</p>
            </div>
            <div className="clinical-panel">
              <p className="text-sm uppercase tracking-[0.16em] text-slate-500">Modo dual</p>
              <p className="mt-3 text-3xl font-semibold">Pilotaje</p>
              <p className="mt-2 text-sm text-slate-600">separado estrictamente de ejecucion real</p>
            </div>
            <div className="clinical-panel">
              <p className="text-sm uppercase tracking-[0.16em] text-slate-500">Operativo</p>
              <p className="mt-3 text-3xl font-semibold">Tablets</p>
              <p className="mt-2 text-sm text-slate-600">UI sobria con pocos clics y botones grandes</p>
            </div>
          </div>
        </section>

        <section className="panel-card p-8">
          <p className="pill pill-ok">Acceso protegido</p>
          <h2 className="mt-4 text-3xl">Ingresar</h2>
          <p className="mt-3 text-sm leading-6 text-slate-600">
            Utiliza tu correo institucional y tu contrasena para entrar al entorno operativo de ECOE.
          </p>
          <form
            className="mt-6 space-y-4"
            onSubmit={async (event) => {
              event.preventDefault();
              setError(null);
              try {
                await login(email, password);
              } catch (err) {
                setError(err instanceof Error ? err.message : "No se pudo iniciar sesion.");
              }
            }}
          >
            <label className="space-y-2">
              <span className="text-sm font-semibold">Correo</span>
              <input value={email} onChange={(event) => setEmail(event.target.value)} />
            </label>
            <label className="space-y-2">
              <span className="text-sm font-semibold">Contrasena</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <button className="btn-primary w-full text-base">Iniciar sesion</button>
            {error ? <p className="text-sm text-[var(--color-error)]">{error}</p> : null}
          </form>
        </section>
      </div>
    </div>
  );
}
