"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Paperclip } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { fechaHora, kg, rendimiento } from "@/lib/formato";
import { fechaCorta, litros, type Lote } from "@/lib/leche";
import type { LoteQueso } from "@/lib/queso";
import { gs } from "@/lib/ventas";
import { NOMBRE_CATEGORIA, NOMBRE_CENTRO, type Gasto } from "@/lib/egresos";
import type { FilaAuditoria } from "@/lib/reportes";
import { VerComprobante } from "@/components/Comprobante";
import { DecidirAprobacion } from "@/components/DecidirAprobacion";
import { Aviso, estiloInput } from "@/components/ui";

const CAMPOS_LECHE: Record<string, string> = {
  fecha: "Fecha", ordene: "Ordeñe", litros: "Litros", grasa_pct: "Grasa %", proteina_pct: "Proteína %",
  temperatura_c: "Temperatura °C", observaciones: "Observaciones",
};

type Seccion = "gastos" | "queso" | "leche" | "editados";

export default function BandejaDeControl() {
  const [gastos, setGastos] = useState<Gasto[] | null>(null);
  const [quesos, setQuesos] = useState<LoteQueso[] | null>(null);
  const [leches, setLeches] = useState<Lote[] | null>(null);
  const [editados, setEditados] = useState<FilaAuditoria[] | null>(null);
  const [abierto, setAbierto] = useState<string | null>(null);
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");

  const cargar = useCallback(() => {
    api<{ results: Gasto[] }>("/gastos?estado=pendiente&page_size=200").then((r) => setGastos(r.results));
    api<{ results: LoteQueso[] }>("/lotes-queso?estado=pendiente&page_size=200").then((r) => setQuesos(r.results)).catch(() => setQuesos([]));
    api<{ results: Lote[] }>("/lotes-leche?estado=pendiente&page_size=200").then((r) => setLeches(r.results.filter((l) => l.cambios_propuestos))).catch(() => setLeches([]));
    api<FilaAuditoria[]>("/control/registros-editados?sin_revisar=1").then(setEditados).catch(() => setEditados([]));
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  async function hacer(ruta: string, cuerpo: object, mensaje: string) {
    setError(""); setAviso("");
    try {
      await api(ruta, { method: "POST", body: JSON.stringify(cuerpo) });
      setAviso(mensaje);
      setAbierto(null);
      cargar();
      return true;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar.");
      return false;
    }
  }

  const cuantos = (l: unknown[] | null) => (l ? l.length : 0);
  const resumen: [Seccion, string, number][] = [
    ["gastos", "Gastos", cuantos(gastos)],
    ["queso", "Lotes de queso", cuantos(quesos)],
    ["leche", "Correcciones de leche", cuantos(leches)],
    ["editados", "Registros editados", cuantos(editados)],
  ];
  const fila = (id: string, cabecera: React.ReactNode, cuerpo: React.ReactNode) => (
    <li key={id} className="rounded-2xl border border-stone-200 bg-white">
      <button onClick={() => setAbierto(abierto === id ? null : id)} aria-expanded={abierto === id}
        className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-left">{cabecera}</button>
      {abierto === id && <div className="space-y-3 border-t border-stone-100 p-4">{cuerpo}</div>}
    </li>
  );
  const vacio = (texto: string) => <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-5 text-center text-sm text-stone-500">{texto}</p>;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <h1 className="text-2xl font-semibold">Bandeja de control</h1>
      <nav className="grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="Resumen de la bandeja">
        {resumen.map(([id, nombre, n]) => (
          <a key={id} href={`#${id}`} className={`rounded-xl border px-3 py-2 text-sm ${n ? "border-amber-200 bg-amber-50 text-amber-900" : "border-stone-200 bg-white text-stone-500"}`}>
            <span className="block text-2xl font-semibold tabular-nums">{n}</span>{nombre}
          </a>
        ))}
      </nav>
      {aviso && <Aviso tipo="ok">{aviso}</Aviso>}
      {error && <Aviso tipo="error">{error}</Aviso>}

      <section id="gastos" className="space-y-3">
        <h2 className="text-lg font-semibold">Gastos por aprobar {gastos && gastos.length > 0 && <span className="font-normal text-stone-500">· {gs(gastos.reduce((s, g) => s + g.monto, 0))}</span>}</h2>
        {!gastos ? <p className="text-stone-500">Cargando…</p> : gastos.length === 0 ? vacio("No hay gastos esperando tu aprobación.") : (
          <ul className="space-y-3" aria-label="Gastos pendientes">
            {gastos.map((g) => fila(`g-${g.id}`, <>
              <span className="w-24 text-sm text-stone-500">{fechaCorta(g.fecha)}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{g.descripcion}</span>
                <span className="block text-xs text-stone-500">{NOMBRE_CATEGORIA[g.categoria]} · {NOMBRE_CENTRO[g.centro_costo]} · cargó {g.creado_por_nombre ?? "—"}</span>
              </span>
              {g.tiene_comprobante && <Paperclip className="h-4 w-4 text-stone-400" aria-label="Con comprobante" />}
              <span className="w-28 text-right font-semibold tabular-nums">{gs(g.monto)}</span>
            </>, <>
              {g.proveedor_nombre && <p className="text-sm">Proveedor: {g.proveedor_nombre}</p>}
              {g.comprobante_numero && <p className="text-sm">Comprobante n.º {g.comprobante_numero}</p>}
              {g.tiene_comprobante ? <VerComprobante ruta={`/gastos/${g.id}/comprobante`} tipo={g.tipo_comprobante} /> : <p className="text-sm text-stone-500">Sin foto del comprobante.</p>}
              <DecidirAprobacion idCampo={g.id}
                onAprobar={(c) => hacer(`/gastos/${g.id}/aprobar`, { comentario: c }, `Aprobado: ${g.descripcion} (${gs(g.monto)}).`)}
                onRechazar={(c) => hacer(`/gastos/${g.id}/rechazar`, { comentario: c }, `Rechazado: ${g.descripcion}. ${g.creado_por_nombre ?? "Quien lo cargó"} ve tu comentario.`)} />
              <Link href={`/gastos/${g.id}`} className="text-sm text-campo-700 hover:underline">Ver el detalle completo</Link>
            </>))}
          </ul>
        )}
      </section>

      <section id="queso" className="space-y-3">
        <h2 className="text-lg font-semibold">Lotes de queso por aprobar</h2>
        {!quesos ? <p className="text-stone-500">Cargando…</p> : quesos.length === 0 ? vacio("No hay lotes de queso esperando control de calidad.") : (
          <ul className="space-y-3" aria-label="Lotes de queso pendientes">
            {quesos.map((l) => fila(`q-${l.id}`, <>
              <span className="w-24 text-sm text-stone-500">{fechaCorta(l.fecha)}</span>
              <span className="min-w-0 flex-1">
                <span className="block font-medium">{l.codigo}</span>
                <span className="block text-xs text-stone-500">{litros(l.litros_leche)} → {kg(l.kg_obtenidos)} · elaboró {l.creado_por_nombre ?? "—"}</span>
              </span>
              <span className={`text-sm tabular-nums ${l.rendimiento_fuera_de_rango ? "font-semibold text-amber-800" : ""}`}>{rendimiento(l.rendimiento_l_kg)}</span>
            </>, <>
              {l.rendimiento_fuera_de_rango && <Aviso tipo="alerta">El rendimiento está fuera del rango esperado. Revisá los kg y la leche antes de aprobar.</Aviso>}
              <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                <div><dt className="text-stone-500">Kg obtenidos</dt><dd>{kg(l.kg_obtenidos)}</dd></div>
                <div><dt className="text-stone-500">Merma</dt><dd>{kg(l.merma_kg)}</dd></div>
                <div><dt className="text-stone-500">Kg netos</dt><dd>{kg(l.kg_netos)}</dd></div>
                <div><dt className="text-stone-500">Leche de</dt><dd>{l.origenes.map((o) => o.codigo).join(", ")}</dd></div>
              </dl>
              {l.insumos.length > 0 && <p className="text-sm text-stone-600">Insumos: {l.insumos.map((i) => `${i.nombre} ${Number(i.cantidad_consumida ?? i.cantidad_declarada).toLocaleString("es-PY")} ${i.unidad}`).join(" · ")}</p>}
              {l.observaciones && <p className="text-sm text-stone-600">“{l.observaciones}”</p>}
              <DecidirAprobacion idCampo={l.id}
                onAprobar={(c) => hacer(`/lotes-queso/${l.id}/aprobar`, { comentario: c }, `Lote ${l.codigo} aprobado: el queso queda disponible para la venta.`)}
                onRechazar={(c) => hacer(`/lotes-queso/${l.id}/rechazar`, { comentario: c }, `Lote ${l.codigo} rechazado. Quien lo elaboró ve el comentario.`)} />
              <Link href={`/queso/${l.id}`} className="text-sm text-campo-700 hover:underline">Ver el lote completo</Link>
            </>))}
          </ul>
        )}
      </section>

      <section id="leche" className="space-y-3">
        <h2 className="text-lg font-semibold">Correcciones de leche por aprobar</h2>
        {!leches ? <p className="text-stone-500">Cargando…</p> : leches.length === 0 ? vacio("No hay correcciones de leche esperando tu aprobación.") : (
          <ul className="space-y-3" aria-label="Correcciones de leche pendientes">
            {leches.map((l) => {
              const cambios = Object.entries(l.cambios_propuestos ?? {}).filter(([k]) => !k.startsWith("_"));
              return fila(`l-${l.id}`, <>
                <span className="w-24 text-sm text-stone-500">{fechaCorta(l.fecha)}</span>
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">{l.codigo}</span>
                  <span className="block text-xs text-stone-500">Propuso {l.propuesto_por_nombre ?? "—"}: {cambios.map(([k]) => CAMPOS_LECHE[k] ?? k).join(", ")}</span>
                </span>
              </>, <>
                <table className="w-full text-sm">
                  <thead className="text-left text-xs text-stone-500"><tr><th className="py-1">Campo</th><th className="py-1">Ahora</th><th className="py-1">Propuesto</th></tr></thead>
                  <tbody>{cambios.map(([k, v]) => (
                    <tr key={k}><td className="py-1">{CAMPOS_LECHE[k] ?? k}</td><td className="py-1 text-stone-500 line-through">{String((l as unknown as Record<string, unknown>)[k] ?? "—")}</td><td className="py-1 font-medium">{v ?? "—"}</td></tr>
                  ))}</tbody>
                </table>
                {l.cambios_propuestos?._motivo && <p className="text-sm text-stone-600">Motivo: “{l.cambios_propuestos._motivo}”</p>}
                <DecidirAprobacion idCampo={l.id}
                  onAprobar={() => hacer(`/lotes-leche/${l.id}/aprobar`, {}, `Corrección de ${l.codigo} aprobada y aplicada.`)}
                  onRechazar={(c) => hacer(`/lotes-leche/${l.id}/rechazar`, { motivo: c }, `Corrección de ${l.codigo} rechazada.`)} />
              </>);
            })}
          </ul>
        )}
      </section>

      <section id="editados" className="space-y-3">
        <div>
          <h2 className="text-lg font-semibold">Registros editados después de cerrados</h2>
          <p className="text-sm text-stone-500">Cambios sobre lotes cerrados o aprobados, reaperturas y anulaciones de cobros o pagos. Marcalos como revisados cuando los controles.</p>
        </div>
        {!editados ? <p className="text-stone-500">Cargando…</p> : editados.length === 0 ? vacio("No hay cambios sin revisar.") : (
          <ul className="space-y-3" aria-label="Registros editados">
            {editados.map((f) => fila(`a-${f.id}`, <>
              <span className="w-32 text-sm text-stone-500">{fechaHora(f.fecha)}</span>
              <span className="min-w-0 flex-1">
                <span className="block font-medium">{f.accion_nombre}: {f.registro}</span>
                <span className="block text-xs text-stone-500">{f.entidad_nombre} · {f.usuario}{f.motivo && ` · “${f.motivo}”`}</span>
              </span>
            </>, <Revisar fila={f} onRevisar={(nota) => hacer(`/control/registros-editados/${f.id}/revisar`, { nota }, "Marcado como revisado.")} />))}
          </ul>
        )}
        <Link href="/reportes/aprobaciones" className="inline-block text-sm text-campo-700 hover:underline">Ver el historial de aprobaciones</Link>
      </section>
    </div>
  );
}

function Revisar({ fila, onRevisar }: { fila: FilaAuditoria; onRevisar: (nota: string) => Promise<boolean> }) {
  const [nota, setNota] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const cambios = Object.entries(fila.cambios ?? {}).filter(([k]) => !["antes", "despues"].includes(k));
  return (
    <>
      {cambios.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-stone-500"><tr><th className="py-1">Campo</th><th className="py-1">Antes</th><th className="py-1">Después</th></tr></thead>
          <tbody>{cambios.map(([k, v]) => {
            const par = Array.isArray(v) ? v : [null, v];
            return <tr key={k}><td className="py-1">{CAMPOS_LECHE[k] ?? k}</td><td className="py-1 text-stone-500">{String(par[0] ?? "—")}</td><td className="py-1 font-medium">{String(par[1] ?? "—")}</td></tr>;
          })}</tbody>
        </table>
      )}
      {fila.ruta && <Link href={fila.ruta} className="text-sm text-campo-700 hover:underline">Abrir el registro</Link>}
      <div className="flex flex-wrap gap-2">
        <input aria-label="Nota de la revisión (opcional)" placeholder="Nota (opcional)" value={nota} onChange={(e) => setNota(e.target.value)} className={`${estiloInput} min-w-0 flex-1`} />
        <button disabled={ocupado} onClick={async () => { setOcupado(true); if (!(await onRevisar(nota))) setOcupado(false); }}
          className="inline-flex items-center gap-1.5 rounded-xl bg-campo-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
          <CheckCircle2 className="h-4 w-4" aria-hidden /> Marcar revisado
        </button>
      </div>
    </>
  );
}
