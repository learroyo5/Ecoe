"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";

export default function ActivateInvitationPage() {
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [activated, setActivated] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const invitationToken = new URLSearchParams(window.location.search).get("token") ?? "";
    setToken(invitationToken);
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-8">
      <section className="panel-card w-full max-w-lg p-8">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--color-primary)]">
          Invitación institucional ECOE
        </p>
        <h1 className="mt-4 text-3xl">Activar cuenta</h1>
        {activated ? (
          <div className="mt-6 space-y-4">
            <p className="rounded-2xl bg-emerald-50 p-4 text-sm text-emerald-800">
              Tu acceso quedó listo. Ya puedes ingresar con tu correo y la contraseña que definiste.
            </p>
            <Link href="/login" className="btn-primary inline-flex">Ir al inicio de sesión</Link>
          </div>
        ) : (
          <form
            className="mt-6 space-y-4"
            onSubmit={async (event) => {
              event.preventDefault();
              setMessage(null);
              if (!token) {
                setMessage("El enlace no contiene una invitación válida.");
                return;
              }
              if (password !== confirmation) {
                setMessage("Las contraseñas no coinciden.");
                return;
              }
              setSaving(true);
              try {
                await api.activateInvitation(token, password);
                window.history.replaceState({}, "", "/activate");
                setToken("");
                setActivated(true);
              } catch (error) {
                setMessage(error instanceof Error ? error.message : "No se pudo activar la cuenta.");
              } finally {
                setSaving(false);
              }
            }}
          >
            <p className="text-sm leading-6 text-slate-600">
              Define una contraseña personal de al menos 12 caracteres. Quien te invitó no podrá verla.
            </p>
            <label className="block space-y-2">
              <span className="text-sm font-semibold">Contraseña</span>
              <input
                type="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={128}
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </label>
            <label className="block space-y-2">
              <span className="text-sm font-semibold">Confirmar contraseña</span>
              <input
                type="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={128}
                required
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
              />
            </label>
            <button className="btn-primary w-full" disabled={saving}>
              {saving ? "Activando..." : "Activar mi cuenta"}
            </button>
            {message ? <p role="alert" className="text-sm text-[var(--color-error)]">{message}</p> : null}
          </form>
        )}
      </section>
    </div>
  );
}
