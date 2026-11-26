"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AlertTriangle, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { kg, rendimiento } from "@/lib/formato";
import { litros } from "@/lib/leche";
import { NOMBRE_CATEGORIA, NOMBRE_CENTRO } from "@/lib/egresos";
import { gsSigno, NOMBRE_ALERTA, pct, type Tablero as Datos } from "@/lib/reportes";
import { gs } from "@/lib/ventas";
import { BarrasDiarias, BarrasHorizontales } from "@/components/Graficos";
import { Aviso, Tarjeta } from "@/components/ui";

const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`;

export function Tablero() {
  const { puede } = useAuth();
  const [d, setD] = useState<Datos | null>(null);
  const [error, setError] = useState(false);
  const [minimo, setMinimo] = useState<number | null>(null);

  useEffect(() => {
    api<Datos>("/tablero").then(setD).catch(() => setError(true));
    api<{ produccion_baja: { activa: boolean; litros_minimos: number } }>("/alertas/configuracion")
      .then((c) => setMinimo(c.produccion_baja.activa ? c.produccion_baja.litros_minimos : null)).catch(() => {});
  }, []);

  if (error) return <Aviso tipo="error">No se pudo cargar el tablero.</Aviso>;
  if (!d) return <p className="text-stone-500">Cargando el tablero…</p>;
  const { operativo: op, financiero: fin, pendientes } = d;
  const totalPend = pendientes ? pendientes.gastos + pendientes.lotes_queso + pendientes.correcciones_leche + pendientes.registros_editados : 0;

  return (
    <div className="space-y-6" data-testid="tablero">
      {pendientes && totalPend > 0 && (
        <Link href="/aprobaciones" className="flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <span>
            <b>{totalPend}</b> {totalPend === 1 ? "cosa espera" : "cosas esperan"} tu control:{" "}
            {[
              pendientes.gastos && plural(pendientes.gastos, "gasto", "gastos"),
              pendientes.lotes_queso && plural(pendientes.lotes_queso, "lote de queso", "lotes de queso"),
              pendientes.correcciones_leche && plural(pendientes.correcciones_leche, "corrección de leche", "correcciones de leche"),
              pendientes.registros_editados && plural(pendientes.registros_editados, "registro editado", "registros editados"),
            ].filter(Boolean).join(" · ")}
          </span>
          <ChevronRight className="h-4 w-4 shrink-0" aria-hidden />
        </Link>
      )}

      <section aria-labelledby="t-prod" className="space-y-3">
        <h2 id="t-prod" className="text-lg font-semibold">Producción</h2>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Tarjeta titulo="Leche hoy" valor={litros(op.leche.hoy)} />
          <Tarjeta titulo="Leche del mes" valor={litros(op.leche.mes)} />
          <Tarjeta titulo="Queso hoy" valor={kg(op.queso.hoy_kg)} />
          <Tarjeta titulo="Queso del mes" valor={kg(op.queso.mes_kg)} detalle={`${plural(op.queso.mes_lotes, "lote", "lotes")} · merma ${kg(op.queso.mes_merma)}`} />
        </div>
        <div className="grid gap-3 lg:grid-cols-[1fr_16rem]">
          <div className="rounded-2xl border border-stone-200 bg-white p-4">
            <BarrasDiarias etiqueta="Leche por día, últimos 30 días" unidad="L" minimo={minimo}
              datos={op.leche.ultimos_30.map((x) => ({ fecha: x.fecha, valor: Number(x.litros) }))} />
          </div>
          <Tarjeta titulo="Rendimiento del mes" valor={rendimiento(op.queso.rendimiento_mes)}
            detalle={op.queso.rendimiento_mes ? `${litros(op.queso.mes_litros)} para ${kg(op.queso.mes_kg)}` : "Sin lotes cerrados este mes"} />
        </div>
      </section>

      {d.alertas.length > 0 && (
        <section aria-labelledby="t-alertas" className="space-y-2">
          <div className="flex items-baseline justify-between">
            <h2 id="t-alertas" className="text-lg font-semibold">Alertas</h2>
            {puede("configuracion.gestionar") && <Link href="/reportes/alertas" className="text-sm text-campo-700 hover:underline">Configurar</Link>}
          </div>
          <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-amber-200 bg-white" aria-label="Alertas">
            {d.alertas.slice(0, 8).map((a, i) => (
              <li key={i}>
                <Link href={a.ruta} className="flex items-start gap-3 px-4 py-3 text-sm hover:bg-amber-50">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" aria-hidden />
                  <span className="min-w-0 flex-1"><span className="font-medium">{NOMBRE_ALERTA[a.tipo]}:</span> {a.texto}</span>
                </Link>
              </li>
            ))}
          </ul>
          {d.alertas.length > 8 && <p className="text-xs text-stone-500">Y {d.alertas.length - 8} alertas más.</p>}
        </section>
      )}

      {fin && (
        <>
          <section aria-labelledby="t-plata" className="space-y-3">
            <div className="flex items-baseline justify-between">
              <h2 id="t-plata" className="text-lg font-semibold">Plata del mes</h2>
              <Link href="/reportes" className="text-sm text-campo-700 hover:underline">Ver reportes</Link>
            </div>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Tarjeta titulo="Ingresos" valor={gs(fin.ingresos_mes.total)}
                detalle={`Leche ${gs(fin.ingresos_mes.leche)} · Queso ${gs(fin.ingresos_mes.queso)}`} />
              <Tarjeta titulo="Gastos aprobados" valor={gs(fin.gastos_mes.total)}
                detalle={fin.gastos_mes.pendientes.cantidad ? `+ ${gs(fin.gastos_mes.pendientes.total)} sin aprobar` : "Nada pendiente"} />
              <Tarjeta titulo="Compras de insumos" valor={gs(fin.compras_mes)} />
              <Tarjeta titulo="Resultado" valor={<span className={fin.resultado_mes < 0 ? "text-red-700" : "text-campo-800"}>{gsSigno(fin.resultado_mes)}</span>}
                detalle="Ingresos − gastos − compras" />
            </div>
          </section>

          <section aria-labelledby="t-margen" className="space-y-3">
            <h2 id="t-margen" className="text-lg font-semibold">Margen bruto por producto</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {fin.margen_productos.map((p) => (
                <div key={p.producto} className="rounded-2xl border border-stone-200 bg-white p-4" data-testid={`margen-${p.producto}`}>
                  <div className="flex items-baseline justify-between">
                    <p className="font-medium">{p.nombre}</p>
                    <p className="text-sm text-stone-500">{Number(p.cantidad).toLocaleString("es-PY")} {p.unidad} vendidos</p>
                  </div>
                  <p className="mt-1 text-2xl font-semibold tabular-nums">{gsSigno(p.margen)} <span className="text-base font-normal text-stone-500">{pct(p.margen_pct)}</span></p>
                  <p className="mt-1 text-xs text-stone-500">Vendido {gs(p.ingresos)} · costo de producirlo {gs(p.costo)}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="grid gap-3 lg:grid-cols-2">
            <div className="rounded-2xl border border-stone-200 bg-white p-4">
              <h3 className="mb-3 font-semibold">Gastos por categoría</h3>
              <BarrasHorizontales formato={(v) => gs(v)} filas={fin.gastos_mes.por_categoria.map((g) => ({ nombre: NOMBRE_CATEGORIA[g.categoria] ?? g.categoria, valor: g.total, detalle: plural(g.cantidad, "gasto", "gastos") }))} />
            </div>
            <div className="rounded-2xl border border-stone-200 bg-white p-4">
              <h3 className="mb-3 font-semibold">Gastos por centro de costo</h3>
              <BarrasHorizontales formato={(v) => gs(v)} filas={fin.gastos_mes.por_centro.map((g) => ({ nombre: NOMBRE_CENTRO[g.centro_costo] ?? g.centro_costo, valor: g.total, detalle: plural(g.cantidad, "gasto", "gastos") }))} />
            </div>
          </section>

          <section className="grid grid-cols-2 gap-3">
            <Link href="/ventas/cuentas" className="rounded-2xl border border-stone-200 bg-white p-4 hover:border-campo-300">
              <p className="text-sm text-stone-500">Nos deben</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">{gs(fin.cuentas.por_cobrar.total)}</p>
              <p className={`mt-1 text-xs ${fin.cuentas.por_cobrar.vencido ? "font-medium text-red-700" : "text-stone-500"}`}>
                {fin.cuentas.por_cobrar.vencido ? `${gs(fin.cuentas.por_cobrar.vencido)} vencido` : "Nada vencido"} · {plural(fin.cuentas.por_cobrar.cuentas, "cuenta", "cuentas")}
              </p>
            </Link>
            <Link href="/compras/cuentas" className="rounded-2xl border border-stone-200 bg-white p-4 hover:border-campo-300">
              <p className="text-sm text-stone-500">Debemos</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">{gs(fin.cuentas.por_pagar.total)}</p>
              <p className={`mt-1 text-xs ${fin.cuentas.por_pagar.vencido ? "font-medium text-red-700" : "text-stone-500"}`}>
                {fin.cuentas.por_pagar.vencido ? `${gs(fin.cuentas.por_pagar.vencido)} vencido` : "Nada vencido"} · {plural(fin.cuentas.por_pagar.cuentas, "cuenta", "cuentas")}
              </p>
            </Link>
          </section>
        </>
      )}
    </div>
  );
}
