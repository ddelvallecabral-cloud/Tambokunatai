"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fechaCorta, hoyISO } from "@/lib/leche";
import { ESTADO_CUENTA, gs, NOMBRE_MEDIO, vencida, type Cuenta, type ResumenCuentas } from "@/lib/ventas";
import { Aviso, estiloInput, Insignia, Tarjeta } from "@/components/ui";

export default function Cuentas() {
  const { puede } = useAuth();
  const [resumen, setResumen] = useState<ResumenCuentas | null>(null);
  const [cuentas, setCuentas] = useState<Cuenta[] | null>(null);
  const [estado, setEstado] = useState("abiertas");
  const [soloVencidas, setSoloVencidas] = useState(false);
  const [error, setError] = useState("");
  const hoy = hoyISO();

  const cargar = useCallback(() => {
    if (!puede("reportes.financieros")) return;
    api<ResumenCuentas>("/cuentas-por-cobrar-resumen").then(setResumen);
    const q = new URLSearchParams({ estado, page_size: "200" });
    if (soloVencidas) q.set("vencidas", "1");
    api<{ results: Cuenta[] }>(`/cuentas-por-cobrar?${q}`).then((p) => setCuentas(p.results));
  }, [estado, soloVencidas, puede]);
  useEffect(() => {
    cargar();
  }, [cargar]);

  if (!puede("reportes.financieros")) return <Aviso tipo="alerta">Las cuentas por cobrar de todo el tambo las ve solo el Administrador.</Aviso>;

  async function anularCobro(cobro: string, motivo: string) {
    setError("");
    try {
      await api(`/cuentas-por-cobrar/cobros/${cobro}/anular`, { method: "POST", body: JSON.stringify({ motivo }) });
      cargar();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo anular.");
    }
  }

  return (
    <div className="space-y-5">
      {resumen && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Tarjeta titulo="Por cobrar" valor={gs(resumen.total_por_cobrar)} />
            <Tarjeta titulo="Vencido" valor={<span className={resumen.vencido ? "text-red-700" : ""}>{gs(resumen.vencido)}</span>} />
            <Tarjeta titulo="Vendido este mes" valor={gs(resumen.vendido_mes)} />
            <Tarjeta titulo="Cobrado este mes" valor={gs(resumen.cobrado_mes)} />
          </div>
          {resumen.por_cliente.length > 0 && (
            <section className="rounded-2xl border border-stone-200 bg-white p-5">
              <h3 className="mb-2 font-semibold">Quién debe</h3>
              <ul className="divide-y divide-stone-100 text-sm">
                {resumen.por_cliente.map((c) => (
                  <li key={c.cliente} className="flex items-center justify-between gap-3 py-1.5">
                    <Link href={`/ventas/clientes/${c.cliente}`} className="text-campo-800 hover:underline">{c.nombre}</Link>
                    <span className="tabular-nums">
                      {c.vencido > 0 && <span className="mr-3 text-red-700">{gs(c.vencido)} vencido</span>}
                      <strong>{gs(c.saldo)}</strong> <span className="text-stone-500">({c.cuentas})</span>
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <select aria-label="Estado" value={estado} onChange={(e) => setEstado(e.target.value)} className={`${estiloInput} w-auto`}>
          <option value="abiertas">Con saldo</option>
          <option value="cobrada">Cobradas</option>
          <option value="anulada">Anuladas</option>
          <option value="todas">Todas</option>
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={soloVencidas} onChange={(e) => setSoloVencidas(e.target.checked)} /> Solo vencidas
        </label>
      </div>
      {error && <Aviso tipo="error">{error}</Aviso>}

      {!cuentas ? <p className="text-stone-500">Cargando…</p> : cuentas.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">No hay cuentas con esos filtros.</p>
      ) : (
        <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white">
          {cuentas.map((c) => {
            const atrasada = c.saldo > 0 && c.estado !== "anulada" && vencida(c.vencimiento, hoy);
            return (
              <li key={c.id} className="px-4 py-3">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                  <Link href={`/ventas/${c.venta}`} className="w-20 font-medium hover:underline">{c.venta_codigo}</Link>
                  <Link href={`/ventas/clientes/${c.cliente}`} className="min-w-0 flex-1 truncate hover:underline">{c.cliente_nombre}</Link>
                  <Insignia color={ESTADO_CUENTA[c.estado].color}>{ESTADO_CUENTA[c.estado].nombre}</Insignia>
                  <span className="ml-auto text-right text-sm tabular-nums">
                    <span className="block font-medium">{gs(c.saldo)} <span className="font-normal text-stone-500">de {gs(c.monto)}</span></span>
                    <span className={`block text-xs ${atrasada ? "font-medium text-red-700" : "text-stone-500"}`}>
                      {atrasada && <AlertTriangle className="mr-1 inline h-3 w-3" aria-hidden />}
                      {atrasada ? "Venció" : "Vence"} {fechaCorta(c.vencimiento)}
                    </span>
                  </span>
                </div>
                {c.cobros.length > 0 && (
                  <ul className="mt-2 space-y-1 border-l-2 border-stone-100 pl-3 text-xs text-stone-600">
                    {c.cobros.map((p) => (
                      <li key={p.id} className={`flex flex-wrap items-center gap-2 ${p.anulado ? "line-through opacity-60" : ""}`}>
                        <span>{fechaCorta(p.fecha)} · {gs(p.monto)} · {NOMBRE_MEDIO[p.medio] ?? p.medio}{p.referencia && ` (${p.referencia})`} · {p.usuario_nombre ?? "—"}</span>
                        {p.anulado && <span className="no-underline">anulado: “{p.motivo_anulacion}”</span>}
                        {!p.anulado && puede("ventas.venta.aprobar") && (
                          <AnularCobro onAnular={(m) => anularCobro(p.id, m)} />
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </li>
            );
          })}
        </ul>
      )}
      <p className="text-xs text-stone-500">Para cobrar, entrá a la venta y usá “Registrar cobro”.</p>
    </div>
  );
}

function AnularCobro({ onAnular }: { onAnular: (motivo: string) => void }) {
  const [abierto, setAbierto] = useState(false);
  const [motivo, setMotivo] = useState("");
  if (!abierto) return <button onClick={() => setAbierto(true)} className="text-red-700 hover:underline">Anular cobro</button>;
  return (
    <span className="flex w-full flex-wrap items-center gap-2">
      <input aria-label="Motivo de la anulación" value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="¿Por qué se anula?"
        className="min-w-0 flex-1 rounded-md border border-stone-300 px-2 py-1 text-sm" />
      <button disabled={!motivo.trim()} onClick={() => onAnular(motivo)} className="rounded-md bg-red-700 px-2 py-1 text-white disabled:opacity-50">Anular</button>
      <button onClick={() => setAbierto(false)} className="px-1">Volver</button>
    </span>
  );
}
