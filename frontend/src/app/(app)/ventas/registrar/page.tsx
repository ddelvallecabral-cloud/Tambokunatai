"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { Check, Search, UserPlus, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fechaCorta, hoyISO } from "@/lib/leche";
import {
  CONDICIONES, gs, MEDIOS, NOMBRE_CONDICION, NOMBRE_TIPO_CLIENTE, PRODUCTOS, TIPOS_CLIENTE,
  type Cliente, type CondicionPago, type Cotizacion, type Producto, type TipoCliente, type Venta,
} from "@/lib/ventas";
import { Aviso, botonPrimario, botonSecundario, estiloInput } from "@/components/ui";

const limpiar = (v: string) => v.replace(/[^0-9.,]/g, "");
const num = (v: string) => Number((v || "0").replace(",", "."));
const n2 = new Intl.NumberFormat("es-PY", { maximumFractionDigits: 2 });

export default function Registrar() {
  return (
    <Suspense fallback={<p className="text-stone-500">Cargando…</p>}>
      <RegistrarVenta />
    </Suspense>
  );
}

function RegistrarVenta() {
  const { puede } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [producto, setProducto] = useState<Producto>("queso");
  const [cant, setCant] = useState("");
  const [fecha, setFecha] = useState(hoyISO);
  const [cotizacion, setCotizacion] = useState<Cotizacion | null>(null);
  const [precioManual, setPrecioManual] = useState("");
  const [entregada, setEntregada] = useState(true);
  const [cobrar, setCobrar] = useState(false);
  const [medio, setMedio] = useState("efectivo");
  const [observaciones, setObservaciones] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [id] = useState(() => crypto.randomUUID());
  const cambiaPrecios = puede("ventas.precio.gestionar");
  const unidad = PRODUCTOS.find((p) => p.valor === producto)!.unidad;

  useEffect(() => {
    const pre = params.get("cliente");
    if (pre) api<Cliente>(`/clientes/${pre}`).then(setCliente).catch(() => undefined);
  }, [params]);

  useEffect(() => {
    const t = setTimeout(() => {
      const q = new URLSearchParams({ producto, cantidad: String(num(cant)) });
      if (cliente) q.set("cliente", cliente.id);
      api<Cotizacion>(`/precios/cotizar?${q}`).then(setCotizacion);
    }, 250);
    return () => clearTimeout(t);
  }, [cliente, producto, cant]);

  useEffect(() => {
    if (cliente) setCobrar(cliente.condicion_pago === "contado");
  }, [cliente]);

  const cantidad = num(cant);
  const stock = cotizacion ? Number(cotizacion.stock_disponible) : 0;
  const precio = precioManual ? num(precioManual) : cotizacion?.precio_unitario ?? 0;
  const total = Math.round(cantidad * precio);
  const sinStock = cotizacion != null && cantidad > stock;

  // De qué lotes va a salir: del más viejo al más nuevo, igual que en el servidor.
  const salida = useMemo(() => {
    let resta = cantidad;
    const filas: { codigo: string; fecha: string; cantidad: number }[] = [];
    for (const l of cotizacion?.lotes_disponibles ?? []) {
      if (resta <= 0) break;
      const tomar = Math.min(resta, Number(l.disponible));
      filas.push({ codigo: l.codigo, fecha: l.fecha, cantidad: tomar });
      resta -= tomar;
    }
    return filas;
  }, [cotizacion, cantidad]);

  async function registrar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!cliente) return setError("Elegí el cliente.");
    if (cantidad <= 0) return setError("Cargá la cantidad.");
    if (sinStock) return setError(`No hay stock suficiente: hay ${n2.format(stock)} ${unidad} disponibles.`);
    setOcupado(true);
    try {
      const venta = await api<Venta>("/ventas", {
        method: "POST",
        body: JSON.stringify({
          id, cliente: cliente.id, producto, cantidad: String(cantidad), fecha,
          precio_unitario: precioManual ? Math.round(num(precioManual)) : null,
          entregada, cobrar_ahora: cobrar, medio, observaciones,
        }),
      });
      router.push(`/ventas/${venta.id}?registrada=1`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo registrar la venta. Revisá la señal y probá de nuevo.");
      setOcupado(false);
    }
  }

  return (
    <form onSubmit={registrar} className="space-y-5">
      <section className="space-y-3 rounded-2xl border border-stone-200 bg-white p-5">
        <h2 className="font-semibold">1. Cliente</h2>
        {cliente ? (
          <div className="flex items-center justify-between gap-3 rounded-xl bg-campo-50 px-4 py-3">
            <div>
              <p className="font-medium">{cliente.nombre}</p>
              <p className="text-sm text-stone-600">{NOMBRE_TIPO_CLIENTE[cliente.tipo]} · {NOMBRE_CONDICION[cliente.condicion_pago]}
                {cliente.saldo_pendiente > 0 && <span className="text-amber-800"> · debe {gs(cliente.saldo_pendiente)}</span>}</p>
            </div>
            <button type="button" onClick={() => setCliente(null)} className="rounded-lg p-2 text-stone-500 hover:bg-white" aria-label="Cambiar cliente">
              <X className="h-5 w-5" />
            </button>
          </div>
        ) : (
          <BuscarCliente onElegir={setCliente} puedeCrear={puede("ventas.cliente.gestionar")} />
        )}
      </section>

      <section className="space-y-4 rounded-2xl border border-stone-200 bg-white p-5">
        <h2 className="font-semibold">2. Producto y cantidad</h2>
        <div className="grid grid-cols-2 gap-2" role="radiogroup" aria-label="Producto">
          {PRODUCTOS.map((p) => (
            <button key={p.valor} type="button" role="radio" aria-checked={producto === p.valor}
              onClick={() => { setProducto(p.valor); setPrecioManual(""); }}
              className={`rounded-xl border px-4 py-3 font-medium ${producto === p.valor ? "border-campo-600 bg-campo-50 text-campo-900" : "border-stone-300 bg-white text-stone-700"}`}>
              {p.nombre}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="cantidad" className="mb-1 block text-sm font-medium">Cantidad ({unidad})</label>
            <input id="cantidad" inputMode="decimal" value={cant} onChange={(e) => setCant(limpiar(e.target.value))}
              className={`${estiloInput} text-lg tabular-nums`} placeholder="0" />
          </div>
          <div>
            <label htmlFor="fecha" className="mb-1 block text-sm font-medium">Fecha</label>
            <input id="fecha" type="date" value={fecha} max={hoyISO()} onChange={(e) => setFecha(e.target.value)} className={estiloInput} />
          </div>
        </div>
        {cotizacion && (
          <p className={`text-sm ${sinStock ? "font-medium text-red-700" : "text-stone-600"}`}>
            Disponible para vender: {n2.format(stock)} {unidad}
            {producto === "leche" && " (leche de los últimos 3 días)"}
            {sinStock && ` · faltan ${n2.format(cantidad - stock)} ${unidad}`}
          </p>
        )}
        {salida.length > 0 && !sinStock && (
          <p className="text-xs text-stone-500">
            Sale de: {salida.map((s) => `${s.codigo} (${n2.format(s.cantidad)} ${unidad}, ${fechaCorta(s.fecha)})`).join(" · ")}
          </p>
        )}
      </section>

      <section className="space-y-4 rounded-2xl border border-stone-200 bg-white p-5">
        <h2 className="font-semibold">3. Precio y cobro</h2>
        {cotizacion?.error_precio ? (
          <Aviso tipo="alerta">{cotizacion.error_precio}</Aviso>
        ) : (
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm text-stone-500">Precio de lista por {unidad}</p>
              <p className="text-lg font-medium tabular-nums">{gs(cotizacion?.precio_unitario)}</p>
              {cotizacion?.regla && (
                <p className="text-xs text-stone-500">
                  {cotizacion.regla.tipo_cliente ? `Precio ${NOMBRE_TIPO_CLIENTE[cotizacion.regla.tipo_cliente as TipoCliente].toLowerCase()}` : "Precio base"}
                  {Number(cotizacion.regla.cantidad_minima) > 0 && ` · desde ${n2.format(Number(cotizacion.regla.cantidad_minima))} ${unidad}`}
                </p>
              )}
            </div>
            <div className="text-right">
              <p className="text-sm text-stone-500">Total</p>
              <p className="text-3xl font-semibold tabular-nums" aria-live="polite">{gs(total)}</p>
            </div>
          </div>
        )}
        {cambiaPrecios && (
          <div>
            <label htmlFor="precio" className="mb-1 block text-sm font-medium">Precio especial por {unidad} (opcional)</label>
            <input id="precio" inputMode="numeric" value={precioManual} onChange={(e) => setPrecioManual(e.target.value.replace(/\D/g, ""))}
              className={estiloInput} placeholder="Dejalo vacío para usar el de lista" />
          </div>
        )}
        <label className="flex items-center gap-3 text-sm">
          <input type="checkbox" checked={entregada} onChange={(e) => setEntregada(e.target.checked)} className="h-5 w-5" />
          Ya se entregó
        </label>
        {puede("ventas.cobro.registrar") && (
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-3 text-sm">
              <input type="checkbox" checked={cobrar} onChange={(e) => setCobrar(e.target.checked)} className="h-5 w-5" />
              Se cobró todo ahora
            </label>
            {cobrar && (
              <select aria-label="Medio de pago" value={medio} onChange={(e) => setMedio(e.target.value)} className={`${estiloInput} w-auto py-1.5`}>
                {MEDIOS.map((m) => <option key={m.valor} value={m.valor}>{m.nombre}</option>)}
              </select>
            )}
          </div>
        )}
        {!cobrar && cliente && (
          <p className="text-xs text-stone-500">Queda en cuentas por cobrar ({NOMBRE_CONDICION[cliente.condicion_pago].toLowerCase()}).</p>
        )}
        <div>
          <label htmlFor="obs" className="mb-1 block text-sm font-medium">Observaciones</label>
          <input id="obs" value={observaciones} onChange={(e) => setObservaciones(e.target.value)} className={estiloInput} />
        </div>
      </section>

      {error && <Aviso tipo="error">{error}</Aviso>}
      <button type="submit" disabled={ocupado || !cliente || cantidad <= 0 || sinStock || !precio} className={`${botonPrimario} w-full`}>
        {ocupado ? "Registrando…" : `Registrar venta${total ? ` por ${gs(total)}` : ""}`}
      </button>
    </form>
  );
}

function BuscarCliente({ onElegir, puedeCrear }: { onElegir: (c: Cliente) => void; puedeCrear: boolean }) {
  const [texto, setTexto] = useState("");
  const [resultados, setResultados] = useState<Cliente[] | null>(null);
  const [nuevo, setNuevo] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => {
      api<{ results: Cliente[] }>(`/clientes?activo=1&page_size=8&buscar=${encodeURIComponent(texto.trim())}`).then((p) => setResultados(p.results));
    }, 200);
    return () => clearTimeout(t);
  }, [texto]);

  if (nuevo) return <ClienteRapido nombre={texto} onCreado={onElegir} onCancelar={() => setNuevo(false)} />;
  return (
    <div className="space-y-2">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-3 h-5 w-5 text-stone-400" aria-hidden />
        <input aria-label="Buscar cliente" value={texto} onChange={(e) => setTexto(e.target.value)} autoFocus
          placeholder="Nombre, RUC o teléfono" className={`${estiloInput} pl-10`} />
      </div>
      {resultados && (
        <ul className="divide-y divide-stone-100 rounded-xl border border-stone-200">
          {resultados.map((c) => (
            <li key={c.id}>
              <button type="button" onClick={() => onElegir(c)} className="flex w-full items-center justify-between gap-3 px-4 py-2.5 text-left hover:bg-stone-50">
                <span>
                  <span className="font-medium">{c.nombre}</span>
                  <span className="block text-xs text-stone-500">{NOMBRE_TIPO_CLIENTE[c.tipo]}{c.telefono && ` · ${c.telefono}`}</span>
                </span>
                {c.saldo_pendiente > 0 && <span className="text-xs text-amber-800">debe {gs(c.saldo_pendiente)}</span>}
              </button>
            </li>
          ))}
          {resultados.length === 0 && <li className="px-4 py-3 text-sm text-stone-500">No hay clientes con ese nombre.</li>}
        </ul>
      )}
      {puedeCrear && (
        <button type="button" onClick={() => setNuevo(true)} className="flex items-center gap-2 text-sm font-medium text-campo-700">
          <UserPlus className="h-4 w-4" aria-hidden /> Cliente nuevo
        </button>
      )}
    </div>
  );
}

