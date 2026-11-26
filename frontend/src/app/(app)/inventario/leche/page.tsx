"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fechaCorta, litros } from "@/lib/leche";
import type { LecheDisponible } from "@/lib/queso";
import { Tarjeta } from "@/components/ui";

type Inventario = {
  dias: number;
  lotes: LecheDisponible[];
  litros_destinados_a_queso: string;
  litros_sin_destino: string;
  litros_disponibles_para_queso: string;
};

export default function InventarioLeche() {
  const [datos, setDatos] = useState<Inventario | null>(null);
  useEffect(() => {
    api<Inventario>("/inventario/leche").then(setDatos);
  }, []);
  if (!datos) return <p className="text-stone-500">Cargando…</p>;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Tarjeta titulo="Disponible para queso" valor={litros(datos.litros_disponibles_para_queso)} detalle={`Lotes de los últimos ${datos.dias} días`} />
        <Tarjeta titulo="Ya destinada a queso" valor={litros(datos.litros_destinados_a_queso)} detalle="Sin lote de queso todavía" />
        <Tarjeta titulo="Sin destino" valor={litros(datos.litros_sin_destino)} />
      </div>
      {datos.lotes.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">No queda leche sin usar en los últimos {datos.dias} días.</p>
      ) : (
        <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white">
          {datos.lotes.map((l) => (
            <li key={l.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-sm">
              <Link href={`/leche/lotes/${l.id}`} className="w-32 font-medium text-campo-800 hover:underline">{l.codigo}</Link>
              <span className="text-stone-500">{fechaCorta(l.fecha)}</span>
              <span className="ml-auto tabular-nums">{litros(l.total)} de {litros(l.litros)}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="text-xs text-stone-500">Cada vez que un lote de queso usa leche, queda un movimiento de salida atado al lote de leche de origen.</p>
    </div>
  );
}
