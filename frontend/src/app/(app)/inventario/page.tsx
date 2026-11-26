"use client";

import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { aNumero, cantidad } from "@/lib/formato";
import { CATEGORIAS, UNIDADES, type Insumo } from "@/lib/inventario";
import { Aviso, botonPrimario, estiloInput, Insignia } from "@/components/ui";

export default function Insumos() {
  const { puede } = useAuth();
  const [insumos, setInsumos] = useState<Insumo[] | null>(null);
  const [nuevo, setNuevo] = useState(false);
  const [abierto, setAbierto] = useState<string | null>(null);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);

  const cargar = useCallback(() => api<{ results: Insumo[] }>("/insumos?page_size=200").then((p) => setInsumos(p.results)), []);
  useEffect(() => {
    cargar();
  }, [cargar]);

  const bajos = insumos?.filter((i) => i.activo && i.bajo_minimo) ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-stone-600">
          {bajos.length ? <span className="font-medium text-red-700">{bajos.length} insumo{bajos.length > 1 ? "s" : ""} bajo el mínimo: {bajos.map((b) => b.nombre).join(", ")}</span>
            : "Disponible = stock menos lo reservado para lotes de queso en elaboración."}
        </p>
        {puede("inventario.catalogo.gestionar") && (
          <button onClick={() => setNuevo((v) => !v)} className="inline-flex items-center gap-1 rounded-lg bg-campo-700 px-3 py-2 text-sm font-medium text-white">
            <Plus className="h-4 w-4" aria-hidden /> Nuevo insumo
          </button>
        )}
      </div>
      {nuevo && <NuevoInsumo alGuardar={() => { setNuevo(false); cargar(); }} />}
      {aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}

      <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-stone-50 text-left text-xs uppercase tracking-wide text-stone-500">
            <tr>
              <th className="px-4 py-2.5">Insumo</th>
              <th className="px-4 py-2.5 text-right">Stock</th>
              <th className="hidden px-4 py-2.5 text-right sm:table-cell">Reservado</th>
              <th className="px-4 py-2.5 text-right">Disponible</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100">
            {insumos?.map((i) => (
              <FilaInsumo key={i.id} insumo={i} abierto={abierto === i.id} alternar={() => setAbierto(abierto === i.id ? null : i.id)}
                alMover={(texto) => { setAviso({ tipo: "ok", texto }); setAbierto(null); cargar(); }}
                alFallar={(texto) => setAviso({ tipo: "error", texto })} />
            ))}
            {insumos?.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-stone-500">Todavía no hay insumos cargados. Agregá el cuajo, la sal y lo que uses para elaborar.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FilaInsumo({ insumo: i, abierto, alternar, alMover, alFallar }: {
  insumo: Insumo; abierto: boolean; alternar: () => void; alMover: (t: string) => void; alFallar: (t: string) => void;
}) {
  const { puede } = useAuth();
  const admin = puede("inventario.ajuste.aprobar");
  const [tipo, setTipo] = useState<"compra" | "ajuste_mas" | "ajuste_menos">("compra");
  const [cant, setCant] = useState("");
  const [loteProv, setLoteProv] = useState("");
  const [nota, setNota] = useState("");

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    const c = aNumero(cant);
    if (!c) return;
    try {
      if (tipo === "ajuste_menos") {
        await api(`/insumos/${i.id}/salida`, { method: "POST", body: JSON.stringify({ cantidad: c, nota }) });
      } else {
        await api(`/insumos/${i.id}/entrada`, {
          method: "POST",
          body: JSON.stringify({ cantidad: c, motivo: tipo === "compra" ? "compra" : "ajuste", lote_proveedor: loteProv, nota }),
        });
      }
      alMover(`${i.nombre}: ${tipo === "ajuste_menos" ? "salida" : "entrada"} de ${cantidad(c, i.unidad)} registrada.`);
      setCant("");
      setNota("");
      setLoteProv("");
    } catch (err) {
      alFallar(err instanceof ApiError ? err.message : "No se pudo registrar.");
    }
  }

  return (
    <>
      <tr className={i.activo ? "" : "opacity-50"}>
        <td className="px-4 py-3">
          <span className="font-medium">{i.nombre}</span>
          <span className="ml-2 text-xs text-stone-500">{i.codigo}</span>
          {i.bajo_minimo && i.activo && <span className="ml-2"><Insignia color="rojo">Bajo mínimo ({cantidad(i.stock_minimo, i.unidad)})</Insignia></span>}
        </td>
        <td className="px-4 py-3 text-right tabular-nums">{cantidad(i.stock, i.unidad)}</td>
        <td className="hidden px-4 py-3 text-right tabular-nums text-stone-500 sm:table-cell">{Number(i.reservado) ? cantidad(i.reservado, i.unidad) : "—"}</td>
        <td className="px-4 py-3 text-right font-medium tabular-nums">{cantidad(i.disponible, i.unidad)}</td>
        <td className="px-4 py-3 text-right">
          {puede("inventario.entrada.registrar") && (
            <button onClick={alternar} aria-expanded={abierto} className="text-sm font-medium text-campo-700">{abierto ? "Cerrar" : "Registrar"}</button>
          )}
        </td>
      </tr>
      {abierto && (
        <tr>
          <td colSpan={5} className="bg-stone-50 px-4 py-3">
            <form onSubmit={guardar} className="grid gap-2 sm:grid-cols-5" aria-label={`Movimiento de ${i.nombre}`}>
              <select aria-label="Tipo" value={tipo} onChange={(e) => setTipo(e.target.value as typeof tipo)} className={estiloInput}>
                <option value="compra">Entrada por compra</option>
                {admin && <option value="ajuste_mas">Ajuste: sumar</option>}
                {admin && <option value="ajuste_menos">Ajuste: restar</option>}
              </select>
              <input aria-label="Cantidad" inputMode="decimal" placeholder={`Cantidad (${i.unidad})`} value={cant} onChange={(e) => setCant(e.target.value)} className={estiloInput} />
              {tipo === "compra"
                ? <input aria-label="Lote del proveedor" placeholder="Lote del proveedor" value={loteProv} onChange={(e) => setLoteProv(e.target.value)} className={estiloInput} />
                : <span className="hidden sm:block" />}
              <input aria-label="Nota" placeholder={tipo === "compra" ? "Nota (opcional)" : "Motivo del ajuste"} required={tipo !== "compra"} value={nota} onChange={(e) => setNota(e.target.value)} className={estiloInput} />
              <button className={`${botonPrimario} py-2.5`}>Guardar</button>
            </form>
          </td>
        </tr>
      )}
    </>
  );
}

