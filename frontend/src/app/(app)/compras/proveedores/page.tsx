"use client";

import { useCallback, useEffect, useState } from "react";
import { Pencil, Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fechaCorta } from "@/lib/leche";
import { gs } from "@/lib/ventas";
import { primerError } from "@/lib/usuarios";
import { NOMBRE_TIPO_PROVEEDOR, TIPOS_PROVEEDOR, type Proveedor } from "@/lib/egresos";
import { Aviso, botonPrimario, botonSecundario, estiloInput, Insignia } from "@/components/ui";

type Datos = Pick<Proveedor, "nombre" | "tipo" | "ruc" | "contacto" | "telefono" | "email" | "direccion" | "notas" | "activo">;
const VACIO: Datos = { nombre: "", tipo: "insumos", ruc: "", contacto: "", telefono: "", email: "", direccion: "", notas: "", activo: true };

export default function Proveedores() {
  const { puede } = useAuth();
  const editar = puede("compras.compra.registrar");
  const [lista, setLista] = useState<Proveedor[] | null>(null);
  const [buscar, setBuscar] = useState("");
  const [tipo, setTipo] = useState("");
  const [editando, setEditando] = useState<Proveedor | "nuevo" | null>(null);
  const [aviso, setAviso] = useState("");

  const cargar = useCallback(() => {
    const q = new URLSearchParams({ page_size: "300" });
    if (buscar.trim()) q.set("buscar", buscar.trim());
    if (tipo) q.set("tipo", tipo);
    api<{ results: Proveedor[] }>(`/proveedores?${q}`).then((r) => setLista(r.results));
  }, [buscar, tipo]);
  useEffect(() => {
    const t = setTimeout(cargar, 250);
    return () => clearTimeout(t);
  }, [cargar]);

  return (
    <div className="space-y-5">
      {aviso && <Aviso tipo="ok">{aviso}</Aviso>}
      {editando ? (
        <FormProveedor proveedor={editando === "nuevo" ? undefined : editando} onCancelar={() => setEditando(null)}
          onGuardado={(p, nuevo) => { setEditando(null); setAviso(nuevo ? `Proveedor “${p.nombre}” agregado.` : `Cambios en “${p.nombre}” guardados.`); cargar(); }} />
      ) : editar && (
        <button onClick={() => { setAviso(""); setEditando("nuevo"); }} className={`${botonPrimario} inline-flex items-center gap-2`}>
          <Plus className="h-5 w-5" aria-hidden /> Nuevo proveedor
        </button>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div className="col-span-2">
          <label htmlFor="f-buscar" className="mb-1 block text-xs font-medium">Buscar</label>
          <input id="f-buscar" value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Nombre, RUC o contacto" className={estiloInput} />
        </div>
        <div>
          <label htmlFor="f-tipo" className="mb-1 block text-xs font-medium">Tipo</label>
          <select id="f-tipo" value={tipo} onChange={(e) => setTipo(e.target.value)} className={estiloInput}>
            <option value="">Todos</option>
            {TIPOS_PROVEEDOR.map((t) => <option key={t.valor} value={t.valor}>{t.nombre}</option>)}
          </select>
        </div>
      </div>

      {!lista ? <p className="text-stone-500">Cargando…</p> : lista.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">No hay proveedores con esa búsqueda.</p>
      ) : (
        <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white" aria-label="Proveedores">
          {lista.map((p) => (
            <li key={p.id} className={`flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 ${p.activo ? "" : "opacity-60"}`}>
              <span className="min-w-0 flex-1">
                <span className="block font-medium">{p.nombre} {!p.activo && <Insignia color="gris">Inactivo</Insignia>}</span>
                <span className="block text-xs text-stone-500">
                  {NOMBRE_TIPO_PROVEEDOR[p.tipo]}{p.ruc && ` · RUC ${p.ruc}`}{p.contacto && ` · ${p.contacto}`}{p.telefono && ` · ${p.telefono}`}
                </span>
              </span>
              <span className="text-right text-sm">
                {p.saldo_pendiente > 0 && <span className="block font-medium text-amber-800 tabular-nums">Debemos {gs(p.saldo_pendiente)}</span>}
                <span className="block text-xs text-stone-500">{p.ultima_compra ? `Última compra ${fechaCorta(p.ultima_compra)}` : "Sin compras"}</span>
              </span>
              {editar && (
                <button onClick={() => { setAviso(""); setEditando(p); window.scrollTo({ top: 0 }); }} aria-label={`Editar ${p.nombre}`} className="rounded-lg p-2 text-stone-500 hover:bg-stone-100">
                  <Pencil className="h-4 w-4" aria-hidden />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function FormProveedor({ proveedor, onGuardado, onCancelar }: { proveedor?: Proveedor; onGuardado: (p: Proveedor, nuevo: boolean) => void; onCancelar: () => void }) {
  const [d, setD] = useState<Datos>(() => (proveedor ? { ...VACIO, ...proveedor } : VACIO));
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const campo = (k: keyof Datos) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setD({ ...d, [k]: e.target.value });

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setOcupado(true);
    try {
      const cuerpo = { nombre: d.nombre, tipo: d.tipo, ruc: d.ruc, contacto: d.contacto, telefono: d.telefono, email: d.email, direccion: d.direccion, notas: d.notas, activo: d.activo };
      const p = await api<Proveedor>(proveedor ? `/proveedores/${proveedor.id}` : "/proveedores", { method: proveedor ? "PATCH" : "POST", body: JSON.stringify(cuerpo) });
      onGuardado(p, !proveedor);
    } catch (err) {
      setError(err instanceof ApiError ? primerError(err.datos, err.message) : "No se pudo guardar.");
      setOcupado(false);
    }
  }

  const texto = (k: keyof Datos, etiqueta: string, tipoInput = "text") => (
    <div>
      <label htmlFor={`pv-${k}`} className="mb-1 block text-sm font-medium">{etiqueta}</label>
      <input id={`pv-${k}`} type={tipoInput} value={String(d[k] ?? "")} onChange={campo(k)} className={estiloInput} required={k === "nombre"} />
    </div>
  );

  return (
    <form onSubmit={guardar} className="space-y-4 rounded-2xl border border-stone-200 bg-white p-5" aria-label={proveedor ? "Editar proveedor" : "Nuevo proveedor"}>
      <h2 className="font-semibold">{proveedor ? `Editar ${proveedor.nombre}` : "Nuevo proveedor"}</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {texto("nombre", "Nombre")}
        <div>
          <label htmlFor="pv-tipo" className="mb-1 block text-sm font-medium">Tipo</label>
          <select id="pv-tipo" value={d.tipo} onChange={campo("tipo")} className={estiloInput}>
            {TIPOS_PROVEEDOR.map((t) => <option key={t.valor} value={t.valor}>{t.nombre}</option>)}
          </select>
        </div>
        {texto("contacto", "Persona de contacto")}
        {texto("telefono", "Teléfono", "tel")}
        {texto("ruc", "RUC (opcional)")}
        {texto("email", "Correo (opcional)", "email")}
        {texto("direccion", "Dirección (opcional)")}
        {texto("notas", "Notas (opcional)")}
      </div>
      {proveedor && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={d.activo} onChange={(e) => setD({ ...d, activo: e.target.checked })} /> Activo (los inactivos no aparecen al cargar compras o gastos)
        </label>
      )}
      {error && <Aviso tipo="error">{error}</Aviso>}
      <div className="flex gap-2">
        <button type="submit" disabled={ocupado || !d.nombre.trim()} className={`${botonPrimario} flex-1`}>{ocupado ? "Guardando…" : "Guardar proveedor"}</button>
        <button type="button" onClick={onCancelar} className={botonSecundario}>Cancelar</button>
      </div>
    </form>
  );
}
