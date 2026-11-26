"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fechaCorta } from "@/lib/leche";
import { gsSigno, type FlujoCaja } from "@/lib/reportes";
import { gs } from "@/lib/ventas";
import { Periodo, usePeriodo } from "@/components/Periodo";
import { Tarjeta } from "@/components/ui";

export default function Pagina() {
  return <Suspense fallback={<p className="text-stone-500">Cargando…</p>}><Flujo /></Suspense>;
}

const nombreMes = (iso: string) => { const [a, m] = iso.split("-").map(Number); return new Date(a, m - 1, 1).toLocaleDateString("es-PY", { month: "long", year: "numeric" }); };

function Flujo() {
  const params = useSearchParams();
  const router = useRouter();
  const ruta = usePathname();
  const agrupar = params.get("agrupar") === "mes" ? "mes" : "dia";
  const { consulta } = usePeriodo(agrupar === "mes" ? "anio" : "mes");
  const [r, setR] = useState<FlujoCaja | null>(null);
  useEffect(() => { setR(null); api<FlujoCaja>(`/reportes/flujo-caja?${consulta}&agrupar=${agrupar}`).then(setR); }, [consulta, agrupar]);
  const cambiar = (a: string) => { const q = new URLSearchParams(params.toString()); q.set("agrupar", a); q.delete("desde"); q.delete("hasta"); router.replace(`${ruta}?${q}`); };

  return (
    <div className="space-y-5">
      <div className="flex gap-1 rounded-lg bg-stone-100 p-1 text-sm sm:w-fit" role="group" aria-label="Agrupar">
        {[["dia", "Diario"], ["mes", "Mensual"]].map(([v, n]) => (
          <button key={v} onClick={() => cambiar(v)} aria-pressed={agrupar === v} className={`flex-1 rounded-md px-4 py-1.5 ${agrupar === v ? "bg-white font-medium shadow-sm" : "text-stone-600"}`}>{n}</button>
        ))}
      </div>
      <Periodo reporte={agrupar === "mes" ? "flujo-caja-mensual" : "flujo-caja"} porDefecto={agrupar === "mes" ? "anio" : "mes"} />
      {!r ? <p className="text-stone-500">Calculando…</p> : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Tarjeta titulo="Entró (cobros)" valor={gs(r.totales.cobros)} />
            <Tarjeta titulo="Salió a proveedores" valor={gs(r.totales.pagos_proveedores)} />
            <Tarjeta titulo="Salió en gastos" valor={gs(r.totales.gastos)} />
            <Tarjeta titulo="Neto del período" valor={<span className={r.totales.neto < 0 ? "text-red-700" : "text-campo-800"}>{gsSigno(r.totales.neto)}</span>} />
          </div>
          <div className="overflow-x-auto rounded-2xl border border-stone-200 bg-white">
            <table className="w-full min-w-[640px] whitespace-nowrap text-sm" data-testid="flujo">
              <thead className="bg-stone-50 text-left text-xs text-stone-500">
                <tr><th className="px-4 py-2">{agrupar === "mes" ? "Mes" : "Día"}</th><th className="px-4 py-2 text-right">Cobros</th><th className="px-4 py-2 text-right">Pagos a proveedores</th><th className="px-4 py-2 text-right">Gastos</th><th className="px-4 py-2 text-right">Neto</th><th className="px-4 py-2 text-right">Acumulado</th></tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {r.filas.map((f) => (
                  <tr key={f.periodo}>
                    <td className="px-4 py-2 capitalize">{agrupar === "mes" ? nombreMes(f.periodo) : fechaCorta(f.periodo)}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{f.cobros ? gs(f.cobros) : "—"}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{f.pagos_proveedores ? gs(f.pagos_proveedores) : "—"}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{f.gastos ? gs(f.gastos) : "—"}</td>
                    <td className={`px-4 py-2 text-right tabular-nums ${f.neto < 0 ? "text-red-700" : ""}`}>{gsSigno(f.neto)}</td>
                    <td className={`px-4 py-2 text-right tabular-nums font-medium ${f.acumulado < 0 ? "text-red-700" : ""}`}>{gsSigno(f.acumulado)}</td>
                  </tr>
                ))}
                {!r.filas.length && <tr><td colSpan={6} className="px-4 py-6 text-center text-stone-500">No hubo movimientos de caja en el período.</td></tr>}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-stone-500">Entradas: cobros registrados. Salidas: pagos a proveedores y gastos aprobados (se toman como pagados en su fecha). No incluye el saldo de caja anterior al período.</p>
        </>
      )}
    </div>
  );
}