function NuevoInsumo({ alGuardar }: { alGuardar: () => void }) {
  const [codigo, setCodigo] = useState("");
  const [nombre, setNombre] = useState("");
  const [categoria, setCategoria] = useState("otro");
  const [unidad, setUnidad] = useState("kg");
  const [minimo, setMinimo] = useState("");
  const [error, setError] = useState("");

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    try {
      await api("/insumos", { method: "POST", body: JSON.stringify({ codigo, nombre, categoria, unidad, stock_minimo: aNumero(minimo) ?? "0" }) });
      alGuardar();
    } catch (err) {
      const datos = err instanceof ApiError ? (err.datos as Record<string, string[]>) : null;
      setError(datos?.codigo ? "Ya existe un insumo con ese código." : err instanceof ApiError ? err.message : "No se pudo guardar.");
    }
  }

  return (
    <form onSubmit={guardar} className="grid gap-3 rounded-2xl border border-stone-200 bg-white p-4 sm:grid-cols-6" aria-label="Nuevo insumo">
      <input aria-label="Código" placeholder="Código" required value={codigo} onChange={(e) => setCodigo(e.target.value)} className={estiloInput} />
      <input aria-label="Nombre" placeholder="Nombre" required value={nombre} onChange={(e) => setNombre(e.target.value)} className={`${estiloInput} sm:col-span-2`} />
      <select aria-label="Categoría" value={categoria} onChange={(e) => setCategoria(e.target.value)} className={estiloInput}>
        {CATEGORIAS.map((c) => <option key={c.valor} value={c.valor}>{c.nombre}</option>)}
      </select>
      <select aria-label="Unidad" value={unidad} onChange={(e) => setUnidad(e.target.value)} className={estiloInput}>
        {UNIDADES.map((u) => <option key={u.valor} value={u.valor}>{u.nombre}</option>)}
      </select>
      <input aria-label="Stock mínimo" placeholder="Stock mínimo" inputMode="decimal" value={minimo} onChange={(e) => setMinimo(e.target.value)} className={estiloInput} />
      {error && <div className="sm:col-span-6"><Aviso tipo="error">{error}</Aviso></div>}
      <div className="sm:col-span-6"><button className={`${botonPrimario} py-2.5`}>Crear insumo</button></div>
    </form>
  );
}