function ClienteRapido({ nombre: inicial, onCreado, onCancelar }: { nombre: string; onCreado: (c: Cliente) => void; onCancelar: () => void }) {
  const [nombre, setNombre] = useState(inicial);
  const [tipo, setTipo] = useState<TipoCliente>("minorista");
  const [telefono, setTelefono] = useState("");
  const [condicion, setCondicion] = useState<CondicionPago>("contado");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function crear() {
    setError("");
    setOcupado(true);
    try {
      onCreado(await api<Cliente>("/clientes", { method: "POST", body: JSON.stringify({ nombre, tipo, telefono, condicion_pago: condicion }) }));
    } catch (err) {
      setError(err instanceof ApiError ? Object.values((err.datos ?? {}) as Record<string, string[]>).flat()[0] ?? err.message : "No se pudo crear.");
      setOcupado(false);
    }
  }

  return (
    <div className="space-y-3 rounded-xl border border-stone-200 p-4">
      <p className="text-sm font-medium">Cliente nuevo</p>
      <input aria-label="Nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre o razón social" className={estiloInput} />
      <div className="grid grid-cols-2 gap-2">
        <select aria-label="Tipo" value={tipo} onChange={(e) => setTipo(e.target.value as TipoCliente)} className={estiloInput}>
          {TIPOS_CLIENTE.map((t) => <option key={t.valor} value={t.valor}>{t.nombre}</option>)}
        </select>
        <select aria-label="Condición de pago" value={condicion} onChange={(e) => setCondicion(e.target.value as CondicionPago)} className={estiloInput}>
          {CONDICIONES.map((t) => <option key={t.valor} value={t.valor}>{t.nombre}</option>)}
        </select>
      </div>
      <input aria-label="Teléfono" value={telefono} onChange={(e) => setTelefono(e.target.value)} placeholder="Teléfono (opcional)" inputMode="tel" className={estiloInput} />
      {error && <Aviso tipo="error">{error}</Aviso>}
      <div className="flex gap-2">
        <button type="button" disabled={ocupado || !nombre.trim()} onClick={crear} className={`${botonPrimario} flex items-center gap-2 py-2`}>
          <Check className="h-4 w-4" aria-hidden /> Crear y usar
        </button>
        <button type="button" onClick={onCancelar} className={`${botonSecundario} py-2`}>Volver</button>
      </div>
    </div>
  );
}
