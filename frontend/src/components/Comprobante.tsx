"use client";

import { useEffect, useRef, useState } from "react";
import { Camera, FileText, X } from "lucide-react";
import { archivoProtegido } from "@/lib/api";
import { prepararFoto } from "@/lib/egresos";

/** Muestra la foto (o el PDF) de un comprobante guardado. Se baja con la sesión del usuario. */
export function VerComprobante({ ruta, tipo }: { ruta: string; tipo: "imagen" | "pdf" | null }) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let local: string | null = null;
    archivoProtegido(ruta).then((u) => { local = u; setUrl(u); }).catch(() => setError(true));
    return () => { if (local) URL.revokeObjectURL(local); };
  }, [ruta]);
  if (error) return <p className="text-sm text-red-700">No se pudo abrir el comprobante.</p>;
  if (!url) return <p className="text-sm text-stone-500">Cargando comprobante…</p>;
  if (tipo === "pdf") {
    return (
      <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-lg border border-stone-300 px-3 py-2 text-sm">
        <FileText className="h-4 w-4" aria-hidden /> Abrir el PDF del comprobante
      </a>
    );
  }
  return (
    <a href={url} target="_blank" rel="noreferrer" title="Ver en grande">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={url} alt="Foto del comprobante" className="max-h-96 w-auto rounded-xl border border-stone-200" />
    </a>
  );
}

/** Elegir o sacar la foto del comprobante. En el celular abre la cámara trasera. */
export function ElegirComprobante({ archivo, onCambio }: { archivo: File | null; onCambio: (f: File | null) => void }) {
  const entrada = useRef<HTMLInputElement>(null);
  const [vista, setVista] = useState<string | null>(null);
  const [preparando, setPreparando] = useState(false);

  useEffect(() => {
    if (!archivo || !archivo.type.startsWith("image/")) {
      setVista(null);
      return;
    }
    const u = URL.createObjectURL(archivo);
    setVista(u);
    return () => URL.revokeObjectURL(u);
  }, [archivo]);

  async function elegir(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setPreparando(true);
    onCambio(await prepararFoto(f));
    setPreparando(false);
  }

  return (
    <div className="space-y-2">
      <input ref={entrada} type="file" accept="image/*,application/pdf" capture="environment" onChange={elegir} className="hidden"
        aria-label="Foto del comprobante" data-testid="input-comprobante" />
      {archivo ? (
        <div className="flex items-start gap-3">
          {vista ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={vista} alt="Vista previa del comprobante" className="h-28 w-auto rounded-lg border border-stone-200" />
          ) : (
            <span className="flex items-center gap-2 rounded-lg border border-stone-200 px-3 py-2 text-sm"><FileText className="h-4 w-4" aria-hidden />{archivo.name}</span>
          )}
          <button type="button" onClick={() => onCambio(null)} className="flex items-center gap-1 text-sm text-stone-600 hover:text-red-700">
            <X className="h-4 w-4" aria-hidden /> Quitar
          </button>
        </div>
      ) : (
        <button type="button" onClick={() => entrada.current?.click()} disabled={preparando}
          className="flex w-full items-center justify-center gap-2 rounded-xl border-2 border-dashed border-stone-300 bg-white px-4 py-5 text-stone-600 hover:border-campo-500 hover:text-campo-800">
          <Camera className="h-5 w-5" aria-hidden /> {preparando ? "Preparando la foto…" : "Sacar o elegir foto del comprobante"}
        </button>
      )}
    </div>
  );
}
