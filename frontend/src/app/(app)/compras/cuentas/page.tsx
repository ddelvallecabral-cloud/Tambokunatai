"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { fechaCorta, hoyISO } from "@/lib/leche";
import { gs } from "@/lib/ventas";
import { ESTADO_CUENTA_PAGAR, type CuentaPagar, type Pago } from "@/lib/egresos";
import { Aviso, estiloInput, Insignia, Tarjeta } from "@/components/ui";

type Resumen = {
  total_por_pagar: number; vencido: number; comprado_mes: number; pagado_mes: number;
  por_proveedor: { proveedor: string; nombre: string; saldo: number; vencido: number; cuentas: number }[];
};

export default function CuentasPorPagar() {
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [cuentas, setCuentas] = useState<CuentaPagar[] | null>(null);
  const [estado, setEstado] = useState("abiertas");
  const [anulando, setAnulando] = useState<Pago | null>(null);
  const [motivo, setMotivo] = useState("");
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");

  const cargar = useCallback(() => {
    api<Resumen>("/cuentas-por-pagar-resumen").then(setResumen);
    api<{ results: CuentaPagar[] }>(`/cuentas-por-pagar?page_size=300&estado=${estado}`).then((r) => setCuentas(r.results));
  }, [estado]);
  useEffect(() => { cargar(); }, [cargar]);

  async function anularPago() {
    if (!anulando) return;
    setError(""); setAviso("");
    try {
      await api(`/cuentas-por-pagar/pagos/${anulando.id}/anular`, { method: "POST", body: JSON.stringify({ motivo }) });
      setAviso(`Pago de ${gs(anulando.monto)} anulado.`);
      setAnulando(null); setMotivo("");
      cargar();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo anular.");
    }
  }

  const hoy = hoyISO();
  return (
    <div className="space-y-5">
      {aviso && <Aviso tipo="ok">{aviso}</Aviso>}
      {error && <Aviso tipo="error">{error}</Aviso>}
      {resumen && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Tarjeta titulo="Por pagar" valor={gs(resumen.total_por_pagar)} />
          <Tarjeta titulo="Vencido" valor={<span className={resumen.vencido ? "text-red-700" : ""}>{gs(resumen.vencido)}</span>} />
          <Tarjeta titulo="Comprado este mes" valor={gs(resumen.comprado_mes)} />
          <Tarjeta titulo="Pagado este mes" valor={gs(resumen.pagado_mes)} />
        </div>
      )}

      <div className="max-w-xs">
        <label htmlFor="f-estado" className="mb-1 block text-xs font-medium">Mostrar</label>
        <select id="f-estado" value={estado} onChange={(e) => setEstado(e.target.value)} className={estiloInput}>
          <option value="abiertas">Pendientes de pago</option>
          <option value="pagada">Pagadas</option>
          <option value="anulada">Anuladas</option>
          <option value="todas">Todas</option>
        </select>
      </div>

      {anulando && (
        <div className="space-y-2 rounded-2xl border border-red-200 bg-red-50 p-4">
          <label htmlFor="motivo-pago" className="block text-sm font-medium text-red-900">¿Por qué se anula el pago de {gs(anulando.monto)} del {fechaCorta(anulando.fecha)}?</label>
          <input id="motivo-pago" value={motivo} onChange={(e) => setMotivo(e.target.value)} className={estiloInput} />
          <div className="flex gap-2">
            <button disabled={!motivo.trim()} onClick={anularPago} className="rounded-lg bg-red-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">Anular pago</button>
            <button onClick={() => setAnulando(null)} className="px-3 py-2 text-sm">Volver</button>
          </div>
        </div>
      )}

      {!cuentas ? <p className="text-stone-500">Cargando…</p> : cuentas.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">No hay cuentas en este estado.</p>
      ) : (
        <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white" aria-label="Cuentas por pagar">
          {cuentas.map((c) => {
            const vencida = c.saldo > 0 && c.vencimiento < hoy && c.estado !== "anulada";
            return (
              <li key={c.id} className="space-y-1 px-4 py-3">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  <Link href={`/compras/${c.compra}`} className="min-w-0 flex-1 hover:underline">
                    <span className="block font-medium">{c.proveedor_nombre}</span>
                    <span className="block text-xs text-stone-500">{c.compra_codigo}{c.factura && ` · Fact. ${c.factura}`} · {fechaCorta(c.fecha_emision)}</span>
                  </Link>
                  <span className={`text-sm ${vencida ? "font-medium text-red-700" : "text-stone-600"}`}>{vencida ? "Venció" : "Vence"} {fechaCorta(c.vencimiento)}</span>
                  <Insignia color={ESTADO_CUENTA_PAGAR[c.estado].color}>{ESTADO_CUENTA_PAGAR[c.estado].nombre}</Insignia>
                  <span className="w-32 text-right tabular-nums">
                    <span className="block font-semibold">{gs(c.saldo)}</span>
                    {c.pagado > 0 && <span className="block text-xs text-stone-500">de {gs(c.monto)}</span>}
                  </span>
                </div>
                {c.pagos.filter((p) => !p.anulado).map((p) => (
                  <p key={p.id} className="flex justify-between pl-2 text-xs text-stone-500">
                    <span>Pago {fechaCorta(p.fecha)} · {p.medio} · {gs(p.monto)}</span>
                    <button onClick={() => { setAnulando(p); setMotivo(""); }} className="text-red-700 hover:underline">Anular pago</button>
                  </p>
                ))}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
