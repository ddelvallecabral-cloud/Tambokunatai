"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { NOMBRE_ALERTA, type Alerta, type ConfigAlertas } from "@/lib/reportes";
import { Aviso, botonPrimario, estiloInput } from "@/components/ui";

export default function Alertas() {
  const { puede } = useAuth();
  const editar = puede("configuracion.gestionar");
  const [conf, setConf] = useState<ConfigAlertas | null>(null);
  const [lista, setLista] = useState<Alerta[] | null>(null);
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const cargarLista = () => api<Alerta[]>("/alertas").then(setLista);
  useEffect(() => { api<ConfigAlertas>("/alertas/configuracion").then(setConf); cargarLista(); }, []);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setAviso(""); setOcupado(true);
    try {
      setConf(await api<ConfigAlertas>("/alertas/configuracion", { method: "PUT", body: JSON.stringify(conf) }));
      setAviso("Alertas guardadas.");
      cargarLista();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar.");
    } finally {
      setOcupado(false);
    }
  }

  if (!conf) return <p className="text-stone-500">Cargando…</p>;
  const set = <K extends keyof ConfigAlertas>(k: K, v: Partial<ConfigAlertas[K]>) => setConf({ ...conf, [k]: { ...conf[k], ...v } });
  const num = (v: string) => Number(v.replace(",", ".")) || 0;
  const interruptor = (k: keyof ConfigAlertas, titulo: string, texto: string, extra?: React.ReactNode) => (
    <fieldset className="space-y-2 rounded-xl border border-stone-200 p-4" disabled={!editar}>
      <label className="flex items-center justify-between gap-3">
        <span><span className="block font-medium">{titulo}</span><span className="block text-sm text-stone-500">{texto}</span></span>
        <input type="checkbox" className="h-5 w-5 accent-campo-700" checked={conf[k].activa} onChange={(e) => set(k, { activa: e.target.checked } as never)} aria-label={`Activar ${titulo}`} />
      </label>
      {conf[k].activa && extra}
    </fieldset>
  );

  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <form onSubmit={guardar} className="space-y-3">
        <h2 className="text-lg font-semibold">Qué avisar</h2>
        {!editar && <p className="text-sm text-stone-500">Solo el Administrador cambia estas alertas.</p>}
        {interruptor("produccion_baja", "Producción diaria baja", "Avisa si un día se ordeña menos de lo esperado.",
          <div><label htmlFor="a-litros" className="mb-1 block text-xs font-medium">Litros mínimos por día</label>
            <input id="a-litros" inputMode="decimal" value={conf.produccion_baja.litros_minimos || ""} onChange={(e) => set("produccion_baja", { litros_minimos: num(e.target.value) })} className={estiloInput} /></div>)}
        {interruptor("rendimiento", "Rendimiento de queso fuera de rango", "Litros de leche por kg de queso. Fuera de este rango, el lote se marca al cerrarlo.",
          <div className="grid grid-cols-2 gap-2">
            <div><label htmlFor="a-min" className="mb-1 block text-xs font-medium">Mínimo (L/kg)</label>
              <input id="a-min" inputMode="decimal" value={conf.rendimiento.minimo} onChange={(e) => set("rendimiento", { minimo: num(e.target.value) })} className={estiloInput} /></div>
            <div><label htmlFor="a-max" className="mb-1 block text-xs font-medium">Máximo (L/kg)</label>
              <input id="a-max" inputMode="decimal" value={conf.rendimiento.maximo} onChange={(e) => set("rendimiento", { maximo: num(e.target.value) })} className={estiloInput} /></div>
          </div>)}
        {interruptor("stock_bajo", "Stock bajo de insumos", "Usa el stock mínimo de cada insumo (se cambia en Inventario).")}
        {interruptor("cuentas_vencidas", "Cuentas por cobrar vencidas", "Solo la ve el Administrador.",
          <div><label htmlFor="a-gracia" className="mb-1 block text-xs font-medium">Días de gracia después del vencimiento</label>
            <input id="a-gracia" inputMode="numeric" value={conf.cuentas_vencidas.dias_gracia} onChange={(e) => set("cuentas_vencidas", { dias_gracia: Math.round(num(e.target.value)) })} className={estiloInput} /></div>)}
        {error && <Aviso tipo="error">{error}</Aviso>}
        {aviso && <Aviso tipo="ok">{aviso}</Aviso>}
        {editar && <button type="submit" disabled={ocupado} className={`${botonPrimario} w-full`}>{ocupado ? "Guardando…" : "Guardar alertas"}</button>}
      </form>
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Alertas de hoy {lista && <span className="font-normal text-stone-500">· {lista.length}</span>}</h2>
        {!lista ? <p className="text-stone-500">Cargando…</p> : lista.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">Todo en orden: no hay alertas.</p>
        ) : (
          <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-amber-200 bg-white" aria-label="Alertas activas">
            {lista.map((a, i) => (
              <li key={i}><Link href={a.ruta} className="flex items-start gap-3 px-4 py-3 text-sm hover:bg-amber-50">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" aria-hidden />
                <span><span className="font-medium">{NOMBRE_ALERTA[a.tipo]}:</span> {a.texto}</span>
              </Link></li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
