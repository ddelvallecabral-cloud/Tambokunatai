"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { cantidad, fechaHora } from "@/lib/formato";
import { NOMBRE_MOTIVO, NOMBRE_TIPO, type Movimiento } from "@/lib/inventario";
import { estiloInput, Vacio } from "@/components/ui";

export default function Movimientos() {
  const [item, setItem] = useState("");
  const [movs, setMovs] = useState<{ count: number; results: Movimiento[] } | null>(null);
  useEffect(() => {
    setMovs(null);
    api<{ count: number; results: Movimiento[] }>(`/movimientos-inventario?page_size=200${item ? `&item=${item}` : ""}`).then(setMovs);
  }, [item]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="w-48">
          <label htmlFor="item" className="mb-1 block text-xs font-medium">Qué se movió</label>
          <select id="item" value={item} onChange={(e) => setItem(e.target.value)} className={estiloInput}>
            <option value="">Todo</option>
            <option value="insumo">Insumos</option>
            <option value="leche">Leche</option>
            <option value="queso">Queso</option>
          </select>
        </div>
        <p className="text-xs text-stone-500">Los movimientos no se editan ni se borran: un error se corrige con un movimiento contrario.</p>
      </div>
      {!movs ? <p className="text-stone-500">Cargando…</p> : movs.results.length === 0 ? (
        <Vacio>No hay movimientos con ese filtro. Aparecen solos al registrar ordeñes, elaboraciones, compras y ventas.</Vacio>
      ) : (
        <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white text-sm">
          {movs.results.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5">
              <span className={`w-20 font-medium ${m.tipo === "entrada" || m.tipo === "liberacion" ? "text-campo-700" : "text-stone-800"}`}>{NOMBRE_TIPO[m.tipo]}</span>
              <span className="min-w-0 flex-1">
                {m.insumo_nombre ?? (m.item === "leche" ? "Leche" : "Queso")}
                <span className="ml-2 text-stone-500">{NOMBRE_MOTIVO[m.motivo] ?? m.motivo}</span>
                {m.lote_leche && <> · <Link href={`/leche/lotes/${m.lote_leche}`} className="text-campo-700 hover:underline">{m.lote_leche_codigo}</Link></>}
                {m.lote_queso && <> · <Link href={`/queso/${m.lote_queso}`} className="text-campo-700 hover:underline">{m.lote_queso_codigo}</Link></>}
                {m.lote_proveedor && <span className="text-stone-500"> · lote prov. {m.lote_proveedor}</span>}
                {m.nota && <span className="text-stone-500"> · {m.nota}</span>}
              </span>
              <span className="tabular-nums">{cantidad(m.cantidad, m.unidad)}</span>
              <span className="w-40 text-right text-xs text-stone-500">{fechaHora(m.fecha)} · {m.usuario_nombre ?? "—"}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
