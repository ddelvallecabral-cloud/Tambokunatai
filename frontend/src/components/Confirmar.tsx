"use client";

import { useState } from "react";

/**
 * Botón para acciones que no se deshacen con un toque: la primera vez pregunta "¿Seguro?" en el mismo
 * lugar (sin ventanas emergentes, que en el celular se cierran sin querer) y recién el segundo toque actúa.
 */
export function Confirmar({ children, pregunta, si, onConfirmar, className, disabled, etiqueta }: {
  children: React.ReactNode; pregunta: string; si: string; onConfirmar: () => void;
  className?: string; disabled?: boolean; etiqueta?: string;
}) {
  const [preguntando, setPreguntando] = useState(false);
  if (!preguntando) {
    return (
      <button type="button" disabled={disabled} onClick={() => setPreguntando(true)} aria-label={etiqueta} className={className}>
        {children}
      </button>
    );
  }
  return (
    <span role="group" aria-label={pregunta} className="inline-flex flex-wrap items-center gap-2 text-sm">
      <span className="text-stone-700">{pregunta}</span>
      <button type="button" autoFocus onClick={() => { setPreguntando(false); onConfirmar(); }}
        className="rounded-lg bg-red-700 px-3 py-1.5 font-medium text-white hover:bg-red-800">{si}</button>
      <button type="button" onClick={() => setPreguntando(false)} className="rounded-lg px-3 py-1.5 font-medium text-stone-600 hover:bg-stone-100">No</button>
    </span>
  );
}
