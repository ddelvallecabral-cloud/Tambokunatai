"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fechaHora } from "@/lib/formato";
import { gs, NOMBRE_TIPO_CLIENTE, PRODUCTOS, TIPOS_CLIENTE, type Precio, type Producto, type TipoCliente } from "@/lib/ventas";
import { Aviso, botonPrimario, botonSecundario, estiloInput } from "@/components/ui";

const n2 = new Intl.NumberFormat("es-PY", { maximumFractionDigits: 2 });
const primerError = (err: unknown) =>
  err instanceof ApiError ? Object.values((err.datos ?? {}) as Record<string, string[]>).flat()[0] ?? err.message : "No se pudo guardar.";

export default function Precios() {
  const { puede } = useAuth();
  const edita = puede("ventas.precio.gestionar");
  const [precios, setPrecios] = useState<Precio[] | null>(null);
  const [error, setError] = useState("");
  const [nuevo, setNuevo] = useState(false);

  const cargar = useCallback(() => api<Precio[]>("/precios").then(setPrecios), []);
  useEffect(() => {
    cargar();
  }, [cargar]);

  async function guardar(p: Precio, cambios: Partial<Precio>) {
    setError("");
    try {
      await api(`/precios/${p.id}`, { method: "PATCH", body: JSON.stringify(cambios) });
      cargar();
    } catch (err) {
      setError(primerError(err));
    }
  }

  return (
    <div className="space-y-5">
      <p className="text-sm text-stone-600">
        Para cada venta se usa el precio más bajo que aplique: el base, el del tipo de cliente o el de volumen cuando se llega a la cantidad mínima.
        {!edita && " Solo el Administrador puede cambiar esta tabla."}
      </p>
      {error && <Aviso tipo="error">{error}</Aviso>}
      {!precios ? <p className="text-stone-500">Cargando…</p> : PRODUCTOS.map((prod) => (
        <section key={prod.valor} className="rounded-2xl border border-stone-200 bg-white p-5">
          <h2 className="mb-2 font-semibold">{prod.nombre} <span className="text-sm font-normal text-stone-500">por {prod.unidad}</span></h2>
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-stone-500">
              <tr><th className="py-1">Para</th><th className="py-1">Desde</th><th className="py-1 text-right">Precio</th>{edita && <th className="py-1" />}</tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {precios.filter((p) => p.producto === prod.valor).map((p) => (
                <Fila key={p.id} p={p} unidad={prod.unidad} edita={edita} onGuardar={(c) => guardar(p, c)} />
              ))}
            </tbody>
          </table>
        </section>
      ))}
      {edita && (nuevo ? (
        <NuevoPrecio onCreado={() => { setNuevo(false); cargar(); }} onCancelar={() => setNuevo(false)} />
      ) : (
        <button onClick={() => setNuevo(true)} className={`${botonSecundario} flex items-center gap-2`}><Plus className="h-4 w-4" aria-hidden /> Agregar precio</button>
      ))}
    </div>
  );
}

function Fila({ p, unidad, edita, onGuardar }: { p: Precio; unidad: string; edita: boolean; onGuardar: (c: Partial<Precio>) => void }) {
  const [valor, setValor] = useState(String(p.precio_unitario));
  const cambiado = Number(valor) !== p.precio_unitario;
  return (
    <tr>
      <td className="py-2">{p.tipo_cliente ? NOMBRE_TIPO_CLIENTE[p.tipo_cliente] : "Todos (precio base)"}</td>
      <td className="py-2 text-stone-600">{Number(p.cantidad_minima) > 0 ? `${n2.format(Number(p.cantidad_minima))} ${unidad}` : "—"}</td>
      <td className="py-2 text-right tabular-nums">
        {edita ? (
          <input aria-label="Precio" inputMode="numeric" value={valor} onChange={(e) => setValor(e.target.value.replace(/\D/g, ""))}
            className="w-28 rounded-md border border-stone-300 px-2 py-1 text-right" />
        ) : gs(p.precio_unitario)}
      </td>
      {edita && (
        <td className="py-2 pl-2 text-right whitespace-nowrap">
          {cambiado ? (
            <button disabled={!Number(valor)} onClick={() => onGuardar({ precio_unitario: Number(valor) })} className="rounded-md bg-campo-700 px-2 py-1 text-xs font-medium text-white">Guardar</button>
          ) : (
            <button onClick={() => onGuardar({ activo: false })} className="text-xs text-red-700 hover:underline" title={`Modificado ${fechaHora(p.fecha_modificacion)}`}>Quitar</button>
          )}
        </td>
      )}
    </tr>
  );
}

function NuevoPrecio({ onCreado, onCancelar }: { onCreado: () => void; onCancelar: () => void }) {
  const [producto, setProducto] = useState<Producto>("queso");
  const [tipo, setTipo] = useState<TipoCliente | "">("");
  const [minimo, setMinimo] = useState("");
  const [precio, setPrecio] = useState("");
  const [error, setError] = useState("");

  async function crear() {
    setError("");
    try {
      await api("/precios", {
        method: "POST",
        body: JSON.stringify({ producto, tipo_cliente: tipo, cantidad_minima: (minimo || "0").replace(",", "."), precio_unitario: Number(precio) }),
      });
      onCreado();
    } catch (err) {
      setError(primerError(err));
    }
  }

  return (
    <div className="space-y-3 rounded-2xl border border-stone-200 bg-white p-5">
      <h2 className="font-semibold">Precio nuevo</h2>
      <div className="grid gap-3 sm:grid-cols-4">
        <select aria-label="Producto" value={producto} onChange={(e) => setProducto(e.target.value as Producto)} className={estiloInput}>
          {PRODUCTOS.map((p) => <option key={p.valor} value={p.valor}>{p.nombre}</option>)}
        </select>
        <select aria-label="Tipo de cliente" value={tipo} onChange={(e) => setTipo(e.target.value as TipoCliente | "")} className={estiloInput}>
          <option value="">Todos los clientes</option>
          {TIPOS_CLIENTE.map((t) => <option key={t.valor} value={t.valor}>{t.nombre}</option>)}
        </select>
        <input aria-label="Cantidad mínima" inputMode="decimal" value={minimo} onChange={(e) => setMinimo(e.target.value.replace(/[^0-9.,]/g, ""))} placeholder="Desde (cantidad, opcional)" className={estiloInput} />
        <input aria-label="Precio en guaraníes" inputMode="numeric" value={precio} onChange={(e) => setPrecio(e.target.value.replace(/\D/g, ""))} placeholder="Precio Gs." className={estiloInput} />
      </div>
      {error && <Aviso tipo="error">{error}</Aviso>}
      <div className="flex gap-2">
        <button disabled={!Number(precio)} onClick={crear} className={botonPrimario}>Agregar</button>
        <button onClick={onCancelar} className={botonSecundario}>Cancelar</button>
      </div>
    </div>
  );
}
