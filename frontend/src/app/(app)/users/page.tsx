"use client";

import { useState } from "react";

import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";
import { DataTable } from "@/components/data-table";
import { LoadingButton } from "@/components/loading-button";

type UserRow = {
  id: number;
  email: string;
  full_name: string;
  role_code: string;
  is_active: boolean;
};

const ROLE_OPTIONS = [
  { value: "admin_ecoe", label: "Administrador ECOE" },
  { value: "coeditor_docente", label: "Coeditor docente" },
  { value: "coordinador_operativo", label: "Coordinador operativo" },
  { value: "evaluador", label: "Evaluador" },
  { value: "estudiante", label: "Estudiante" },
  { value: "cronometrador", label: "Cronometrador" },
];

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api";

async function usersRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { ...options, credentials: "include", cache: "no-store" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Error");
  }
  return res.json();
}

export default function UsersPage() {
  const { token } = useECOE();
  const { data: users, setData } = useApi(
    () => usersRequest<UserRow[]>("/users"),
    [token],
  );

  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState({ full_name: "", email: "", password: "", role_code: "evaluador" });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const openCreate = () => {
    setEditingId(null);
    setForm({ full_name: "", email: "", password: "", role_code: "evaluador" });
    setModalOpen(true);
  };

  const openEdit = (u: UserRow) => {
    setEditingId(u.id);
    setForm({ full_name: u.full_name, email: u.email, password: "", role_code: u.role_code });
    setModalOpen(true);
  };

  const refresh = async () => {
    const data = await usersRequest<UserRow[]>("/users");
    setData(data);
  };

  const handleSave = async () => {
    setSaving(true); setMessage(null);
    try {
      const payload = editingId
        ? { full_name: form.full_name, role_code: form.role_code, password: form.password || undefined }
        : { full_name: form.full_name, email: form.email, password: form.password, role_code: form.role_code };
      const method = editingId ? "PATCH" : "POST";
      const url = editingId ? `/users/${editingId}` : "/users";
      await usersRequest(url, { method, body: JSON.stringify(payload), headers: { "Content-Type": "application/json" } });
      await refresh();
      setModalOpen(false);
      setMessage(editingId ? "Usuario actualizado." : "Usuario creado correctamente.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Error al guardar.");
    } finally { setSaving(false); }
  };

  const toggleActive = async (u: UserRow) => {
    await usersRequest(`/users/${u.id}`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: !u.is_active }),
      headers: { "Content-Type": "application/json" },
    });
    await refresh();
  };

  return (
    <div className="space-y-6">
      <SectionCard title="Gestión de usuarios" subtitle="Crea, edita y administra las cuentas del sistema. Solo visible para el Administrador ECOE.">
        <div className="mb-4">
          <button className="btn-primary" onClick={openCreate}>Crear usuario</button>
        </div>

        <DataTable
          rows={users ?? []}
          searchKeys={["full_name", "email", "role_code"]}
          columns={[
            { key: "full_name", label: "Nombre" },
            { key: "email", label: "Correo" },
            {
              key: "role_code",
              label: "Rol",
              render: (row) => (
                <span className="text-xs font-semibold uppercase text-slate-500">
                  {ROLE_OPTIONS.find((r) => r.value === (row as UserRow).role_code)?.label ?? (row as UserRow).role_code}
                </span>
              ),
            },
            {
              key: "is_active",
              label: "Estado",
              render: (row) => {
                const u = row as UserRow;
                return (
                  <button
                    onClick={() => toggleActive(u)}
                    className={`rounded-full px-3 py-1 text-xs font-semibold transition ${
                      u.is_active ? "bg-green-100 text-green-700 hover:bg-red-100 hover:text-red-700" : "bg-red-100 text-red-700 hover:bg-green-100 hover:text-green-700"
                    }`}
                    title={u.is_active ? "Clic para desactivar" : "Clic para activar"}
                  >
                    {u.is_active ? "Activo" : "Inactivo"}
                  </button>
                );
              },
            },
            {
              key: "actions",
              label: "",
              render: (row) => (
                <button className="text-sm text-[var(--color-primary)] hover:underline" onClick={() => openEdit(row as UserRow)}>
                  Editar
                </button>
              ),
            },
          ]}
        />

        {message ? <p className="mt-4 text-sm text-green-700">{message}</p> : null}
      </SectionCard>

      {/* Modal */}
      {modalOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={() => setModalOpen(false)}>
          <div className="mx-4 w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl animate-fade-in" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-xl font-semibold text-slate-900">{editingId ? "Editar usuario" : "Crear usuario"}</h3>

            <div className="mt-4 space-y-4">
              <label className="block space-y-1">
                <span className="text-sm font-semibold text-slate-700">Nombre completo</span>
                <input value={form.full_name} onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} />
              </label>
              {!editingId ? (
                <label className="block space-y-1">
                  <span className="text-sm font-semibold text-slate-700">Correo</span>
                  <input type="email" value={form.email} onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
                </label>
              ) : null}
              <label className="block space-y-1">
                <span className="text-sm font-semibold text-slate-700">{editingId ? "Nueva contraseña (dejar vacío para no cambiar)" : "Contraseña"}</span>
                <input type="password" value={form.password} onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))} />
              </label>
              <label className="block space-y-1">
                <span className="text-sm font-semibold text-slate-700">Rol</span>
                <select value={form.role_code} onChange={(e) => setForm((f) => ({ ...f, role_code: e.target.value }))}>
                  {ROLE_OPTIONS.map((r) => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className="mt-6 flex gap-3 justify-end">
              <button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancelar</button>
              <LoadingButton loading={saving} disabled={!form.full_name || (!editingId && !form.email) || (!editingId && !form.password)} onClick={handleSave}>
                {editingId ? "Guardar cambios" : "Crear usuario"}
              </LoadingButton>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
