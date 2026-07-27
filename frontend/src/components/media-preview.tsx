"use client";

import { useEffect, useState } from "react";
import type { MediaAsset } from "@/lib/types";

type Props = {
  asset: MediaAsset;
};

export function MediaPreview({ asset }: Props) {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        setLoading(true);
        // Fetch the file as blob and create an object URL
        const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api";
        const response = await fetch(`${API_URL}/media/file/${asset.id}`, {
          credentials: "include",
        });
        if (!response.ok) throw new Error("No se pudo cargar el archivo");
        const blob = await response.blob();
        if (active) {
          setUrl(URL.createObjectURL(blob));
          setLoading(false);
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Error al cargar");
          setLoading(false);
        }
      }
    }
    load();
    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [asset.id]);

  const isImage = asset.content_type?.startsWith("image/");
  const isVideo = asset.content_type?.startsWith("video/");
  const isAudio = asset.content_type?.startsWith("audio/");
  const isPdf = asset.content_type === "application/pdf" || asset.filename?.endsWith(".pdf");

  if (loading) {
    return <div className="flex items-center gap-2 py-4 text-sm text-slate-500">
      <span className="inline-block size-4 animate-spin rounded-full border-2 border-slate-300 border-t-[var(--color-primary)]" />
      Cargando {asset.original_name}...
    </div>;
  }

  if (error || !url) {
    return <div className="py-2 text-sm text-red-500">
      📁 {asset.original_name} — {error || "No disponible"}
    </div>;
  }

  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-slate-500 truncate">{asset.original_name}</p>
      {isImage ? (
        <img src={url} alt={asset.original_name} className="max-h-64 rounded-xl object-contain border border-slate-200" />
      ) : isVideo ? (
        <video controls className="max-h-64 rounded-xl w-full">
          <source src={url} type={asset.content_type} />
        </video>
      ) : isAudio ? (
        <audio controls className="w-full">
          <source src={url} type={asset.content_type} />
        </audio>
      ) : isPdf ? (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-[var(--color-primary)] hover:bg-slate-50"
        >
          📄 Abrir {asset.original_name}
        </a>
      ) : (
        <a
          href={url}
          download={asset.original_name}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
        >
          📎 Descargar {asset.original_name}
        </a>
      )}
    </div>
  );
}

export function MediaGrid({ assets }: { assets: MediaAsset[] }) {
  if (!assets.length) {
    return <p className="text-sm text-slate-400">Sin recursos multimedia para esta estación.</p>;
  }
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {assets.map((asset) => (
        <MediaPreview key={asset.id} asset={asset} />
      ))}
    </div>
  );
}
