"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { ArrowLeft, Truck } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fechaHora } from "@/lib/formato";
import { fechaCorta, hoyISO } from "@/lib/leche";
import {
  cantidadVenta, ESTADO_CUENTA, ESTADO_VENTA, gs, MEDIOS, NOMBRE_PRODUCTO, vencida, type Venta,
} from "@/lib/ventas";
import { Aviso, botonPrimario, botonSecundario, estiloInput, Insignia, Tarjeta } from "@/components/ui";

export default function DetalleVenta() {
  return (
    <Suspense fallback={<p className="text-stone-500">Cargando…</p>}>
      <Detalle />
    </Suspense>
  );
}

function Detalle() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const { puede } = useAuth();
  const [venta, setVenta] = useState<Venta | null>(null);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState(params.get("registrada") ? "Venta registrada. El stock ya se descontó y la cuenta por cobrar quedó creada." : "");
  const [ocupado, setOcupado] = useState(false);

  const cargar = useCallback(() => api<Venta>(`/ventas/${id}`).then(setVenta).catch(() => setError("No se encontró la venta.")), [id]);
  useEffect(() => {
    cargar();
  }, [cargar]);

  async function accion(ruta: string, cuerpo: object, mensaje: string) {
    setError("");
    setAviso("");
    setOcupado(true);
    try {
      setVenta(await api<Venta>(`/ventas/${id}/${ruta}`, { method: "POST", body: JSON.stringify(cuerpo) }));
      setAviso(mensaje);
      return true;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar. Probá de nuevo.");
      return false;
    } finally {
      setOcupado(false);
    }
  }

  if (!venta) return error ? <Aviso tipo="error">{error}</Aviso> : <p className="text-stone-500">Cargando…</p>;
  const estado = ESTADO_VENTA[venta.estado_venta];
  const cuenta = venta.cuenta;
  const anulada = venta.estado_venta === "anulada";
  const especial = venta.precio_unitario !== venta.precio_de_lista;

  return (
    <div className="space-y-5">
      <Link href="/ventas" className="inline-flex items-center gap-1 text-sm text-stone-600 hover:text-stone-900">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Ventas
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl font-semibold">{venta.codigo}</h2>
        <Insignia color={estado.color}>{estado.nombre}</Insignia>
        <span className="text-sm text-stone-500">{fechaCorta(venta.fecha)} · cargó {venta.creado_por_nombre ?? "—"}</span>
      </div>
      {aviso && <Aviso tipo="ok">{aviso}</Aviso>}
      {error && <Aviso tipo="error">{error}</Aviso>}
      {anulada && <Aviso tipo="alerta">Venta anulada{venta.motivo_estado && `: “${venta.motivo_estado}”`}. El stock volvió a sus lotes.</Aviso>}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tarjeta titulo="Cliente" valor={<Link href={`/ventas/clientes/${venta.cliente}`} className="text-lg text-campo-800 hover:underline">{venta.cliente_nombre}</Link>} />
        <Tarjeta titulo={NOMBRE_PRODUCTO[venta.producto]} valor={cantidadVenta(venta.cantidad, venta.unidad)}
          detalle={`${gs(venta.precio_unitario)} por ${venta.unidad === "l" ? "L" : "kg"}${especial ? ` (lista ${gs(venta.precio_de_lista)})` : ""}`} />
        <Tarjeta titulo="Total" valor={gs(venta.total)} />
        {cuenta && (
          <Tarjeta titulo="Saldo" valor={gs(cuenta.saldo)}
            detalle={cuenta.estado === "anulada" ? "Cuenta anulada" : cuenta.saldo === 0 ? "Cobrada" :
              `${vencida(cuenta.vencimiento, hoyISO()) ? "Vencida el" : "Vence el"} ${fechaCorta(cuenta.vencimiento)}`} />
        )}
      </div>

      <section className="rounded-2xl border border-stone-200 bg-white p-5">
        <h3 className="mb-2 font-semibold">Salió de los lotes</h3>
        <ul className="divide-y divide-stone-100 text-sm">
          {venta.lotes.map((l) => (
            <li key={l.lote + l.cantidad} className="flex justify-between py-1.5">
              <Link href={l.tipo === "queso" ? `/queso/${l.lote}` : `/leche/lotes/${l.lote}`} className="text-campo-800 hover:underline">{l.codigo}</Link>
              <span className="tabular-nums">{cantidadVenta(l.cantidad, l.tipo === "queso" ? "kg" : "l")}</span>
            </li>
          ))}
        </ul>
        {venta.observaciones && <p className="mt-3 text-sm text-stone-600">“{venta.observaciones}”</p>}
      </section>

      {!anulada && (
        <div className="space-y-3">
          {!venta.fecha_entrega && puede("ventas.venta.registrar") && (
            <button disabled={ocupado} onClick={() => accion("entregar", {}, "Marcada como entregada.")} className={`${botonSecundario} flex w-full items-center justify-center gap-2`}>
              <Truck className="h-5 w-5" aria-hidden /> Marcar como entregada
            </button>
          )}
          {venta.fecha_entrega && <p className="text-sm text-stone-600">Entregada el {fechaHora(venta.fecha_entrega)}.</p>}
          {cuenta && cuenta.saldo > 0 && puede("ventas.cobro.registrar") && (
            <Cobrar saldo={cuenta.saldo} ocupado={ocupado} onCobrar={(c) => accion("cobrar", c, "Cobro registrado.")} />
          )}
          {puede("ventas.venta.aprobar") && (
            <Anular ocupado={ocupado} tieneCobros={!!cuenta && cuenta.cobrado > 0} onAnular={(motivo) => accion("anular", { motivo }, "Venta anulada.")} />
          )}
        </div>
      )}
      {cuenta && <p className="text-xs text-stone-500">Cuenta por cobrar: {ESTADO_CUENTA[cuenta.estado].nombre.toLowerCase()} · cobrado {gs(cuenta.cobrado)} de {gs(cuenta.monto)}.</p>}
    </div>
  );
}

