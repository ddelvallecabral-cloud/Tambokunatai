"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, ClipboardCheck, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fechaCorta, litros, ORDENES, type Tablero } from "@/lib/leche";

const COLOR_DESTINO: Record<string, string> = {
  elaboracion_queso: "bg-campo-600",
  venta: "bg-sky-500",
  descarte: "bg-red-400",
  pendiente: "bg-stone-300",
};
const NOMBRE: Record<string, string> = { elaboracion_queso: "Queso", venta: "Venta", descarte: "Descarte", pendiente: "Sin destino" };

export default function PanelLeche() {
  const { puede } = useAuth();
  const [t, setT] = useState<Tablero | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Tablero>("/leche/tablero").then(setT).catch(() => setError("No se pudo cargar el panel."));
  }, []);

  if (error) return <p className="text-red-700">{error}</p>;
  if (!t) return <p className="text-stone-500">Cargando…</p>;

  const total = Number(t.hoy.total_litros);
  const maximo = Math.max(...t.ultimos_14_dias.map((d) => Number(d.litros)), Number(t.umbral_litros_diarios ?? 0), 1);
  const umbral = Number(t.umbral_litros_diarios ?? 0);

  return (
    <div className="space-y-4">
      {t.alertas.map((a) => (
        <div key={a.fecha + a.mensaje} role="alert" className="flex items-start gap-2 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {a.mensaje}
        </div>
      ))}
      {puede("leche.lote.aprobar") && t.correcciones_pendientes > 0 && (
        <Link href="/leche/lotes?estado=pendiente" className="flex items-center gap-2 rounded-lg bg-sky-50 px-4 py-3 text-sm font-medium text-sky-900">
          <ClipboardCheck className="h-4 w-4" aria-hidden />
          {t.correcciones_pendientes === 1 ? "1 corrección espera" : `${t.correcciones_pendientes} correcciones esperan`} tu aprobación
        </Link>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <section className="rounded-2xl border border-stone-200 bg-white p-5" aria-labelledby="hoy">
          <h2 id="hoy" className="text-sm font-medium text-stone-500">Hoy · {fechaCorta(t.fecha)}</h2>
          <p className="mt-1 text-4xl font-semibold tabular-nums" data-testid="litros-hoy">{litros(total)}</p>
          <dl className="mt-3 flex gap-6 text-sm">
            {ORDENES.map((o) => (
              <div key={o.valor}>
                <dt className="text-stone-500">{o.nombre}</dt>
                <dd className="font-medium tabular-nums">
                  {t.hoy.ordenes_faltantes.includes(o.valor) ? <span className="text-stone-400">sin cargar</span> : litros(t.hoy.por_ordene[o.valor])}
                </dd>
              </div>
            ))}
          </dl>
          {total > 0 && (
            <>
              <div className="mt-4 flex h-2.5 overflow-hidden rounded-full bg-stone-100" aria-hidden>
                {Object.entries(t.hoy.por_destino).map(([k, v]) =>
                  Number(v) > 0 ? <div key={k} className={COLOR_DESTINO[k]} style={{ width: `${(Number(v) / total) * 100}%` }} /> : null,
                )}
              </div>
              <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-stone-600">
                {Object.entries(t.hoy.por_destino).map(([k, v]) => (
                  <li key={k} className="flex items-center gap-1.5">
                    <span className={`h-2 w-2 rounded-full ${COLOR_DESTINO[k]}`} aria-hidden />
                    {NOMBRE[k]} {litros(v)}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>

        <section className="rounded-2xl border border-stone-200 bg-white p-5" aria-labelledby="mes">
          <h2 id="mes" className="text-sm font-medium text-stone-500">Este mes</h2>
          <p className="mt-1 text-4xl font-semibold tabular-nums" data-testid="litros-mes">{litros(t.mes.litros)}</p>
          <dl className="mt-3 flex gap-6 text-sm">
            <div>
              <dt className="text-stone-500">Promedio diario</dt>
              <dd className="font-medium tabular-nums">{litros(t.mes.promedio_diario)}</dd>
            </div>
            <div>
              <dt className="text-stone-500">Días con carga</dt>
              <dd className="font-medium tabular-nums">{t.mes.dias_con_carga}</dd>
            </div>
          </dl>
        </section>
      </div>

      <section className="rounded-2xl border border-stone-200 bg-white p-5" aria-labelledby="dias">
        <div className="flex items-baseline justify-between">
          <h2 id="dias" className="text-sm font-medium text-stone-500">Últimos 14 días</h2>
          {umbral > 0 && <span className="text-xs text-stone-500">Línea: mínimo de {litros(umbral)}</span>}
        </div>
        <div className="relative mt-4 flex h-36 items-end gap-1" role="img" aria-label="Litros por día de los últimos 14 días">
          {umbral > 0 && (
            <div className="pointer-events-none absolute inset-x-0 border-t border-dashed border-amber-500" style={{ bottom: `${(umbral / maximo) * 100}%` }} />
          )}
          {t.ultimos_14_dias.map((d) => {
            const v = Number(d.litros);
            const bajo = umbral > 0 && v > 0 && v < umbral;
            return (
              <div key={d.fecha} className="group flex h-full flex-1 flex-col justify-end" title={`${fechaCorta(d.fecha)}: ${litros(v)}`}>
                <div className={`rounded-t ${bajo ? "bg-amber-400" : d.fecha === t.fecha ? "bg-campo-700" : "bg-campo-500/70"}`} style={{ height: `${(v / maximo) * 100}%` }} />
              </div>
            );
          })}
        </div>
        <div className="mt-1 flex justify-between text-[11px] text-stone-500">
          <span>{fechaCorta(t.ultimos_14_dias[0].fecha)}</span>
          <span>Hoy</span>
        </div>
      </section>

      {puede("leche.lote.gestionar") && (
        <Link href="/leche/registrar" className="flex items-center justify-center gap-2 rounded-xl bg-campo-700 py-4 text-lg font-semibold text-white hover:bg-campo-900">
          <Plus className="h-5 w-5" aria-hidden /> Registrar ordeñe
        </Link>
      )}
    </div>
  );
}
