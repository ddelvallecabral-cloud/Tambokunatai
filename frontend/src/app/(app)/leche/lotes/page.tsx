"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { DESTINOS, fechaCorta, litros, NOMBRE_DESTINO, NOMBRE_ESTADO, type Lote } from "@/lib/leche";

type Pagina = { count: number; results: Lote[] };

const COLOR_ESTADO: Record<Lote["estado"], string> = {
  borrador: "bg-stone-100 text-stone-700",
  pendiente: "bg-sky-100 text-sky-800",
  aprobado: "bg-campo-100 text-campo-900",
  rechazado: "bg-red-100 text-red-800",
  cerrado: "bg-stone-800 text-white",
  anulado: "bg-stone-100 text-stone-400 line-through",
};

function Listado() {
  const router = useRouter();
  const params = useSearchParams();
  const [pagina, setPagina] = useState<Pagina | null>(null);
  const filtros = {
    desde: params.get("desde") ?? "",
    hasta: params.get("hasta") ?? "",
    destino: params.get("destino") ?? "",
    estado: params.get("estado") ?? "",
  };

  useEffect(() => {
    const q = new URLSearchParams(Object.entries(filtros).filter(([, v]) => v));
    setPagina(null);
    api<Pagina>(`/lotes-leche?${q}`).then(setPagina);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  function cambiar(campo: string, valor: string) {
    const q = new URLSearchParams(params);
    if (valor) q.set(campo, valor);
    else q.delete(campo);
    router.replace(`/leche/lotes?${q}`);
  }

  const estiloCampo = "w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm";
  const totalLitros = pagina?.results.reduce((s, l) => s + Number(l.litros), 0) ?? 0;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 rounded-2xl border border-stone-200 bg-white p-4 sm:grid-cols-4">
        <label className="text-xs font-medium text-stone-600">
          Desde
          <input type="date" value={filtros.desde} onChange={(e) => cambiar("desde", e.target.value)} className={`${estiloCampo} mt-1`} />
        </label>
        <label className="text-xs font-medium text-stone-600">
          Hasta
          <input type="date" value={filtros.hasta} onChange={(e) => cambiar("hasta", e.target.value)} className={`${estiloCampo} mt-1`} />
        </label>
        <label className="text-xs font-medium text-stone-600">
          Destino
          <select value={filtros.destino} onChange={(e) => cambiar("destino", e.target.value)} className={`${estiloCampo} mt-1`}>
            <option value="">Todos</option>
            {DESTINOS.map((d) => (
              <option key={d.valor} value={d.valor}>{d.valor === "pendiente" ? "Con litros sin destino" : d.corto}</option>
            ))}
          </select>
        </label>
        <label className="text-xs font-medium text-stone-600">
          Estado
          <select value={filtros.estado} onChange={(e) => cambiar("estado", e.target.value)} className={`${estiloCampo} mt-1`}>
            <option value="">Todos (sin anulados)</option>
            {Object.entries(NOMBRE_ESTADO).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
      </div>

      {!pagina ? (
        <p className="text-stone-500">Cargando…</p>
      ) : pagina.results.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">No hay lotes con esos filtros.</p>
      ) : (
        <>
          <p className="text-sm text-stone-600" data-testid="resumen-listado">
            {pagina.count} {pagina.count === 1 ? "lote" : "lotes"} · {litros(totalLitros)}
            {pagina.count > pagina.results.length && ` (mostrando ${pagina.results.length})`}
          </p>
          <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white">
            {pagina.results.map((l) => (
              <li key={l.id}>
                <Link href={`/leche/lotes/${l.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-stone-50" data-testid="fila-lote">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">
                      {fechaCorta(l.fecha)} · {l.ordene === "manana" ? "Mañana" : "Tarde"}
                    </p>
                    <p className="text-xs text-stone-500">
                      {l.codigo} · {NOMBRE_DESTINO[l.destino]}
                      {Number(l.saldo_disponible) > 0 && l.destino !== "pendiente" && ` · quedan ${litros(l.saldo_disponible)}`}
                    </p>
                  </div>
                  <span className={`hidden rounded-full px-2 py-0.5 text-xs font-medium sm:inline ${COLOR_ESTADO[l.estado]}`}>{NOMBRE_ESTADO[l.estado]}</span>
                  <span className="w-24 text-right text-lg font-semibold tabular-nums">{litros(l.litros)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

export default function LotesLeche() {
  return (
    <Suspense fallback={<p className="text-stone-500">Cargando…</p>}>
      <Listado />
    </Suspense>
  );
}
