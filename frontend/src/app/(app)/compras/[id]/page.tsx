"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fechaHora } from "@/lib/formato";
import { fechaCorta, hoyISO } from "@/lib/leche";
import { gs } from "@/lib/ventas";
import { primerError } from "@/lib/usuarios";
import { ESTADO_CUENTA_PAGAR, MEDIOS_PAGO, NOMBRE_CONDICION_COMPRA, type Compra } from "@/lib/egresos";
import { ElegirComprobante, VerComprobante } from "@/components/Comprobante";
import { Aviso, botonPrimario, estiloInput, Insignia } from "@/components/ui";

const NOMBRE_MEDIO = Object.fromEntries(MEDIOS_PAGO.map((m) => [m.valor, m.nombre])) as Record<string, string>;

export default function DetalleCompra() {
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
  const [c, setC] = useState<Compra | null>(null);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [version, setVersion] = useState(0);
  const [archivo, setArchivo] = useState<File | null>(null);

  useEffect(() => {
    api<Compra>(`/compras/${id}`).then((x) => {
      setC(x);
      if (params.get("cargada")) {
        setAviso(params.get("sin_foto") ? "Compra guardada y stock actualizado, pero la foto no se pudo subir. Probá de nuevo abajo." : "Compra guardada. Los insumos ya entraron al inventario.");
      }
    }).catch(() => setError("No se encontró la compra."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function enviar(ruta: string, cuerpo: object | FormData, mensaje: string) {
    setError(""); setAviso("");
    try {
      setC(await api<Compra>(`/compras/${id}/${ruta}`, { method: "POST", body: cuerpo instanceof FormData ? cuerpo : JSON.stringify(cuerpo) }));
      setAviso(mensaje);
      return true;
    } catch (err) {
      setError(err instanceof ApiError ? primerError(err.datos, err.message) : "No se pudo guardar.");
      return false;
    }
  }

  async function subirFoto() {
    if (!archivo) return;
    const datos = new FormData();
    datos.append("comprobante", archivo);
    if (await enviar("comprobante", datos, "Comprobante guardado.")) { setArchivo(null); setVersion((v) => v + 1); }
  }

  if (!c) return error ? <Aviso tipo="error">{error}</Aviso> : <p className="text-stone-500">Cargando…</p>;
  const cuenta = c.cuenta;
  const anulada = c.estado_compra === "anulada";
  const pagosActivos = cuenta.pagos.filter((p) => !p.anulado);

  return (
    <div className="space-y-5">
      <Link href="/compras" className="inline-flex items-center gap-1 text-sm text-stone-600 hover:text-stone-900">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Compras
      </Link>
      {aviso && <Aviso tipo="ok">{aviso}</Aviso>}
      {error && <Aviso tipo="error">{error}</Aviso>}
      {anulada && <Aviso tipo="alerta">Compra anulada: “{c.motivo_estado}”. El stock se descontó de nuevo.</Aviso>}

      <section className="space-y-4 rounded-2xl border border-stone-200 bg-white p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm text-stone-500">{c.codigo} · {fechaCorta(c.fecha)} · {NOMBRE_CONDICION_COMPRA[c.condicion]}</p>
            <h2 className="text-xl font-semibold">{c.proveedor_nombre}</h2>
            {c.factura && <p className="text-sm text-stone-600">Factura n.º {c.factura}</p>}
            <p className="text-xs text-stone-500">Cargada por {c.creado_por_nombre ?? "—"} · {fechaHora(c.fecha_creacion)}</p>
          </div>
          <p className="text-3xl font-semibold tabular-nums">{gs(c.total)}</p>
        </div>
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-stone-500">
            <tr><th className="py-1">Insumo</th><th className="py-1 text-right">Cantidad</th><th className="py-1 text-right">Precio</th><th className="py-1 text-right">Subtotal</th></tr>
          </thead>
          <tbody className="divide-y divide-stone-100">
            {c.items.map((i) => (
              <tr key={i.insumo}>
                <td className="py-2">
                  <Link href="/inventario" className="font-medium hover:underline">{i.insumo_nombre}</Link>
                  {i.lote_proveedor && <span className="block text-xs text-stone-500">Lote {i.lote_proveedor}</span>}
                </td>
                <td className="py-2 text-right tabular-nums">{Number(i.cantidad).toLocaleString("es-PY")} {i.unidad}</td>
                <td className="py-2 text-right tabular-nums">{gs(i.precio_unitario)}</td>
                <td className="py-2 text-right font-medium tabular-nums">{gs(i.subtotal)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {c.observaciones && <p className="text-sm text-stone-600">{c.observaciones}</p>}
      </section>

      <section className="space-y-3 rounded-2xl border border-stone-200 bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-semibold">Cuenta por pagar</h3>
          <Insignia color={ESTADO_CUENTA_PAGAR[cuenta.estado].color}>{ESTADO_CUENTA_PAGAR[cuenta.estado].nombre}</Insignia>
        </div>
        <dl className="grid grid-cols-3 gap-3 text-sm">
          <div><dt className="text-stone-500">Total</dt><dd className="font-medium tabular-nums">{gs(cuenta.monto)}</dd></div>
          <div><dt className="text-stone-500">Pagado</dt><dd className="font-medium tabular-nums">{gs(cuenta.pagado)}</dd></div>
          <div><dt className="text-stone-500">Saldo · vence {fechaCorta(cuenta.vencimiento)}</dt><dd className="font-semibold tabular-nums">{gs(cuenta.saldo)}</dd></div>
        </dl>
        {cuenta.pagos.length > 0 && (
          <ul className="divide-y divide-stone-100 border-t border-stone-100 text-sm">
            {cuenta.pagos.map((p) => (
              <li key={p.id} className={`flex flex-wrap justify-between gap-2 py-2 ${p.anulado ? "text-stone-400 line-through" : ""}`}>
                <span>{fechaCorta(p.fecha)} · {NOMBRE_MEDIO[p.medio] ?? p.medio}{p.referencia && ` · ${p.referencia}`} · {p.usuario_nombre}</span>
                <span className="tabular-nums">{gs(p.monto)}</span>
              </li>
            ))}
          </ul>
        )}
        {!anulada && cuenta.saldo > 0 && puede("compras.pago.registrar") && <Pagar saldo={cuenta.saldo} onPagar={(d) => enviar("pagar", d, "Pago registrado.")} />}
      </section>

      <section className="space-y-3 rounded-2xl border border-stone-200 bg-white p-5">
        <h3 className="font-semibold">Comprobante</h3>
        {c.tiene_comprobante ? <VerComprobante key={version} ruta={`/compras/${c.id}/comprobante`} tipo={c.tipo_comprobante} />
          : <p className="text-sm text-stone-500">No se adjuntó foto de la factura.</p>}
        {!anulada && puede("compras.compra.registrar") && (
          <div className="space-y-2">
            <ElegirComprobante archivo={archivo} onCambio={setArchivo} />
            {archivo && <button onClick={subirFoto} className={botonPrimario}>{c.tiene_comprobante ? "Reemplazar comprobante" : "Guardar comprobante"}</button>}
          </div>
        )}
      </section>

      {!anulada && puede("compras.compra.aprobar") && (
        pagosActivos.length > 0
          ? <p className="text-sm text-stone-500">Para anular la compra primero anulá sus pagos desde Cuentas por pagar.</p>
          : <Anular onAnular={(m) => enviar("anular", { motivo: m }, "Compra anulada. El stock se descontó.")} />
      )}
    </div>
  );
}

function Pagar({ saldo, onPagar }: { saldo: number; onPagar: (d: object) => Promise<boolean> }) {
  const [monto, setMonto] = useState(String(saldo));
  const [fecha, setFecha] = useState(hoyISO());
  const [medio, setMedio] = useState("efectivo");
  const [referencia, setReferencia] = useState("");
  const [ocupado, setOcupado] = useState(false);
  return (
    <form onSubmit={async (e) => { e.preventDefault(); setOcupado(true); await onPagar({ monto: Number(monto), fecha, medio, referencia }); setOcupado(false); }}
      className="grid grid-cols-2 gap-2 rounded-xl bg-stone-50 p-3 sm:grid-cols-5">
      <div>
        <label htmlFor="p-monto" className="mb-1 block text-xs">Monto (Gs.)</label>
        <input id="p-monto" inputMode="numeric" value={monto} onChange={(e) => setMonto(e.target.value.replace(/\D/g, ""))} className={estiloInput} />
      </div>
      <div>
        <label htmlFor="p-fecha" className="mb-1 block text-xs">Fecha</label>
        <input id="p-fecha" type="date" value={fecha} max={hoyISO()} onChange={(e) => setFecha(e.target.value)} className={estiloInput} />
      </div>
      <div>
        <label htmlFor="p-medio" className="mb-1 block text-xs">Medio</label>
        <select id="p-medio" value={medio} onChange={(e) => setMedio(e.target.value)} className={estiloInput}>
          {MEDIOS_PAGO.map((m) => <option key={m.valor} value={m.valor}>{m.nombre}</option>)}
        </select>
      </div>
      <div>
        <label htmlFor="p-ref" className="mb-1 block text-xs">Referencia</label>
        <input id="p-ref" value={referencia} onChange={(e) => setReferencia(e.target.value)} className={estiloInput} />
      </div>
      <button type="submit" disabled={ocupado || !Number(monto) || Number(monto) > saldo} className={`${botonPrimario} col-span-2 self-end sm:col-span-1`}>Registrar pago</button>
    </form>
  );
}

function Anular({ onAnular }: { onAnular: (m: string) => Promise<boolean> }) {
  const [abierto, setAbierto] = useState(false);
  const [motivo, setMotivo] = useState("");
  if (!abierto) return <button onClick={() => setAbierto(true)} className="text-sm font-medium text-red-700 hover:underline">Anular compra</button>;
  return (
    <div className="space-y-2 rounded-2xl border border-red-200 bg-red-50 p-4">
      <label htmlFor="motivo" className="block text-sm font-medium text-red-900">¿Por qué se anula? Se va a descontar el stock que entró.</label>
      <input id="motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} className={estiloInput} />
      <div className="flex gap-2">
        <button disabled={!motivo.trim()} onClick={async () => (await onAnular(motivo)) && setAbierto(false)} className="rounded-lg bg-red-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">Anular</button>
        <button onClick={() => setAbierto(false)} className="px-3 py-2 text-sm">Volver</button>
      </div>
    </div>
  );
}
