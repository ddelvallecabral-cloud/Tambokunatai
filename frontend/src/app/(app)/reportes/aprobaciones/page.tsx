"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fechaHora } from "@/lib/formato";
import type { FilaAuditoria } from "@/lib/reportes";
import { Periodo, usePeriodo } from "@/components/Periodo";
import { estiloInput, Insignia } from "@/components/ui";

export default function Pagina() {
  return <Suspense fallback={<p className="text-stone-500">Cargando…</p>}><Historial /></Suspense>;
}

const ENTIDADES = [["", "Todo"], ["gastos", "Gastos"], ["lotes_queso", "Lotes de queso"], ["lotes_leche", "Correcciones de leche"]];

function Historial() {
  const params = useSearchParams();
  const router = useRouter();
  const ruta = usePathname();
  const { consulta } = usePeriodo();
  const entidad = params.get("entidad") ?? "";
  const [filas, setFilas] = useState<FilaAuditoria[] | null>(null);
  useEffect(() => { setFilas(null); api<FilaAuditoria[]>(`/reportes/aprobaciones?${consulta}&entidad=${entidad}`).then(setFilas); }, [consulta, entidad]);
  const cambiar = (v: string) => { const q = new URLSearchParams(params.toString()); if (v) q.set("entidad", v); else q.delete("entidad"); router.replace(`${ruta}?${q}`); };
  return (
    <div className="space-y-5">
      <Periodo reporte="aprobaciones" />
      <div className="max-w-xs">
        <label htmlFor="f-ent" className="mb-1 block text-xs font-medium">Qué</label>
        <select id="f-ent" value={entidad} onChange={(e) => cambiar(e.target.value)} className={estiloInput}>
          {ENTIDADES.map(([v, n]) => <option key={v} value={v}>{n}</option>)}
        </select>
      </div>
      {!filas ? <p className="text-stone-500">Cargando…</p> : filas.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">No hubo aprobaciones ni rechazos en el período.</p>
      ) : (
        <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white" aria-label="Historial de aprobaciones">
          {filas.map((f, i) => (
            <li key={f.id ?? `a${i}`} className="flex flex-wrap items-start gap-x-4 gap-y-1 px-4 py-3 text-sm">
              <span className="w-32 shrink-0 text-stone-500">{fechaHora(f.fecha)}</span>
              <span className="min-w-0 flex-1">
                <span className="block"><b>{f.usuario}</b> · {f.accion_nombre.toLowerCase()} {f.entidad_nombre.toLowerCase()}:{" "}
                  {f.ruta ? <Link href={f.ruta} className="font-medium text-campo-800 hover:underline">{f.registro}</Link> : f.registro}
                </span>
                {f.motivo && <span className="block text-xs text-stone-500">“{f.motivo}”</span>}
              </span>
              <Insignia color={f.accion === "rechazar" ? "rojo" : "verde"}>{f.accion === "rechazar" ? "Rechazado" : "Aprobado"}</Insignia>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
