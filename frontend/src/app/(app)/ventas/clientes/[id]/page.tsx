"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Pencil, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { kg } from "@/lib/formato";
import { fechaCorta, litros } from "@/lib/leche";
import { FormCliente } from "@/components/FormCliente";
import {
  cantidadVenta, ESTADO_VENTA, gs, NOMBRE_CONDICION, NOMBRE_PRODUCTO, NOMBRE_TIPO_CLIENTE, type Historial,
} from "@/lib/ventas";
import { Aviso, Insignia, Tarjeta } from "@/components/ui";

export default function DetalleCliente() {
  const { id } = useParams<{ id: string }>();
  const { puede } = useAuth();
  const [h, setH] = useState<Historial | null>(null);
  const [error, setError] = useState("");
  const [editando, setEditando] = useState(false);

  const cargar = useCallback(() => api<Historial>(`/clientes/${id}/historial`).then(setH).catch(() => setError("No se encontró el cliente.")), [id]);
  useEffect(() => {
    cargar();
  }, [cargar]);

  if (!h) return error ? <Aviso tipo="error">{error}</Aviso> : <p className="text-stone-500">Cargando…</p>;
  const c = h.cliente;
  const t = h.totales;

  return (
    <div className="space-y-5">
      <Link href="/ventas/clientes" className="inline-flex items-center gap-1 text-sm text-stone-600 hover:text-stone-900">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Clientes
      </Link>

      {editando ? (
        <FormCliente cliente={c} onGuardado={() => { setEditando(false); cargar(); }} onCancelar={() => setEditando(false)} />
      ) : (
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold">{c.nombre} {!c.activo && <Insignia>Dado de baja</Insignia>}</h2>
            <p className="text-sm text-stone-600">
              {NOMBRE_TIPO_CLIENTE[c.tipo]} · {NOMBRE_CONDICION[c.condicion_pago]}
              {c.documento && ` · ${c.documento}`}{c.telefono && ` · ${c.telefono}`}
            </p>
            {c.direccion && <p className="text-sm text-stone-500">{c.direccion}</p>}
            {c.notas && <p className="mt-1 text-sm text-stone-600">“{c.notas}”</p>}
          </div>
          <div className="flex gap-2">
            {puede("ventas.venta.registrar") && c.activo && (
              <Link href={`/ventas/registrar?cliente=${c.id}`} className="flex items-center gap-1 rounded-lg bg-campo-700 px-3 py-2 text-sm font-medium text-white hover:bg-campo-900">
                <Plus className="h-4 w-4" aria-hidden /> Nueva venta
              </Link>
            )}
            {puede("ventas.cliente.gestionar") && (
              <button onClick={() => setEditando(true)} className="flex items-center gap-1 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm">
                <Pencil className="h-4 w-4" aria-hidden /> Editar
              </button>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tarjeta titulo="Compras" valor={t.compras} detalle={t.ultima_compra ? `Última: ${fechaCorta(t.ultima_compra)}` : "Todavía no compró"} />
        <Tarjeta titulo="Total comprado" valor={gs(t.total_comprado)} />
        <Tarjeta titulo="Queso / leche" valor={kg(t.kg_queso)} detalle={`${litros(t.litros_leche)} de leche`} />
        <Tarjeta titulo="Saldo pendiente" valor={<span className={t.saldo_pendiente ? "text-amber-800" : ""}>{gs(t.saldo_pendiente)}</span>} />
      </div>

      <section className="rounded-2xl border border-stone-200 bg-white p-5">
        <h3 className="mb-2 font-semibold">Lotes que recibió</h3>
        {h.lotes_entregados.length === 0 ? <p className="text-sm text-stone-500">Todavía no recibió ningún lote.</p> : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-stone-500"><tr><th className="py-1">Lote</th><th className="py-1">Elaborado</th><th className="py-1">Ventas</th><th className="py-1 text-right">Cantidad</th></tr></thead>
            <tbody className="divide-y divide-stone-100">
              {h.lotes_entregados.map((l) => (
                <tr key={l.lote}>
                  <td className="py-1.5"><Link href={l.tipo === "queso" ? `/queso/${l.lote}` : `/leche/lotes/${l.lote}`} className="text-campo-800 hover:underline">{l.codigo}</Link></td>
                  <td className="py-1.5 text-stone-500">{fechaCorta(l.fecha_lote)}</td>
                  <td className="py-1.5 text-stone-500">{l.ventas.join(", ")}</td>
                  <td className="py-1.5 text-right tabular-nums">{cantidadVenta(l.cantidad, l.unidad)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h3 className="mb-2 font-semibold">Historial de compras</h3>
        {h.ventas.length === 0 ? <p className="text-sm text-stone-500">Sin compras.</p> : (
          <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white">
            {h.ventas.map((v) => (
              <li key={v.id}>
                <Link href={`/ventas/${v.id}`} className={`flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-stone-50 ${v.estado_venta === "anulada" ? "opacity-60" : ""}`}>
                  <span className="w-20 font-medium">{v.codigo}</span>
                  <span className="w-24 text-sm text-stone-500">{fechaCorta(v.fecha)}</span>
                  <span className="text-sm text-stone-600">{NOMBRE_PRODUCTO[v.producto]} · {cantidadVenta(v.cantidad, v.unidad)}</span>
                  <Insignia color={ESTADO_VENTA[v.estado_venta].color}>{ESTADO_VENTA[v.estado_venta].nombre}</Insignia>
                  <span className="ml-auto text-right text-sm tabular-nums">
                    <span className="block font-medium">{gs(v.total)}</span>
                    {v.cuenta && v.cuenta.saldo > 0 && v.estado_venta !== "anulada" && <span className="block text-xs text-amber-800">debe {gs(v.cuenta.saldo)}</span>}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
