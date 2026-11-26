"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { hoyISO } from "@/lib/leche";
import { CATEGORIAS, CENTROS, type Gasto, type Proveedor } from "@/lib/egresos";
import { gs } from "@/lib/ventas";
import { primerError } from "@/lib/usuarios";
import { ElegirComprobante } from "@/components/Comprobante";
import { Aviso, botonPrimario, estiloInput } from "@/components/ui";

/** Alta de un gasto o corrección de uno pendiente o rechazado. Va como formulario para llevar la foto. */
export function FormGasto({ gasto, umbral, onGuardado }: { gasto?: Gasto; umbral?: number; onGuardado: (g: Gasto) => void }) {
  const [id] = useState(() => crypto.randomUUID());
  const [fecha, setFecha] = useState(gasto?.fecha ?? hoyISO());
  const [categoria, setCategoria] = useState(gasto?.categoria ?? "");
  const [centro, setCentro] = useState(gasto?.centro_costo ?? "");
  const [monto, setMonto] = useState(gasto ? String(gasto.monto) : "");
  const [descripcion, setDescripcion] = useState(gasto?.descripcion ?? "");
  const [proveedor, setProveedor] = useState(gasto?.proveedor ?? "");
  const [numero, setNumero] = useState(gasto?.comprobante_numero ?? "");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [proveedores, setProveedores] = useState<Proveedor[] | null>(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    api<{ results: Proveedor[] }>("/proveedores?activo=1&page_size=300").then((p) => setProveedores(p.results)).catch(() => setProveedores(null));
  }, []);

  const valor = Number(monto || 0);
  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!categoria || !centro) return setError("Elegí la categoría y el centro de costo.");
    setOcupado(true);
    const datos = new FormData();
    if (!gasto) datos.append("id", id);
    datos.append("fecha", fecha);
    datos.append("categoria", categoria);
    datos.append("centro_costo", centro);
    datos.append("monto", String(valor));
    datos.append("descripcion", descripcion);
    datos.append("comprobante_numero", numero);
    if (proveedor) datos.append("proveedor", proveedor);
    if (archivo) datos.append("comprobante", archivo);
    try {
      onGuardado(await api<Gasto>(gasto ? `/gastos/${gasto.id}/corregir` : "/gastos", { method: "POST", body: datos }));
    } catch (err) {
      setError(err instanceof ApiError ? primerError(err.datos, err.message) : "No se pudo guardar. Revisá la señal y probá de nuevo.");
      setOcupado(false);
    }
  }

  return (
    <form onSubmit={guardar} className="space-y-4 rounded-2xl border border-stone-200 bg-white p-5">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="g-monto" className="mb-1 block text-sm font-medium">Monto (Gs.)</label>
          <input id="g-monto" inputMode="numeric" value={monto} onChange={(e) => setMonto(e.target.value.replace(/\D/g, ""))}
            className={`${estiloInput} text-lg tabular-nums`} placeholder="0" required />
          {valor > 0 && <p className="mt-1 text-xs text-stone-600">{gs(valor)}</p>}
        </div>
        <div>
          <label htmlFor="g-fecha" className="mb-1 block text-sm font-medium">Fecha</label>
          <input id="g-fecha" type="date" value={fecha} max={hoyISO()} onChange={(e) => setFecha(e.target.value)} className={estiloInput} />
        </div>
      </div>
      {umbral != null && valor > 0 && (
        <p className={`rounded-lg px-3 py-2 text-sm ${valor > umbral ? "bg-amber-50 text-amber-900" : "bg-campo-50 text-campo-900"}`}>
          {valor > umbral ? `Supera ${gs(umbral)}: va a quedar pendiente hasta que lo apruebe el Administrador.` : "Se aprueba solo al guardarlo."}
        </p>
      )}
      <div>
        <label htmlFor="g-desc" className="mb-1 block text-sm font-medium">¿En qué se gastó?</label>
        <input id="g-desc" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} className={estiloInput} placeholder="Ej.: vacuna aftosa para 12 vacas" required />
      </div>
      <fieldset>
        <legend className="mb-1 text-sm font-medium">Categoría</legend>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {CATEGORIAS.map((c) => (
            <button key={c.valor} type="button" aria-pressed={categoria === c.valor} onClick={() => setCategoria(c.valor)}
              className={`rounded-lg border px-2 py-2 text-sm ${categoria === c.valor ? "border-campo-600 bg-campo-50 font-medium text-campo-900" : "border-stone-300 bg-white"}`}>
              {c.nombre}
            </button>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend className="mb-1 text-sm font-medium">Centro de costo</legend>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          {CENTROS.map((c) => (
            <button key={c.valor} type="button" aria-pressed={centro === c.valor} onClick={() => setCentro(c.valor)}
              className={`rounded-lg border px-2 py-2 text-sm ${centro === c.valor ? "border-campo-600 bg-campo-50 font-medium text-campo-900" : "border-stone-300 bg-white"}`}>
              {c.nombre}
            </button>
          ))}
        </div>
      </fieldset>
      <div className="grid gap-3 sm:grid-cols-2">
        {proveedores && (
          <div>
            <label htmlFor="g-prov" className="mb-1 block text-sm font-medium">Proveedor (opcional)</label>
            <select id="g-prov" value={proveedor} onChange={(e) => setProveedor(e.target.value)} className={estiloInput}>
              <option value="">Sin proveedor</option>
              {proveedores.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select>
          </div>
        )}
        <div>
          <label htmlFor="g-num" className="mb-1 block text-sm font-medium">N.º de factura o recibo (opcional)</label>
          <input id="g-num" value={numero} onChange={(e) => setNumero(e.target.value)} className={estiloInput} />
        </div>
      </div>
      <div>
        <p className="mb-1 text-sm font-medium">Comprobante {gasto?.tiene_comprobante && <span className="font-normal text-stone-500">(ya tiene uno; elegí otro solo para reemplazarlo)</span>}</p>
        <ElegirComprobante archivo={archivo} onCambio={setArchivo} />
      </div>
      {error && <Aviso tipo="error">{error}</Aviso>}
      <button type="submit" disabled={ocupado || !valor || !descripcion.trim()} className={`${botonPrimario} w-full`}>
        {ocupado ? "Guardando…" : gasto ? "Guardar y volver a enviar" : `Guardar gasto${valor ? ` de ${gs(valor)}` : ""}`}
      </button>
    </form>
  );
}
