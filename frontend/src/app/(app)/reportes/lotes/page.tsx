"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { kg, rendimiento } from "@/lib/formato";
import { fechaCorta, litros } from "@/lib/leche";
import { gsSigno, type RentabilidadLotes } from "@/lib/reportes";
import { gs } from "@/lib/ventas";
import { Periodo, usePeriodo } from "@/components/Periodo";
import { Aviso, Tarjeta } from "@/components/ui";

export default function Pagina() {
  return <Suspense fallback={<p className="text-stone-500">Cargando…</p>}><Lotes /></Suspense>;
}

function Lotes() {
  const { consulta } = usePeriodo();
  const [r, setR] = useState<RentabilidadLotes | null>(null);
  useEffect(() => { setR(null); api<RentabilidadLotes>(`/reportes/rentabilidad-lotes?${consulta}`).then(setR); }, [consulta]);
  const sinPrecio = r ? [...new Set(r.lotes.flatMap((l) => l.insumos_sin_precio))] : [];
  const t = r?.totales as Record<string, number> | undefined;
  return (
    <div className="space-y-5">
      <Periodo reporte="rentabilidad-lotes" />
      {!r || !t ? <p className="text-stone-500">Calculando…</p> : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Tarjeta titulo="Costo de producir" valor={gs(t.costo_total)} detalle={`${kg(t.kg)} en ${r.lotes.length} lotes`} />
            <Tarjeta titulo="Vendido de estos lotes" valor={gs(t.ingresos)} detalle={`${kg(t.kg_vendidos)} vendidos`} />
            <Tarjeta titulo="Margen de lo vendido" valor={<span className={t.margen_vendido < 0 ? "text-red-700" : ""}>{gsSigno(t.margen_vendido)}</span>} detalle="Ingresos − costo de los kg vendidos" />
            <Tarjeta titulo="Resultado de los lotes" valor={<span className={t.resultado < 0 ? "text-red-700" : ""}>{gsSigno(t.resultado)}</span>} detalle="Ingresos − costo total (incluye lo sin vender)" />
          </div>
          {sinPrecio.length > 0 && <Aviso tipo="alerta">Sin precio de compra cargado (no suman costo): {sinPrecio.join(", ")}. Registrá una compra para que se valoricen.</Aviso>}
          <div className="overflow-x-auto rounded-2xl border border-stone-200 bg-white">
            <table className="w-full min-w-[900px] whitespace-nowrap text-sm" data-testid="tabla-lotes">
              <thead className="bg-stone-50 text-left text-xs text-stone-500">
                <tr>
                  <th className="px-3 py-2">Lote</th><th className="px-3 py-2 text-right">Leche</th><th className="px-3 py-2 text-right">Kg</th><th className="px-3 py-2 text-right">L/kg</th>
                  <th className="px-3 py-2 text-right">Costo leche</th><th className="px-3 py-2 text-right">Insumos</th><th className="px-3 py-2 text-right">Elaboración</th>
                  <th className="px-3 py-2 text-right">Costo/kg</th><th className="px-3 py-2 text-right">Vendido</th><th className="px-3 py-2 text-right">Ingresos</th><th className="px-3 py-2 text-right">Resultado</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {r.lotes.map((l) => (
                  <tr key={l.lote}>
                    <td className="px-3 py-2"><Link href={`/queso/${l.lote}`} className="font-medium hover:underline">{l.codigo}</Link><span className="block text-xs text-stone-500">{fechaCorta(l.fecha)}</span></td>
                    <td className="px-3 py-2 text-right tabular-nums">{litros(l.litros)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{kg(l.kg)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{rendimiento(l.rendimiento)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{gs(l.costo_leche)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{gs(l.costo_insumos)}{l.insumos_sin_precio.length > 0 && <span title={`Sin precio: ${l.insumos_sin_precio.join(", ")}`} className="text-amber-700"> *</span>}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{gs(l.costo_elaboracion)}</td>
                    <td className="px-3 py-2 text-right tabular-nums font-medium">{gs(l.costo_kg)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{kg(l.kg_vendidos)}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{gs(l.ingresos)}</td>
                    <td className={`px-3 py-2 text-right tabular-nums font-medium ${l.resultado < 0 ? "text-red-700" : "text-campo-800"}`}>{gsSigno(l.resultado)}</td>
                  </tr>
                ))}
                {!r.lotes.length && <tr><td colSpan={11} className="px-3 py-6 text-center text-stone-500">No hay lotes de queso cerrados en el período.</td></tr>}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-stone-500">Costo del lote = leche al costo por litro del mes (gastos de producción de leche ÷ litros ordeñados) + insumos consumidos al precio promedio de compra + su parte de los gastos de elaboración de queso del mes. Ingresos: ventas de ese lote hasta hoy. Un resultado negativo puede ser solo queso que todavía no se vendió.</p>
        </>
      )}
    </div>
  );
}
