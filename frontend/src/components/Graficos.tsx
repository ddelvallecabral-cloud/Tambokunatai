"use client";

import { useState } from "react";

/** Barras verticales de una sola serie (p. ej. litros por día), con el valor al pasar el dedo o el mouse. */
export function BarrasDiarias({ datos, unidad, etiqueta, minimo }: {
  datos: { fecha: string; valor: number }[]; unidad: string; etiqueta: string; minimo?: number | null;
}) {
  const [activa, setActiva] = useState<number | null>(null);
  // 15 % de aire arriba para que la línea del mínimo no choque con el título.
  const max = Math.max(1, ...datos.map((d) => d.valor), minimo ?? 0) * 1.15;
  const fmt = (v: number) => `${v.toLocaleString("es-PY", { maximumFractionDigits: 1 })} ${unidad}`;
  const dia = (iso: string) => { const [, m, d] = iso.split("-"); return `${Number(d)}/${Number(m)}`; };
  const sel = activa != null ? datos[activa] : datos[datos.length - 1];
  return (
    <figure className="space-y-2">
      <figcaption className="flex items-baseline justify-between text-sm">
        <span className="text-stone-500">{etiqueta}</span>
        {sel && <span className="tabular-nums text-stone-700" aria-live="polite">{dia(sel.fecha)}: <b>{fmt(sel.valor)}</b></span>}
      </figcaption>
      <div className="relative h-28" onMouseLeave={() => setActiva(null)}>
        {minimo ? (
          <div className="pointer-events-none absolute inset-x-0 border-t border-dashed border-amber-500" style={{ bottom: `${(minimo / max) * 100}%` }}>
            <span className="absolute right-0 top-0.5 bg-white/80 px-1 text-[10px] text-amber-800">mínimo {fmt(minimo)}</span>
          </div>
        ) : null}
        <div className="flex h-full items-end gap-[2px]">
          {datos.map((d, i) => (
            <button key={d.fecha} type="button" onMouseEnter={() => setActiva(i)} onFocus={() => setActiva(i)} onClick={() => setActiva(i)}
              aria-label={`${dia(d.fecha)}: ${fmt(d.valor)}`} className="group flex h-full flex-1 items-end">
              <span className={`block w-full rounded-t-[3px] ${activa === i ? "bg-campo-900" : "bg-campo-600 group-hover:bg-campo-800"}`}
                style={{ height: `${Math.max(d.valor ? 2 : 0, (d.valor / max) * 100)}%` }} />
            </button>
          ))}
        </div>
      </div>
      <div className="flex justify-between text-[11px] text-stone-400">
        <span>{datos[0] && dia(datos[0].fecha)}</span><span>{datos.length && dia(datos[datos.length - 1].fecha)}</span>
      </div>
    </figure>
  );
}

/** Barras horizontales de una sola serie (p. ej. gastos por categoría), con el monto como etiqueta. */
export function BarrasHorizontales({ filas, formato }: { filas: { nombre: string; valor: number; detalle?: string }[]; formato: (v: number) => string }) {
  const max = Math.max(1, ...filas.map((f) => f.valor));
  if (!filas.length) return <p className="text-sm text-stone-500">Sin datos en el período.</p>;
  return (
    <ul className="space-y-2">
      {filas.map((f) => (
        <li key={f.nombre} title={f.detalle}>
          <div className="flex justify-between gap-2 text-sm">
            <span className="truncate">{f.nombre}</span>
            <span className="shrink-0 tabular-nums font-medium">{formato(f.valor)}</span>
          </div>
          <div className="mt-1 h-2 rounded-full bg-stone-100">
            <div className="h-2 rounded-full bg-campo-600" style={{ width: `${(f.valor / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
