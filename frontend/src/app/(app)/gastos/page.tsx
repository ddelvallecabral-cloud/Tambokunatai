"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Paperclip, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fechaCorta } from "@/lib/leche";
import { gs } from "@/lib/ventas";
import {
  CATEGORIAS, CENTROS, ESTADO_GASTO, NOMBRE_CATEGORIA, NOMBRE_CENTRO, type EstadoGasto, type Gasto, type ResumenGastos,
} from "@/lib/egresos";
import { estiloInput, Insignia, Tarjeta } from "@/components/ui";

export default function Gastos() {
  return (
    <Suspense fallback={<p className="text-stone-500">Cargando…</p>}>
      <Listado />
    </Suspense>
  );
}

function Listado() {
  const { puede } = useAuth();
  const router = useRouter();
  const ruta = usePathname();
  const params = useSearchParams();
  const [gastos, setGastos] = useState<{ count: number; results: Gasto[] } | null>(null);
  const [resumen, setResumen] = useState<ResumenGastos | null>(null);
  const todos = puede("gastos.ver_todos");

  const filtro = (k: string) => params.get(k) ?? "";
  const cambiar = (k: string, v: string) => {
    const q = new URLSearchParams(params.toString());
    if (v) q.set(k, v);
    else q.delete(k);
    router.replace(`${ruta}?${q}`);
  };

  useEffect(() => {
    setGastos(null);
    api<{ count: number; results: Gasto[] }>(`/gastos?page_size=200&${params.toString()}`).then(setGastos);
    const q = new URLSearchParams();
    if (params.get("desde")) q.set("desde", params.get("desde")!);
    if (params.get("hasta")) q.set("hasta", params.get("hasta")!);
    api<ResumenGastos>(`/gastos/resumen?${q}`).then(setResumen);
  }, [params]);

  return (
    <div className="space-y-5">
      {puede("gastos.gasto.registrar") && (
        <Link href="/gastos/cargar" className="flex items-center justify-center gap-2 rounded-xl bg-campo-700 px-4 py-3 font-semibold text-white hover:bg-campo-900 sm:hidden">
          <Plus className="h-5 w-5" aria-hidden /> Cargar gasto
        </Link>
      )}
      {!todos && <p className="text-sm text-stone-600">Ves los gastos que cargaste vos.</p>}
      {resumen && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Tarjeta titulo="Aprobado" valor={gs(resumen.total_aprobado)} detalle={filtro("desde") || filtro("hasta") ? "En el período elegido" : "Todos"} />
          <Tarjeta titulo="Pendiente" valor={<span className={resumen.pendientes ? "text-amber-800" : ""}>{gs(resumen.total_pendiente)}</span>}
            detalle={`${resumen.pendientes} ${resumen.pendientes === 1 ? "gasto" : "gastos"} por aprobar`} />
          <Tarjeta titulo="Mayor categoría" valor={<span className="text-lg">{resumen.por_categoria[0] ? NOMBRE_CATEGORIA[resumen.por_categoria[0].categoria] : "—"}</span>}
            detalle={resumen.por_categoria[0] ? gs(resumen.por_categoria[0].total) : undefined} />
          <Tarjeta titulo="Se aprueba solo hasta" valor={<span className="text-lg">{gs(resumen.umbral_aprobacion)}</span>} detalle="Más que eso lo aprueba el Administrador" />
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <div>
          <label htmlFor="f-cat" className="mb-1 block text-xs font-medium">Categoría</label>
          <select id="f-cat" value={filtro("categoria")} onChange={(e) => cambiar("categoria", e.target.value)} className={estiloInput}>
            <option value="">Todas</option>
            {CATEGORIAS.map((c) => <option key={c.valor} value={c.valor}>{c.nombre}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="f-centro" className="mb-1 block text-xs font-medium">Centro de costo</label>
          <select id="f-centro" value={filtro("centro_costo")} onChange={(e) => cambiar("centro_costo", e.target.value)} className={estiloInput}>
            <option value="">Todos</option>
            {CENTROS.map((c) => <option key={c.valor} value={c.valor}>{c.nombre}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="f-estado" className="mb-1 block text-xs font-medium">Estado</label>
          <select id="f-estado" value={filtro("estado")} onChange={(e) => cambiar("estado", e.target.value)} className={estiloInput}>
            <option value="">Todos</option>
            {(Object.keys(ESTADO_GASTO) as EstadoGasto[]).map((e) => <option key={e} value={e}>{ESTADO_GASTO[e].nombre}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="f-desde" className="mb-1 block text-xs font-medium">Desde</label>
          <input id="f-desde" type="date" value={filtro("desde")} onChange={(e) => cambiar("desde", e.target.value)} className={estiloInput} />
        </div>
        <div>
          <label htmlFor="f-hasta" className="mb-1 block text-xs font-medium">Hasta</label>
          <input id="f-hasta" type="date" value={filtro("hasta")} onChange={(e) => cambiar("hasta", e.target.value)} className={estiloInput} />
        </div>
      </div>

      {!gastos ? <p className="text-stone-500">Cargando…</p> : gastos.results.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">No hay gastos con esos filtros.</p>
      ) : (
        <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white">
          {gastos.results.map((g) => (
            <li key={g.id}>
              <Link href={`/gastos/${g.id}`} className={`flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-stone-50 ${g.estado === "anulado" ? "opacity-60" : ""}`}>
                <span className="w-24 text-sm text-stone-500">{fechaCorta(g.fecha)}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{g.descripcion}</span>
                  <span className="block text-xs text-stone-500">
                    {NOMBRE_CATEGORIA[g.categoria]} · {NOMBRE_CENTRO[g.centro_costo]}{todos && g.creado_por_nombre && ` · ${g.creado_por_nombre}`}
                  </span>
                </span>
                {g.tiene_comprobante && <Paperclip className="h-4 w-4 text-stone-400" aria-label="Con comprobante" />}
                <Insignia color={ESTADO_GASTO[g.estado].color}>{g.estado === "aprobado" && g.aprobacion_automatica ? "Aprobado (automático)" : ESTADO_GASTO[g.estado].nombre}</Insignia>
                <span className="w-28 text-right font-medium tabular-nums">{gs(g.monto)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
