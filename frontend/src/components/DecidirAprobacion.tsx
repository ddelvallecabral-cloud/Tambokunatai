"use client";

import { useState } from "react";
import { botonPrimario, estiloInput } from "@/components/ui";

/** Aprobar o rechazar (con comentario obligatorio al rechazar). */
export function DecidirAprobacion({ onAprobar, onRechazar, idCampo = "g" }: { idCampo?: string; onAprobar: (c: string) => Promise<boolean>; onRechazar: (c: string) => Promise<boolean> }) {
  const [comentario, setComentario] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const correr = async (f: (c: string) => Promise<boolean>) => { setOcupado(true); await f(comentario); setOcupado(false); };
  return (
    <section className="space-y-3 rounded-2xl border border-amber-200 bg-amber-50 p-5">
      <label htmlFor={`comentario-${idCampo}`} className="block text-sm font-medium text-amber-900">Comentario (obligatorio si lo rechazás)</label>
      <input id={`comentario-${idCampo}`} value={comentario} onChange={(e) => setComentario(e.target.value)} className={estiloInput} />
      <div className="flex gap-2">
        <button disabled={ocupado} onClick={() => correr(onAprobar)} className={`${botonPrimario} flex-1`}>Aprobar</button>
        <button disabled={ocupado || !comentario.trim()} onClick={() => correr(onRechazar)}
          className="flex-1 rounded-xl border border-red-300 bg-white px-4 py-3 font-semibold text-red-700 disabled:opacity-50">Rechazar</button>
      </div>
    </section>
  );
}

