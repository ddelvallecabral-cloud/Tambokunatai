"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { hoyISO } from "@/lib/leche";
import { gs } from "@/lib/ventas";
import { primerError } from "@/lib/usuarios";
import type { Insumo } from "@/lib/inventario";
import { CONDICIONES_COMPRA, MEDIOS_PAGO, type Compra, type Proveedor } from "@/lib/egresos";
import { useAuth } from "@/lib/auth";
import { ElegirComprobante } from "@/components/Comprobante";
import { Aviso, botonPrimario, botonSecundario, estiloInput } from "@/components/ui";

type Fila = { clave: number; insumo: string; cantidad: string; precio: string; lote: string };
const filaVacia = (clave: number): Fila => ({ clave, insumo: "", cantidad: "", precio: "", lote: "" });

export default function RegistrarCompra() {
  const router = useRouter();
  const { puede } = useAuth();
  const [id] = useState(() => crypto.randomUUID());
  const [proveedores, setProveedores] = useState<Proveedor[] | null>(null);
  const [insumos, setInsumos] = useState<Insumo[]>([]);
  const [proveedor, setProveedor] = useState("");
  const [fecha, setFecha] = useState(hoyISO());
  const [factura, setFactura] = useState("");
  const [condicion, setCondicion] = useState("contado");
  const [pagada, setPagada] = useState(false);
  const [medio, setMedio] = useState("efectivo");
  const [observaciones, setObservaciones] = useState("");
  const [filas, setFilas] = useState<Fila[]>([filaVacia(1)]);
  const [archivo, setArchivo] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    api<{ results: Proveedor[] }>("/proveedores?activo=1&page_size=300").then((p) => setProveedores(p.results));
    api<{ results: Insumo[] }>("/insumos?page_size=300").then((p) => setInsumos(p.results.filter((i) => i.activo)));
  }, []);

  const cambiarFila = (clave: number, campo: keyof Fila, valor: string) =>
    setFilas((fs) => fs.map((f) => (f.clave === clave ? { ...f, [campo]: valor } : f)));
  const subtotal = (f: Fila) => Math.round(Number(f.cantidad || 0) * Number(f.precio || 0));
  const total = filas.reduce((s, f) => s + subtotal(f), 0);
  const completas = filas.filter((f) => f.insumo && Number(f.cantidad) > 0 && Number(f.precio) > 0);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!proveedor) return setError("Elegí el proveedor.");
    if (completas.length !== filas.length) return setError("Completá insumo, cantidad y precio en cada fila (o quitá la fila vacía).");
    setOcupado(true);
    try {
      let compra = await api<Compra>("/compras", {
        method: "POST",
        body: JSON.stringify({
          id, proveedor, fecha, factura, condicion, pagada: condicion === "contado" && pagada, medio, observaciones,
          items: filas.map((f) => ({ insumo: f.insumo, cantidad: f.cantidad, precio_unitario: Number(f.precio), lote_proveedor: f.lote })),
        }),
      });
      if (archivo) {
        const datos = new FormData();
        datos.append("comprobante", archivo);
        try {
          compra = await api<Compra>(`/compras/${compra.id}/comprobante`, { method: "POST", body: datos });
        } catch {
          router.push(`/compras/${compra.id}?cargada=1&sin_foto=1`);
          return;
        }
      }
      router.push(`/compras/${compra.id}?cargada=1`);
    } catch (err) {
      setError(err instanceof ApiError ? primerError(err.datos, err.message) : "No se pudo guardar. Revisá la señal y probá de nuevo.");
      setOcupado(false);
    }
  }

  if (proveedores && proveedores.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-600">
        Todavía no hay proveedores. <Link href="/compras/proveedores" className="font-medium text-campo-700 hover:underline">Cargá el primero</Link>.
      </p>
    );
  }

  return (
    <form onSubmit={guardar} className="space-y-5 rounded-2xl border border-stone-200 bg-white p-5">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="sm:col-span-2">
          <label htmlFor="c-prov" className="mb-1 block text-sm font-medium">Proveedor</label>
          <select id="c-prov" value={proveedor} onChange={(e) => setProveedor(e.target.value)} className={estiloInput} required>
            <option value="">Elegí…</option>
            {proveedores?.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="c-fecha" className="mb-1 block text-sm font-medium">Fecha</label>
          <input id="c-fecha" type="date" value={fecha} max={hoyISO()} onChange={(e) => setFecha(e.target.value)} className={estiloInput} />
        </div>
      </div>

      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Insumos comprados</legend>
        {filas.map((f, n) => {
          const ins = insumos.find((i) => i.id === f.insumo);
          return (
            <div key={f.clave} className="grid grid-cols-6 items-end gap-2 rounded-xl bg-stone-50 p-3" data-testid="fila-compra">
              <div className="col-span-6 sm:col-span-2">
                <label htmlFor={`i-${f.clave}`} className="mb-1 block text-xs">Insumo</label>
                <select id={`i-${f.clave}`} value={f.insumo} onChange={(e) => cambiarFila(f.clave, "insumo", e.target.value)} className={estiloInput}>
                  <option value="">Elegí…</option>
                  {insumos.map((i) => <option key={i.id} value={i.id}>{i.nombre} ({i.unidad})</option>)}
                </select>
              </div>
              <div className="col-span-2 sm:col-span-1">
                <label htmlFor={`q-${f.clave}`} className="mb-1 block text-xs">Cantidad{ins && ` (${ins.unidad})`}</label>
                <input id={`q-${f.clave}`} inputMode="decimal" value={f.cantidad} onChange={(e) => cambiarFila(f.clave, "cantidad", e.target.value.replace(",", ".").replace(/[^\d.]/g, ""))} className={estiloInput} />
              </div>
              <div className="col-span-2 sm:col-span-1">
                <label htmlFor={`p-${f.clave}`} className="mb-1 block text-xs">Precio unitario (Gs.)</label>
                <input id={`p-${f.clave}`} inputMode="numeric" value={f.precio} onChange={(e) => cambiarFila(f.clave, "precio", e.target.value.replace(/\D/g, ""))} className={estiloInput} />
              </div>
              <div className="col-span-2 sm:col-span-1">
                <label htmlFor={`l-${f.clave}`} className="mb-1 block text-xs">Lote (opcional)</label>
                <input id={`l-${f.clave}`} value={f.lote} onChange={(e) => cambiarFila(f.clave, "lote", e.target.value)} className={estiloInput} />
              </div>
              <div className="col-span-6 flex items-center justify-between gap-2 sm:col-span-1 sm:flex-col sm:items-end">
                <span className="text-sm font-medium tabular-nums">{gs(subtotal(f))}</span>
                {filas.length > 1 && (
                  <button type="button" onClick={() => setFilas((fs) => fs.filter((x) => x.clave !== f.clave))} className="text-red-700" aria-label={`Quitar fila ${n + 1}`}>
                    <Trash2 className="h-4 w-4" aria-hidden />
                  </button>
                )}
              </div>
            </div>
          );
        })}
        <button type="button" onClick={() => setFilas((fs) => [...fs, filaVacia(Math.max(...fs.map((x) => x.clave)) + 1)])}
          className="inline-flex items-center gap-1 text-sm font-medium text-campo-700 hover:underline">
          <Plus className="h-4 w-4" aria-hidden /> Agregar otro insumo
        </button>
      </fieldset>

      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <label htmlFor="c-fact" className="mb-1 block text-sm font-medium">N.º de factura (opcional)</label>
          <input id="c-fact" value={factura} onChange={(e) => setFactura(e.target.value)} className={estiloInput} />
        </div>
        <div>
          <label htmlFor="c-cond" className="mb-1 block text-sm font-medium">Condición</label>
          <select id="c-cond" value={condicion} onChange={(e) => setCondicion(e.target.value)} className={estiloInput}>
            {CONDICIONES_COMPRA.map((c) => <option key={c.valor} value={c.valor}>{c.nombre}</option>)}
          </select>
        </div>
        {condicion === "contado" && puede("compras.pago.registrar") && (
          <div>
            <label className="mb-1 flex items-center gap-2 text-sm font-medium">
              <input type="checkbox" checked={pagada} onChange={(e) => setPagada(e.target.checked)} /> Ya se pagó
            </label>
            {pagada && (
              <select aria-label="Medio de pago" value={medio} onChange={(e) => setMedio(e.target.value)} className={estiloInput}>
                {MEDIOS_PAGO.map((m) => <option key={m.valor} value={m.valor}>{m.nombre}</option>)}
              </select>
            )}
          </div>
        )}
      </div>
      <div>
        <label htmlFor="c-obs" className="mb-1 block text-sm font-medium">Observaciones (opcional)</label>
        <input id="c-obs" value={observaciones} onChange={(e) => setObservaciones(e.target.value)} className={estiloInput} />
      </div>
      <div>
        <p className="mb-1 text-sm font-medium">Foto de la factura (opcional)</p>
        <ElegirComprobante archivo={archivo} onCambio={setArchivo} />
      </div>

      <p className="rounded-lg bg-campo-50 px-3 py-2 text-sm text-campo-900">
        Al guardar, los insumos entran al inventario y queda una cuenta por pagar al proveedor{condicion === "contado" && pagada ? " (ya pagada)" : ""}.
      </p>
      {error && <Aviso tipo="error">{error}</Aviso>}
      <div className="flex gap-2">
        <button type="submit" disabled={ocupado || completas.length === 0 || !proveedor} className={`${botonPrimario} flex-1`}>
          {ocupado ? "Guardando…" : `Confirmar compra${total ? ` de ${gs(total)}` : ""}`}
        </button>
        <Link href="/compras" className={botonSecundario}>Cancelar</Link>
      </div>
    </form>
  );
}
