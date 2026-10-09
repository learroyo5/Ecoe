"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";

import { useECOE } from "@/lib/auth";

/**
 * /ecoe/<id> ya no es una segunda pantalla del mismo evento: selecciona ese
 * ECOE como activo y lleva a Datos del ECOE, la única vista de gestión (UX-5).
 * Si el id no es accesible, el provider vuelve al primero de la lista.
 */
export default function ECOEDetailRedirect() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { ready, authenticated, setEventId } = useECOE();

  useEffect(() => {
    if (!ready || !authenticated) return;
    const id = Number(params.id);
    if (Number.isInteger(id) && id > 0) setEventId(id);
    router.replace("/ecoe");
  }, [ready, authenticated, params.id, setEventId, router]);

  return <div className="h-40 animate-pulse rounded-3xl bg-slate-100" aria-busy="true" />;
}