function Cobrar({ saldo, ocupado, onCobrar }: { saldo: number; ocupado: boolean; onCobrar: (c: object) => Promise<boolean> }) {
  const [monto, setMonto] = useState(String(saldo));
  const [medio, setMedio] = useState("efectivo");
  const [referencia, setReferencia] = useState("");
  useEffect(() => setMonto(String(saldo)), [saldo]);
  const valor = Number(monto || 0);
  return (
    <section className="space-y-3 rounded-2xl border border-stone-200 bg-white p-5">
      <h3 className="font-semibold">Registrar cobro</h3>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="monto" className="mb-1 block text-sm font-medium">Monto (Gs.)</label>
          <input id="monto" inputMode="numeric" value={monto} onChange={(e) => setMonto(e.target.value.replace(/\D/g, ""))} className={`${estiloInput} tabular-nums`} />
        </div>
        <div>
          <label htmlFor="medio" className="mb-1 block text-sm font-medium">Medio</label>
          <select id="medio" value={medio} onChange={(e) => setMedio(e.target.value)} className={estiloInput}>
            {MEDIOS.map((m) => <option key={m.valor} value={m.valor}>{m.nombre}</option>)}
          </select>
        </div>
      </div>
      {medio !== "efectivo" && (
        <input aria-label="Referencia" value={referencia} onChange={(e) => setReferencia(e.target.value)} placeholder="N.º de transferencia o referencia" className={estiloInput} />
      )}
      {valor > saldo && <Aviso tipo="error">El saldo es {gs(saldo)}: no se puede cobrar más.</Aviso>}
      <button disabled={ocupado || valor <= 0 || valor > saldo} onClick={() => onCobrar({ monto: valor, medio, referencia })} className={`${botonPrimario} w-full`}>
        Cobrar {gs(valor)}{valor < saldo && valor > 0 ? ` (queda ${gs(saldo - valor)})` : ""}
      </button>
    </section>
  );
}

function Anular({ ocupado, tieneCobros, onAnular }: { ocupado: boolean; tieneCobros: boolean; onAnular: (m: string) => Promise<boolean> }) {
  const [abierto, setAbierto] = useState(false);
  const [motivo, setMotivo] = useState("");
  if (!abierto) {
    return <button onClick={() => setAbierto(true)} className="text-sm font-medium text-red-700 hover:underline">Anular venta</button>;
  }
  return (
    <div className="space-y-2 rounded-2xl border border-red-200 bg-red-50 p-4">
      <label htmlFor="motivo" className="block text-sm font-medium text-red-900">¿Por qué se anula?</label>
      <input id="motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} className={estiloInput} />
      <p className="text-xs text-red-800">
        El queso o la leche vuelven a su lote y la cuenta por cobrar se anula.
        {tieneCobros && " Esta venta tiene cobros: primero anulalos desde Cuentas por cobrar."}
      </p>
      <div className="flex gap-2">
        <button disabled={ocupado || !motivo.trim()} onClick={async () => (await onAnular(motivo)) && setAbierto(false)}
          className="rounded-lg bg-red-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">Anular venta</button>
        <button onClick={() => setAbierto(false)} className="px-3 py-2 text-sm">Volver</button>
      </div>
    </div>
  );
}
