"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { kg, rendimiento } from "@/lib/formato";
import { fechaCorta, litros } from "@/lib/leche";
import { ESTADO_QUESO, ESTADOS_QUESO, type LoteQueso, type ResumenQueso } from "@/lib/queso";
import { estiloInput, Insignia, Tarjeta } from "@/components/ui";

export default function Lotes() {
  return (
    <Suspense fallback={<p className="text-stone-500">Cargando…</p>}>
      <ListadoLotes />
    </Suspense>
  );
}

function ListadoLotes() {
  const { puede } = useAuth();
  const router = useRouter();
  const ruta = usePathname();
  const params = useSearchParams();
  const [resumen, setResumen] = useState<ResumenQueso | null>(null);
  const [lotes, setLotes] = useState<{ count: number; results: LoteQueso[] } | null>(null);

  const filtro = (k: string) => params.get(k) ?? "";
  const cambiar = (k: string, v: string) => {
    const q = new URLSearchParams(params.toString());
    if (v) q.set(k, v);
    else q.delete(k);
    router.replace(`${ruta}?${q}`);
  };

  useEffect(() => {
    api<ResumenQueso>("/queso/resumen").then(setResumen);
  }, []);
  useEffect(() => {
    setLotes(null);
    api<{ count: number; results: LoteQueso[] }>(`/lotes-queso?page_size=100&${params.toString()}`).then(setLotes);
  }, [params]);

  return (
    <div className="space-y-5">
      {resumen && (
        <>
          {resumen.pendientes_aprobacion > 0 && puede("queso.lote.aprobar") && (
            <button onClick={() => cambiar("estado", "pendiente")} className="flex w-full items-center gap-2 rounded-lg bg-amber-50 px-4 py-3 text-left text-sm text-amber-900">
              <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
              {resumen.pendientes_aprobacion === 1 ? "Hay 1 lote esperando tu aprobación." : `Hay ${resumen.pendientes_aprobacion} lotes esperando tu aprobación.`}
              <span className="font-medium underline">Ver</span>
            </button>
          )}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Tarjeta titulo="Leche lista para queso" valor={litros(resumen.leche_disponible_litros)} detalle="Últimos 7 días" />
            <Tarjeta titulo="En elaboración" valor={resumen.en_elaboracion} detalle={`${resumen.pendientes_aprobacion} pendientes de aprobación`} />
            <Tarjeta titulo="Queso disponible" valor={kg(resumen.queso.kg_disponibles)} detalle={`${kg(resumen.queso.kg_en_revision)} en revisión`} />
            <Tarjeta titulo="Rendimiento del mes" valor={rendimiento(resumen.mes.rendimiento_l_kg)}
              detalle={`Esperado ${resumen.rango_rendimiento.min} a ${resumen.rango_rendimiento.max} L/kg`} />
          </div>
        </>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div>
          <label htmlFor="estado" className="mb-1 block text-xs font-medium">Estado</label>
          <select id="estado" value={filtro("estado")} onChange={(e) => cambiar("estado", e.target.value)} className={estiloInput}>
            <option value="">Todos</option>
            {ESTADOS_QUESO.map((e) => <option key={e.valor} value={e.valor}>{e.nombre}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="desde" className="mb-1 block text-xs font-medium">Desde</label>
          <input id="desde" type="date" value={filtro("desde")} onChange={(e) => cambiar("desde", e.target.value)} className={estiloInput} />
        </div>
        <div>
          <label htmlFor="hasta" className="mb-1 block text-xs font-medium">Hasta</label>
          <input id="hasta" type="date" value={filtro("hasta")} onChange={(e) => cambiar("hasta", e.target.value)} className={estiloInput} />
        </div>
        <label className="flex items-end gap-2 pb-3 text-sm">
          <input type="checkbox" checked={filtro("fuera_de_rango") === "1"} onChange={(e) => cambiar("fuera_de_rango", e.target.checked ? "1" : "")} />
          Rendimiento fuera de rango
        </label>
      </div>

      {!lotes ? (
        <p className="text-stone-500">Cargando…</p>
      ) : lotes.results.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">No hay lotes con esos filtros.</p>
      ) : (
        <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white">
          {lotes.results.map((l) => (
            <li key={l.id}>
              <Link href={`/queso/${l.id}`} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-stone-50">
                <span className="w-32 font-medium">{l.codigo}</span>
                <span className="w-24 text-sm text-stone-500">{fechaCorta(l.fecha)}</span>
                <Insignia color={ESTADO_QUESO[l.estado].color}>{ESTADO_QUESO[l.estado].nombre}</Insignia>
                <span className="ml-auto flex items-center gap-4 text-sm tabular-nums">
                  <span>{litros(l.litros_leche)}</span>
                  <span className="w-20 text-right">{kg(l.kg_obtenidos)}</span>
                  <span className={`w-24 text-right ${l.rendimiento_fuera_de_rango ? "font-semibold text-red-700" : "text-stone-600"}`}>
                    {l.rendimiento_fuera_de_rango && <AlertTriangle className="mr-1 inline h-3.5 w-3.5" aria-label="Fuera de rango" />}
                    {rendimiento(l.rendimiento_l_kg)}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
