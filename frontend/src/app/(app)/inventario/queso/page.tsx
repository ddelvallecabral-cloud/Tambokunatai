"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { kg } from "@/lib/formato";
import { fechaCorta } from "@/lib/leche";
import { ESTADO_QUESO, type EstadoQueso } from "@/lib/queso";
import { Insignia, Tarjeta } from "@/components/ui";

type Inventario = {
  kg_disponibles: string;
  kg_en_revision: string;
  lotes: { lote_queso: string; codigo: string; fecha: string; estado: EstadoQueso; kg: string; disponible_para_venta: boolean }[];
};

export default function InventarioQueso() {
  const [datos, setDatos] = useState<Inventario | null>(null);
  useEffect(() => {
    api<Inventario>("/inventario/queso").then(setDatos);
  }, []);
  if (!datos) return <p className="text-stone-500">Cargando…</p>;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <Tarjeta titulo="Disponible para vender" valor={kg(datos.kg_disponibles)} detalle="Lotes aprobados" />
        <Tarjeta titulo="En revisión" valor={kg(datos.kg_en_revision)} detalle="Esperando aprobación o corrección" />
      </div>
      <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white">
        {datos.lotes.map((l) => (
          <li key={l.lote_queso} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-sm">
            <Link href={`/queso/${l.lote_queso}`} className="w-32 font-medium text-campo-800 hover:underline">{l.codigo}</Link>
            <span className="text-stone-500">{fechaCorta(l.fecha)}</span>
            <Insignia color={ESTADO_QUESO[l.estado].color}>{ESTADO_QUESO[l.estado].nombre}</Insignia>
            <span className="ml-auto font-medium tabular-nums">{kg(l.kg)}</span>
          </li>
        ))}
        {datos.lotes.length === 0 && <li className="px-4 py-8 text-center text-stone-500">No hay queso en stock.</li>}
      </ul>
    </div>
  );
}
