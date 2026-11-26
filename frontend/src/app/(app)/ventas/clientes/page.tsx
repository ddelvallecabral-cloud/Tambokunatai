"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Search, UserPlus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fechaCorta } from "@/lib/leche";
import { FormCliente } from "@/components/FormCliente";
import { gs, NOMBRE_CONDICION, NOMBRE_TIPO_CLIENTE, TIPOS_CLIENTE, type Cliente } from "@/lib/ventas";
import { botonPrimario, estiloInput, Insignia } from "@/components/ui";

export default function Clientes() {
  const { puede } = useAuth();
  const [buscar, setBuscar] = useState("");
  const [tipo, setTipo] = useState("");
  const [inactivos, setInactivos] = useState(false);
  const [clientes, setClientes] = useState<Cliente[] | null>(null);
  const [nuevo, setNuevo] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => {
      const q = new URLSearchParams({ page_size: "200", buscar: buscar.trim(), tipo });
      if (!inactivos) q.set("activo", "1");
      api<{ results: Cliente[] }>(`/clientes?${q}`).then((p) => setClientes(p.results));
    }, 200);
    return () => clearTimeout(t);
  }, [buscar, tipo, inactivos, version]);

  return (
    <div className="space-y-5">
      {puede("ventas.cliente.gestionar") && (nuevo ? (
        <FormCliente onGuardado={() => { setNuevo(false); setVersion((v) => v + 1); }} onCancelar={() => setNuevo(false)} />
      ) : (
        <button onClick={() => setNuevo(true)} className={`${botonPrimario} flex items-center gap-2`}>
          <UserPlus className="h-5 w-5" aria-hidden /> Cliente nuevo
        </button>
      ))}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="relative col-span-2">
          <Search className="pointer-events-none absolute left-3 top-3 h-5 w-5 text-stone-400" aria-hidden />
          <input aria-label="Buscar cliente" value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Nombre, RUC o teléfono" className={`${estiloInput} pl-10`} />
        </div>
        <select aria-label="Tipo de cliente" value={tipo} onChange={(e) => setTipo(e.target.value)} className={estiloInput}>
          <option value="">Todos los tipos</option>
          {TIPOS_CLIENTE.map((t) => <option key={t.valor} value={t.valor}>{t.nombre}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={inactivos} onChange={(e) => setInactivos(e.target.checked)} /> Ver dados de baja
        </label>
      </div>

      {!clientes ? (
        <p className="text-stone-500">Cargando…</p>
      ) : clientes.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">No hay clientes con esos filtros.</p>
      ) : (
        <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white">
          {clientes.map((c) => (
            <li key={c.id}>
              <Link href={`/ventas/clientes/${c.id}`} className={`flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-stone-50 ${c.activo ? "" : "opacity-60"}`}>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{c.nombre}</span>
                  <span className="block text-xs text-stone-500">
                    {NOMBRE_TIPO_CLIENTE[c.tipo]} · {NOMBRE_CONDICION[c.condicion_pago]}{c.telefono && ` · ${c.telefono}`}
                  </span>
                </span>
                {!c.activo && <Insignia>Dado de baja</Insignia>}
                <span className="text-right text-sm">
                  {c.saldo_pendiente > 0 ? <span className="block font-medium text-amber-800 tabular-nums">Debe {gs(c.saldo_pendiente)}</span> : <span className="block text-stone-400">Sin deuda</span>}
                  <span className="block text-xs text-stone-500">{c.ultima_compra ? `Última compra ${fechaCorta(c.ultima_compra)}` : "Sin compras"}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
