"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Paperclip } from "lucide-react";
import { api } from "@/lib/api";
import { fechaCorta } from "@/lib/leche";
import { gs } from "@/lib/ventas";
import { ESTADO_CUENTA_PAGAR, NOMBRE_CONDICION_COMPRA, type Compra, type Proveedor } from "@/lib/egresos";
import { estiloInput, Insignia } from "@/components/ui";

export default function Compras() {
  return (
    <Suspense fallback={<p className="text-stone-500">Cargando…</p>}>
      <Listado />
    </Suspense>
  );
}

function Listado() {
  const router = useRouter();
  const ruta = usePathname();
  const params = useSearchParams();
  const [compras, setCompras] = useState<Compra[] | null>(null);
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const filtro = (k: string) => params.get(k) ?? "";
  const cambiar = (k: string, v: string) => {
    const q = new URLSearchParams(params.toString());
    if (v) q.set(k, v);
    else q.delete(k);
    router.replace(`${ruta}?${q}`);
  };

  useEffect(() => {
    api<{ results: Proveedor[] }>("/proveedores?page_size=300").then((p) => setProveedores(p.results));
  }, []);
  useEffect(() => {
    setCompras(null);
    api<{ results: Compra[] }>(`/compras?page_size=200&${params.toString()}`).then((r) => setCompras(r.results));
  }, [params]);

  const total = compras?.filter((c) => c.estado_compra === "confirmada").reduce((s, c) => s + c.total, 0) ?? 0;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="col-span-2">
          <label htmlFor="f-prov" className="mb-1 block text-xs font-medium">Proveedor</label>
          <select id="f-prov" value={filtro("proveedor")} onChange={(e) => cambiar("proveedor", e.target.value)} className={estiloInput}>
            <option value="">Todos</option>
            {proveedores.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
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
      {compras && compras.length > 0 && <p className="text-sm text-stone-600">{compras.length} compras · {gs(total)} confirmadas</p>}

      {!compras ? <p className="text-stone-500">Cargando…</p> : compras.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">No hay compras con esos filtros.</p>
      ) : (
        <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white" aria-label="Compras">
          {compras.map((c) => {
            const cuenta = ESTADO_CUENTA_PAGAR[c.cuenta.estado];
            return (
              <li key={c.id}>
                <Link href={`/compras/${c.id}`} className={`flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-stone-50 ${c.estado_compra === "anulada" ? "opacity-60" : ""}`}>
                  <span className="w-24 text-sm text-stone-500">{fechaCorta(c.fecha)}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{c.codigo} · {c.proveedor_nombre}</span>
                    <span className="block truncate text-xs text-stone-500">
                      {c.items.map((i) => i.insumo_nombre).join(", ")} · {NOMBRE_CONDICION_COMPRA[c.condicion]}{c.factura && ` · Fact. ${c.factura}`}
                    </span>
                  </span>
                  {c.tiene_comprobante && <Paperclip className="h-4 w-4 text-stone-400" aria-label="Con comprobante" />}
                  {c.estado_compra === "anulada" ? <Insignia color="gris">Anulada</Insignia> : <Insignia color={cuenta.color}>{cuenta.nombre}</Insignia>}
                  <span className="w-28 text-right font-medium tabular-nums">{gs(c.total)}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
