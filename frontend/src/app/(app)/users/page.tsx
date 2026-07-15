"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";
import { StatusNotice } from "@/components/forms";
import { DataTable } from "@/components/data-table";
import { LoadingButton } from "@/components/loading-button";

type UserRow = {
  id: number;
  email: string;
  full_name: string;
  role_code: string;
  is_active: boolean;
  account_status: string;
};

const ROLE_OPTIONS = [
  { value: "admin_global", label: "Administrador global" },
  { value: "miembro", label: "Miembro institucional" },
  { value: "admin_ecoe", label: "Administrador ECOE" },
  { value: "coeditor_docente", label: "Coeditor docente" },
  { value: "coordinador_operativo", label: "Coordinador operativo" },
  { value: "evaluador", label: "Evaluador" },
  { value: "estudiante", label: "Estudiante" },
  { value: "cronometrador", label: "Cronometrador" },
];

export default function UsersPage() {
  const { authenticated, eventId, ecoeEvent } = useECOE();
  const { data: users, setData } = useApi(
    () => api.listUsers(),
    [authenticated],
  );
  const { data: eventAdmins, setData: setEventAdmins } = useApi(
    () => api.eventAdmins(eventId),
    [authenticated, eventId],
  );

  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState({ full_name: "", email: "", password: "", role_code: "evaluador" });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!modalOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setModalOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [modalOpen]);

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
    const data = await api.listUsers();
    setData(data);
  };

  const handleSave = async () => {
    setSaving(true); setMessage(null);
    try {
      if (editingId) {
        await api.updateUser(editingId, {
          full_name: form.full_name,
          role_code: form.role_code,
          password: form.password || undefined,
        });
      } else {
        await api.createUser({
          full_name: form.full_name,
          email: form.email,
          password: form.password,
          role_code: form.role_code,
        });
      }
      await refresh();
      setModalOpen(false);
      setMessage(editingId ? "Usuario actualizado." : "Usuario creado correctamente.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Error al guardar.");
    } finally { setSaving(false); }
  };

  const toggleActive = async (u: UserRow) => {
    setMessage(null);
    try {
      await api.updateUser(u.id, { is_active: !u.is_active });
      await refresh();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo cambiar el estado del usuario.");
    }
  };

  const toggleEventAdmin = async (u: UserRow) => {
    setMessage(null);
    try {
      const assigned = (eventAdmins ?? []).some((item) => item.user_id === u.id);
      if (assigned) {
        await api.revokeEventAdmin(eventId, u.id);
      } else {
        await api.grantEventAdmin(eventId, u.id);
      }
      setEventAdmins(await api.eventAdmins(eventId));
      setMessage(
        assigned
          ? `Se retiro a ${u.full_name} como administrador del ECOE activo.`
          : `${u.full_name} ahora administra el ECOE activo.`,
      );
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo cambiar la administracion del ECOE.");
    }
  };

  return (
    <div className="space-y-6">
      <SectionCard title="Gestión institucional de usuarios" subtitle={`El administrador global gestiona cuentas y delega administradores para ${ecoeEvent?.name ?? "el ECOE activo"}.`}>
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
                <div className="flex flex-wrap gap-3">
                  <button className="text-sm text-[var(--color-primary)] hover:underline" onClick={() => openEdit(row as UserRow)}>
                    Editar
                  </button>
                  {(row as UserRow).role_code !== "admin_global" ? (
                    <button
                      className="text-sm text-[var(--color-primary)] hover:underline"
                      onClick={() => toggleEventAdmin(row as UserRow)}
                    >
                      {(eventAdmins ?? []).some((item) => item.user_id === (row as UserRow).id)
                        ? "Quitar admin ECOE"
                        : "Asignar admin ECOE"}
                    </button>
                  ) : null}
                </div>
              ),
            },
          ]}
        />

        <StatusNotice message={message} className="mt-4" />
      </SectionCard>

      {/* Modal */}
      {modalOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm"
          onClick={() => setModalOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="user-modal-title"
            className="mx-4 w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl animate-fade-in"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="user-modal-title" className="text-xl font-semibold text-slate-900">
              {editingId ? "Editar usuario" : "Crear usuario"}
            </h3>

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
