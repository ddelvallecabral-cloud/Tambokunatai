"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ChevronRight, Paperclip } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { fechaCorta } from "@/lib/leche";
import { gs } from "@/lib/ventas";
import { NOMBRE_CATEGORIA, NOMBRE_CENTRO, type Gasto, type Pendientes } from "@/lib/egresos";
import { VerComprobante } from "@/components/Comprobante";
import { DecidirAprobacion } from "@/components/DecidirAprobacion";
import { Aviso } from "@/components/ui";

export default function Aprobaciones() {
  const [pendientes, setPendientes] = useState<Pendientes | null>(null);
  const [gastos, setGastos] = useState<Gasto[] | null>(null);
  const [abierto, setAbierto] = useState<string | null>(null);
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");

  const cargar = useCallback(() => {
    api<Pendientes>("/aprobaciones/pendientes").then(setPendientes);
    api<{ results: Gasto[] }>("/gastos?estado=pendiente&page_size=200").then((r) => setGastos(r.results));
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  async function decidir(g: Gasto, ruta: "aprobar" | "rechazar", comentario: string) {
    setError(""); setAviso("");
    try {
      await api(`/gastos/${g.id}/${ruta}`, { method: "POST", body: JSON.stringify({ comentario }) });
      setAviso(ruta === "aprobar" ? `Aprobado: ${g.descripcion} (${gs(g.monto)}).` : `Rechazado: ${g.descripcion}. ${g.creado_por_nombre ?? "Quien lo cargó"} ve tu comentario.`);
      setAbierto(null);
      cargar();
      return true;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar.");
      return false;
    }
  }

  const total = gastos?.reduce((s, g) => s + g.monto, 0) ?? 0;

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <h1 className="text-2xl font-semibold">Aprobaciones</h1>
      {aviso && <Aviso tipo="ok">{aviso}</Aviso>}
      {error && <Aviso tipo="error">{error}</Aviso>}

      {pendientes && (pendientes.lotes_queso > 0 || pendientes.correcciones_leche > 0) && (
        <div className="grid gap-3 sm:grid-cols-2">
          {pendientes.lotes_queso > 0 && (
            <Link href="/queso?estado=pendiente" className="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {pendientes.lotes_queso} {pendientes.lotes_queso === 1 ? "lote de queso espera" : "lotes de queso esperan"} control de calidad
              <ChevronRight className="h-4 w-4" aria-hidden />
            </Link>
          )}
          {pendientes.correcciones_leche > 0 && (
            <Link href="/leche/lotes?estado=pendiente" className="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {pendientes.correcciones_leche} {pendientes.correcciones_leche === 1 ? "corrección de leche espera" : "correcciones de leche esperan"} tu aprobación
              <ChevronRight className="h-4 w-4" aria-hidden />
            </Link>
          )}
        </div>
      )}

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">
          Gastos por aprobar {gastos && gastos.length > 0 && <span className="font-normal text-stone-500">· {gastos.length} por {gs(total)}</span>}
        </h2>
        {!gastos ? <p className="text-stone-500">Cargando…</p> : gastos.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">No hay gastos esperando tu aprobación.</p>
        ) : (
          <ul className="space-y-3" aria-label="Gastos pendientes">
            {gastos.map((g) => (
              <li key={g.id} className="rounded-2xl border border-stone-200 bg-white">
                <button onClick={() => setAbierto(abierto === g.id ? null : g.id)} aria-expanded={abierto === g.id}
                  className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-left">
                  <span className="w-24 text-sm text-stone-500">{fechaCorta(g.fecha)}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{g.descripcion}</span>
                    <span className="block text-xs text-stone-500">
                      {NOMBRE_CATEGORIA[g.categoria]} · {NOMBRE_CENTRO[g.centro_costo]} · cargó {g.creado_por_nombre ?? "—"}
                    </span>
                  </span>
                  {g.tiene_comprobante && <Paperclip className="h-4 w-4 text-stone-400" aria-label="Con comprobante" />}
                  <span className="w-28 text-right font-semibold tabular-nums">{gs(g.monto)}</span>
                </button>
                {abierto === g.id && (
                  <div className="space-y-3 border-t border-stone-100 p-4">
                    {g.proveedor_nombre && <p className="text-sm">Proveedor: {g.proveedor_nombre}</p>}
                    {g.comprobante_numero && <p className="text-sm">Comprobante n.º {g.comprobante_numero}</p>}
                    {g.tiene_comprobante ? <VerComprobante ruta={`/gastos/${g.id}/comprobante`} tipo={g.tipo_comprobante} />
                      : <p className="text-sm text-stone-500">Sin foto del comprobante.</p>}
                    <DecidirAprobacion idCampo={g.id} onAprobar={(c) => decidir(g, "aprobar", c)} onRechazar={(c) => decidir(g, "rechazar", c)} />
                    <Link href={`/gastos/${g.id}`} className="text-sm text-campo-700 hover:underline">Ver el detalle completo</Link>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
