"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fechaCorta } from "@/lib/leche";
import { cantidadVenta, ESTADO_VENTA, ESTADOS_VENTA, gs, NOMBRE_PRODUCTO, PRODUCTOS, type Venta } from "@/lib/ventas";
import { estiloInput, Insignia } from "@/components/ui";

export default function Ventas() {
  return (
    <Suspense fallback={<p className="text-stone-500">Cargando…</p>}>
      <ListadoVentas />
    </Suspense>
  );
}

function ListadoVentas() {
  const { puede } = useAuth();
  const router = useRouter();
  const ruta = usePathname();
  const params = useSearchParams();
  const [ventas, setVentas] = useState<{ count: number; results: Venta[] } | null>(null);
  const [buscar, setBuscar] = useState(params.get("buscar") ?? "");

  const filtro = (k: string) => params.get(k) ?? "";
  const cambiar = (k: string, v: string) => {
    const q = new URLSearchParams(params.toString());
    if (v) q.set(k, v);
    else q.delete(k);
    router.replace(`${ruta}?${q}`);
  };

  useEffect(() => {
    const t = setTimeout(() => buscar !== filtro("buscar") && cambiar("buscar", buscar.trim()), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buscar]);
  useEffect(() => {
    setVentas(null);
    api<{ count: number; results: Venta[] }>(`/ventas?page_size=100&${params.toString()}`).then(setVentas);
  }, [params]);

  const validas = ventas?.results.filter((v) => v.estado_venta !== "anulada") ?? [];
  const total = validas.reduce((s, v) => s + v.total, 0);
  const saldo = validas.reduce((s, v) => s + (v.cuenta?.saldo ?? 0), 0);

  return (
    <div className="space-y-5">
      {puede("ventas.venta.registrar") && (
        <Link href="/ventas/registrar" className="flex items-center justify-center gap-2 rounded-xl bg-campo-700 px-4 py-3 font-semibold text-white hover:bg-campo-900 sm:hidden">
          <Plus className="h-5 w-5" aria-hidden /> Registrar venta
        </Link>
      )}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <div className="col-span-2">
          <label htmlFor="buscar" className="mb-1 block text-xs font-medium">Cliente</label>
          <input id="buscar" value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Buscar por nombre" className={estiloInput} />
        </div>
        <div>
          <label htmlFor="producto" className="mb-1 block text-xs font-medium">Producto</label>
          <select id="producto" value={filtro("producto")} onChange={(e) => cambiar("producto", e.target.value)} className={estiloInput}>
            <option value="">Todos</option>
            {PRODUCTOS.map((p) => <option key={p.valor} value={p.valor}>{p.nombre}</option>)}
          </select>
        </div>
        <div className="col-span-2 sm:col-span-2">
          <label htmlFor="estado" className="mb-1 block text-xs font-medium">Estado</label>
          <select id="estado" value={filtro("estado_venta")} onChange={(e) => cambiar("estado_venta", e.target.value)} className={estiloInput}>
            <option value="">Todos</option>
            {ESTADOS_VENTA.map((e) => <option key={e.valor} value={e.valor}>{e.nombre}</option>)}
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
      </div>

      {!ventas ? (
        <p className="text-stone-500">Cargando…</p>
      ) : ventas.results.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">No hay ventas con esos filtros.</p>
      ) : (
        <>
          <p className="text-sm text-stone-600">
            {validas.length} {validas.length === 1 ? "venta" : "ventas"} por <strong className="tabular-nums">{gs(total)}</strong>
            {saldo > 0 && <> · <span className="text-amber-800">falta cobrar {gs(saldo)}</span></>}
          </p>
          <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white">
            {ventas.results.map((v) => (
              <li key={v.id}>
                <Link href={`/ventas/${v.id}`} className={`flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-stone-50 ${v.estado_venta === "anulada" ? "opacity-60" : ""}`}>
                  <span className="w-20 font-medium">{v.codigo}</span>
                  <span className="w-24 text-sm text-stone-500">{fechaCorta(v.fecha)}</span>
                  <span className="min-w-0 flex-1 truncate">{v.cliente_nombre}</span>
                  <Insignia color={ESTADO_VENTA[v.estado_venta].color}>{ESTADO_VENTA[v.estado_venta].nombre}</Insignia>
                  <span className="flex w-full items-center gap-4 text-sm tabular-nums sm:w-auto">
                    <span className="text-stone-600">{NOMBRE_PRODUCTO[v.producto]} · {cantidadVenta(v.cantidad, v.unidad)}</span>
                    <span className="ml-auto w-28 text-right font-medium">{gs(v.total)}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
