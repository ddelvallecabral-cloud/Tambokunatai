"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fechaCorta } from "@/lib/leche";
import type { MisVentas } from "@/lib/reportes";
import { cantidadVenta as cantidad, gs } from "@/lib/ventas";
import { Periodo, usePeriodo } from "@/components/Periodo";
import { Aviso, Tarjeta, Vacio } from "@/components/ui";

export default function Pagina() {
  return <Suspense fallback={<p className="text-stone-500">Cargando…</p>}><Reporte /></Suspense>;
}

function Reporte() {
  const { consulta } = usePeriodo();
  const [r, setR] = useState<MisVentas | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    setR(null); setError("");
    api<MisVentas>(`/reportes/mis-ventas?${consulta}`).then(setR).catch((e) => setError(e.message));
  }, [consulta]);
  return (
    <div className="space-y-5">
      <Periodo />
      {error ? <Aviso tipo="error">{error}</Aviso> : !r ? <p className="text-stone-500">Calculando…</p> : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="mis-ventas">
            <Tarjeta titulo="Vendiste" valor={gs(r.total)} detalle={`${r.cantidad_ventas} ${r.cantidad_ventas === 1 ? "venta" : "ventas"}`} />
            {r.por_producto.map((p) => (
              <Tarjeta key={p.producto} titulo={p.nombre} valor={gs(p.total)} detalle={cantidad(p.cantidad, p.unidad)} />
            ))}
            <Tarjeta titulo="Cobraste" valor={gs(r.cobrado)} detalle="Cobros que registraste en el período" />
          </div>
          <div className="rounded-2xl border border-stone-200 bg-white p-4">
            <p className="text-sm text-stone-500">Te falta cobrar de tus ventas (de cualquier fecha)</p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">{gs(r.por_cobrar)}</p>
            <p className={`mt-1 text-xs ${r.vencido ? "font-medium text-red-700" : "text-stone-500"}`}>
              {r.vencido ? `${gs(r.vencido)} ya vencido` : "Nada vencido"} · Para cobrar, abrí la venta y tocá Registrar cobro.
            </p>
          </div>
          {r.ventas.length === 0 ? <Vacio>No registraste ventas en este período.</Vacio> : (
            <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white text-sm" aria-label="Mis ventas">
              {r.ventas.map((v) => (
                <li key={v.id}>
                  <Link href={`/ventas/${v.id}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 hover:bg-stone-50">
                    <span className="w-16 text-stone-500">{fechaCorta(v.fecha)}</span>
                    <span className="min-w-0 flex-1"><b>{v.codigo}</b> · {v.cliente}
                      <span className="block text-xs text-stone-500">{cantidad(v.cantidad, v.unidad)} de {v.producto}</span></span>
                    <span className="text-right tabular-nums">{gs(v.total)}
                      {v.saldo > 0 && <span className="block text-xs text-amber-700">falta {gs(v.saldo)}</span>}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
