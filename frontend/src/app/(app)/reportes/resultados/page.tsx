"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { NOMBRE_CATEGORIA, NOMBRE_CENTRO } from "@/lib/egresos";
import { gsSigno, pct, type EstadoResultados } from "@/lib/reportes";
import { gs } from "@/lib/ventas";
import { Periodo, usePeriodo } from "@/components/Periodo";
import { Aviso } from "@/components/ui";

export default function Pagina() {
  return <Suspense fallback={<p className="text-stone-500">Cargando…</p>}><Resultados /></Suspense>;
}

function Resultados() {
  const { consulta, desde, hasta } = usePeriodo();
  const [r, setR] = useState<EstadoResultados | null>(null);
  useEffect(() => { setR(null); api<EstadoResultados>(`/reportes/estado-resultados?${consulta}`).then(setR); }, [consulta]);
  const fila = (concepto: React.ReactNode, monto: number, fuerte = false, sangria = false) => (
    <tr className={fuerte ? "border-t border-stone-300 font-semibold" : ""}>
      <td className={`py-2 ${sangria ? "pl-4 text-stone-700" : ""}`}>{concepto}</td>
      <td className={`py-2 text-right tabular-nums ${monto < 0 ? "text-red-700" : ""}`}>{gsSigno(monto)}</td>
    </tr>
  );
  return (
    <div className="space-y-5">
      <Periodo reporte="estado-resultados" />
      {!r ? <p className="text-stone-500">Calculando…</p> : (
        <>
          <section className="rounded-2xl border border-stone-200 bg-white p-5">
            <h2 className="mb-3 text-lg font-semibold">Estado de resultados</h2>
            <table className="w-full text-sm" data-testid="estado-resultados">
              <tbody>
                <tr><td colSpan={2} className="pt-1 text-xs font-semibold uppercase tracking-wide text-stone-500">Ingresos (ventas)</td></tr>
                {r.ingresos.map((i) => fila(<Link href={`/ventas?producto=${i.producto}&desde=${desde}&hasta=${hasta}`} className="hover:underline">{i.concepto}</Link>, i.monto, false, true))}
                {fila("Total ingresos", r.total_ingresos, true)}
                <tr><td colSpan={2} className="pt-4 text-xs font-semibold uppercase tracking-wide text-stone-500">Egresos</td></tr>
                {r.gastos_por_categoria.map((g) => fila(<Link href={`/gastos?categoria=${g.categoria}&estado=aprobado&desde=${desde}&hasta=${hasta}`} className="hover:underline">{NOMBRE_CATEGORIA[g.categoria] ?? g.categoria} <span className="text-stone-400">({g.cantidad})</span></Link>, -g.total, false, true))}
                {fila(<Link href={`/compras?desde=${desde}&hasta=${hasta}`} className="hover:underline">Compras de insumos <span className="text-stone-400">({r.cantidad_compras})</span></Link>, -r.compras_insumos, false, true)}
                {fila("Total egresos", -r.total_egresos, true)}
                <tr className="border-t-2 border-stone-800 text-base font-bold">
                  <td className="py-3">Resultado del período</td>
                  <td className={`py-3 text-right tabular-nums ${r.resultado < 0 ? "text-red-700" : "text-campo-800"}`} data-testid="resultado">{gsSigno(r.resultado)}</td>
                </tr>
              </tbody>
            </table>
            <p className="mt-2 text-xs text-stone-500">Margen sobre ventas: {pct(r.margen_pct)}. Ingresos por fecha de venta (cobrado o no). Gastos: solo aprobados. Compras de insumos: en el mes en que se compran.</p>
          </section>
          {r.gastos_pendientes.cantidad > 0 && (
            <Aviso tipo="alerta">
              No incluye {r.gastos_pendientes.cantidad} {r.gastos_pendientes.cantidad === 1 ? "gasto pendiente" : "gastos pendientes"} de aprobación por {gs(r.gastos_pendientes.total)}. <Link href="/aprobaciones" className="font-medium underline">Revisarlos</Link>
            </Aviso>
          )}
          <section className="rounded-2xl border border-stone-200 bg-white p-5">
            <h2 className="mb-3 font-semibold">Gastos por centro de costo</h2>
            <table className="w-full text-sm">
              <tbody className="divide-y divide-stone-100">
                {r.gastos_por_centro.map((c) => (
                  <tr key={c.centro_costo}><td className="py-2">{NOMBRE_CENTRO[c.centro_costo]}</td><td className="py-2 text-right text-stone-500">{c.cantidad} gastos</td><td className="py-2 text-right tabular-nums">{gs(c.total)}</td></tr>
                ))}
                {!r.gastos_por_centro.length && <tr><td className="py-2 text-stone-500">Sin gastos aprobados en el período.</td></tr>}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}
