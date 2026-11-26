"use client";

import { Suspense, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { litros } from "@/lib/leche";
import { gsSigno, pct, type RentabilidadProductos } from "@/lib/reportes";
import { gs } from "@/lib/ventas";
import { Periodo, usePeriodo } from "@/components/Periodo";

export default function Pagina() {
  return <Suspense fallback={<p className="text-stone-500">Cargando…</p>}><Productos /></Suspense>;
}

const nombreMes = (iso: string) => { const [a, m] = iso.split("-").map(Number); return new Date(a, m - 1, 1).toLocaleDateString("es-PY", { month: "long", year: "numeric" }); };

function Productos() {
  const { consulta } = usePeriodo();
  const [r, setR] = useState<RentabilidadProductos | null>(null);
  useEffect(() => { setR(null); api<RentabilidadProductos>(`/reportes/rentabilidad-productos?${consulta}`).then(setR); }, [consulta]);
  return (
    <div className="space-y-5">
      <Periodo reporte="rentabilidad-productos" />
      {!r ? <p className="text-stone-500">Calculando…</p> : (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            {r.productos.map((p) => (
              <section key={p.producto} className="rounded-2xl border border-stone-200 bg-white p-5" data-testid={`producto-${p.producto}`}>
                <h2 className="text-lg font-semibold">{p.nombre}</h2>
                <dl className="mt-3 grid grid-cols-2 gap-y-2 text-sm">
                  <dt className="text-stone-500">Vendido</dt><dd className="text-right tabular-nums">{Number(p.cantidad).toLocaleString("es-PY")} {p.unidad} · {p.ventas} ventas</dd>
                  <dt className="text-stone-500">Ingresos</dt><dd className="text-right tabular-nums">{gs(p.ingresos)}</dd>
                  <dt className="text-stone-500">Costo de producir lo vendido</dt><dd className="text-right tabular-nums">{gs(p.costo)}</dd>
                  <dt className="border-t border-stone-200 pt-2 font-semibold">Margen bruto</dt>
                  <dd className={`border-t border-stone-200 pt-2 text-right font-semibold tabular-nums ${p.margen < 0 ? "text-red-700" : "text-campo-800"}`}>{gsSigno(p.margen)} · {pct(p.margen_pct)}</dd>
                  <dt className="text-stone-500">Precio promedio / costo por {p.unidad}</dt><dd className="text-right tabular-nums">{gs(p.precio_promedio)} / {gs(p.costo_unitario)}</dd>
                </dl>
              </section>
            ))}
          </div>
          <p className="text-sm text-stone-600">Total: ingresos {gs(r.total.ingresos)}, costo {gs(r.total.costo)}, margen bruto <b>{gsSigno(r.total.margen)}</b>. Los gastos de administración del período ({gs(r.gastos_administracion)}) no se reparten entre productos.</p>
          <section className="rounded-2xl border border-stone-200 bg-white p-5">
            <h2 className="mb-3 font-semibold">Costo de la leche por mes</h2>
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-stone-500"><tr><th className="py-1">Mes</th><th className="py-1 text-right">Gastos de producción</th><th className="py-1 text-right">Litros</th><th className="py-1 text-right">Costo por litro</th></tr></thead>
              <tbody className="divide-y divide-stone-100">
                {r.costo_litro_por_mes.map((m) => (
                  <tr key={m.mes}><td className="py-2 capitalize">{nombreMes(m.mes)}</td><td className="py-2 text-right tabular-nums">{gs(m.gastos)}</td><td className="py-2 text-right tabular-nums">{litros(m.litros)}</td><td className="py-2 text-right font-medium tabular-nums">{gs(m.por_litro)}</td></tr>
                ))}
                {!r.costo_litro_por_mes.length && <tr><td colSpan={4} className="py-3 text-stone-500">No hubo ordeñe en el período.</td></tr>}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-stone-500">Costo por litro = gastos aprobados del centro “Producción de leche” del mes ÷ litros ordeñados ese mes. Es la base para el costo de la leche vendida y de la usada en queso.</p>
          </section>
        </>
      )}
    </div>
  );
}
