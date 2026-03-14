"use client";

import { useState } from "react";

import { useAuth } from "@/lib/auth";

const demoUsers = [
  ["creator@ecoe.cl", "admin123", "Creador ECOE"],
  ["coeditor@ecoe.cl", "admin123", "Coeditor docente"],
  ["eval1@ecoe.cl", "admin123", "Evaluador"],
  ["coord@ecoe.cl", "admin123", "Coordinacion operativa"],
  ["timer@ecoe.cl", "admin123", "Cronometrador"],
];

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("creator@ecoe.cl");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-8">
      <div className="grid w-full max-w-6xl gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <section className="panel-card overflow-hidden p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-teal-700">
            Red local universitaria
          </p>
          <h1 className="mt-4 text-5xl">Gestion integral para ECOE y OSCE</h1>
          <p className="mt-4 max-w-2xl text-lg text-slate-600">
            Disena estaciones, pilota circuitos, ejecuta evaluaciones en vivo y consolida
            resultados con una sola plataforma.
          </p>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            <div className="rounded-3xl bg-teal-800 p-5 text-white">
              <p className="text-sm uppercase tracking-[0.16em] text-teal-100">MVP operativo</p>
              <p className="mt-3 text-3xl font-semibold">16</p>
              <p className="mt-2 text-sm text-teal-50">pantallas funcionales conectadas a API</p>
            </div>
            <div className="rounded-3xl bg-amber-600 p-5 text-white">
              <p className="text-sm uppercase tracking-[0.16em] text-amber-100">Modo dual</p>
              <p className="mt-3 text-3xl font-semibold">Pilotaje</p>
              <p className="mt-2 text-sm text-amber-50">separado estrictamente de ejecucion real</p>
            </div>
            <div className="rounded-3xl bg-slate-900 p-5 text-white">
              <p className="text-sm uppercase tracking-[0.16em] text-slate-300">Operativo</p>
              <p className="mt-3 text-3xl font-semibold">Tablets</p>
              <p className="mt-2 text-sm text-slate-200">UI sobria con pocos clics y botones grandes</p>
            </div>
          </div>
        </section>

        <section className="panel-card p-8">
          <p className="pill pill-ok">Acceso por rol</p>
          <h2 className="mt-4 text-3xl">Ingresar</h2>
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
            {error ? <p className="text-sm text-red-700">{error}</p> : null}
          </form>

          <div className="mt-8 space-y-3">
            <p className="text-sm font-semibold text-slate-700">Accesos demo</p>
            {demoUsers.map(([demoEmail, demoPassword, role]) => (
              <button
                key={demoEmail}
                className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3 text-left"
                onClick={() => {
                  setEmail(demoEmail);
                  setPassword(demoPassword);
                }}
              >
                <span>
                  <span className="block font-semibold">{role}</span>
                  <span className="text-sm text-slate-500">{demoEmail}</span>
                </span>
                <span className="pill pill-warn">demo</span>
              </button>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
