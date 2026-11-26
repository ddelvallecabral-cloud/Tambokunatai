"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { CONDICIONES, TIPOS_CLIENTE, type Cliente } from "@/lib/ventas";
import { Aviso, botonPrimario, botonSecundario, estiloInput } from "@/components/ui";

type Campos = Pick<Cliente, "nombre" | "tipo" | "documento" | "telefono" | "email" | "direccion" | "condicion_pago" | "notas" | "activo">;

const VACIO: Campos = {
  nombre: "", tipo: "minorista", documento: "", telefono: "", email: "", direccion: "", condicion_pago: "contado", notas: "", activo: true,
};

/** Alta o edición de un cliente. */
export function FormCliente({ cliente, onGuardado, onCancelar }: { cliente?: Cliente; onGuardado: (c: Cliente) => void; onCancelar: () => void }) {
  const [datos, setDatos] = useState<Campos>(cliente ? { ...VACIO, ...cliente } : VACIO);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const campo = <K extends keyof Campos>(k: K) => (v: Campos[K]) => setDatos((d) => ({ ...d, [k]: v }));

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setOcupado(true);
    try {
      const c = await api<Cliente>(cliente ? `/clientes/${cliente.id}` : "/clientes", {
        method: cliente ? "PATCH" : "POST",
        body: JSON.stringify(datos),
      });
      onGuardado(c);
    } catch (err) {
      setError(err instanceof ApiError ? Object.values((err.datos ?? {}) as Record<string, string[]>).flat()[0] ?? err.message : "No se pudo guardar.");
    } finally {
      setOcupado(false);
    }
  }

  const texto = (k: "nombre" | "documento" | "telefono" | "email" | "direccion", etiqueta: string, extra: React.InputHTMLAttributes<HTMLInputElement> = {}) => (
    <div>
      <label htmlFor={`c-${k}`} className="mb-1 block text-sm font-medium">{etiqueta}</label>
      <input id={`c-${k}`} value={datos[k]} onChange={(e) => campo(k)(e.target.value)} className={estiloInput} {...extra} />
    </div>
  );

  return (
    <form onSubmit={guardar} className="space-y-3 rounded-2xl border border-stone-200 bg-white p-5">
      <h2 className="font-semibold">{cliente ? "Editar cliente" : "Cliente nuevo"}</h2>
      {texto("nombre", "Nombre o razón social", { required: true })}
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="c-tipo" className="mb-1 block text-sm font-medium">Tipo</label>
          <select id="c-tipo" value={datos.tipo} onChange={(e) => campo("tipo")(e.target.value as Campos["tipo"])} className={estiloInput}>
            {TIPOS_CLIENTE.map((t) => <option key={t.valor} value={t.valor}>{t.nombre}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="c-cond" className="mb-1 block text-sm font-medium">Condición de pago</label>
          <select id="c-cond" value={datos.condicion_pago} onChange={(e) => campo("condicion_pago")(e.target.value as Campos["condicion_pago"])} className={estiloInput}>
            {CONDICIONES.map((t) => <option key={t.valor} value={t.valor}>{t.nombre}</option>)}
          </select>
        </div>
        {texto("documento", "RUC o C.I. (opcional)")}
        {texto("telefono", "Teléfono", { inputMode: "tel" })}
        {texto("email", "Correo (opcional)", { type: "email" })}
        {texto("direccion", "Dirección")}
      </div>
      <div>
        <label htmlFor="c-notas" className="mb-1 block text-sm font-medium">Notas</label>
        <textarea id="c-notas" value={datos.notas} onChange={(e) => campo("notas")(e.target.value)} rows={2} className={estiloInput} />
      </div>
      {cliente && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={!datos.activo} onChange={(e) => campo("activo")(!e.target.checked)} /> Dado de baja (no se le pueden hacer ventas nuevas)
        </label>
      )}
      {error && <Aviso tipo="error">{error}</Aviso>}
      <div className="flex gap-2">
        <button type="submit" disabled={ocupado || !datos.nombre.trim()} className={botonPrimario}>{ocupado ? "Guardando…" : "Guardar"}</button>
        <button type="button" onClick={onCancelar} className={botonSecundario}>Cancelar</button>
      </div>
    </form>
  );
}
