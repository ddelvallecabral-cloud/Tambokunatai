"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cantidad, fechaHora, kg, rendimiento } from "@/lib/formato";
import { NOMBRE_MOTIVO, NOMBRE_TIPO } from "@/lib/inventario";
import { fechaCorta, litros } from "@/lib/leche";
import { ESTADO_QUESO, NOMBRE_ACCION, type LoteQueso, type ResumenQueso, type Trazabilidad } from "@/lib/queso";
import { Pasos } from "@/components/Pasos";
import { Aviso, botonPrimario, botonSecundario, estiloInput, Insignia, Tarjeta } from "@/components/ui";

const limpiar = (v: string) => v.replace(/[^0-9.,]/g, "");
const num = (v: string) => Number((v || "0").replace(",", "."));
const texto = (v: string | null | undefined) => (v == null ? "" : String(Number(v)).replace(".", ","));

export default function DetalleLoteQueso() {
  return (
    <Suspense fallback={<p className="text-stone-500">Cargando…</p>}>
      <Detalle />
    </Suspense>
  );
}

function Detalle() {
  const { id } = useParams<{ id: string }>();
  const recienIniciado = useSearchParams().get("iniciado") === "1";
  const { usuario, puede } = useAuth();
  const [lote, setLote] = useState<LoteQueso | null>(null);
  const [traza, setTraza] = useState<Trazabilidad | null>(null);
  const [rango, setRango] = useState<ResumenQueso["rango_rendimiento"] | null>(null);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "error"; texto: string } | null>(
    recienIniciado ? { tipo: "ok", texto: "Lote iniciado: la leche se descontó y los insumos quedaron reservados." } : null,
  );
  const [ocupado, setOcupado] = useState(false);

  const cargar = useCallback(() => {
    api<LoteQueso>(`/lotes-queso/${id}`).then(setLote);
    api<Trazabilidad>(`/lotes-queso/${id}/trazabilidad`).then(setTraza);
  }, [id]);
  useEffect(() => {
    cargar();
    api<ResumenQueso>("/queso/resumen").then((r) => setRango(r.rango_rendimiento));
  }, [cargar]);

  async function accion(ruta: string, cuerpo: object, exito: string) {
    setOcupado(true);
    setAviso(null);
    try {
      const l = await api<LoteQueso>(`/lotes-queso/${id}/${ruta}`, { method: "POST", body: JSON.stringify(cuerpo) });
      setLote(l);
      setAviso({ tipo: "ok", texto: exito });
      api<Trazabilidad>(`/lotes-queso/${id}/trazabilidad`).then(setTraza);
    } catch (err) {
      setAviso({ tipo: "error", texto: err instanceof ApiError ? err.message : "No se pudo completar. Revisá la señal." });
    } finally {
      setOcupado(false);
    }
  }

  if (!lote) return <p className="text-stone-500">Cargando…</p>;
  const estado = ESTADO_QUESO[lote.estado];
  const propio = usuario?.id === lote.creado_por;
  const paso = lote.estado === "borrador" || lote.estado === "rechazado" ? 2 : 3;

  return (
    <div className="space-y-4">
      <Link href="/queso" className="inline-flex items-center gap-1 text-sm text-campo-700"><ArrowLeft className="h-4 w-4" aria-hidden /> Lotes</Link>

      <section className="space-y-4 rounded-2xl border border-stone-200 bg-white p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold">{lote.codigo}</h2>
            <p className="text-sm text-stone-500">
              {fechaCorta(lote.fecha)} · iniciado por {lote.creado_por_nombre ?? "—"}
              {lote.cerrado_por_nombre && ` · cerrado por ${lote.cerrado_por_nombre}`}
              {lote.aprobado_por_nombre && ` · aprobado por ${lote.aprobado_por_nombre}`}
            </p>
          </div>
          <Insignia color={estado.color}>{estado.nombre}</Insignia>
        </div>
        {lote.estado !== "anulado" && <Pasos actual={paso} />}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Tarjeta titulo="Leche usada" valor={litros(lote.litros_leche)} />
          <Tarjeta titulo="Kg obtenidos" valor={kg(lote.kg_obtenidos)} detalle={Number(lote.merma_kg) > 0 ? `Merma ${kg(lote.merma_kg)}` : undefined} />
          <Tarjeta titulo="Kg al inventario" valor={kg(lote.kg_netos)} />
          <Tarjeta
            titulo="Rendimiento"
            valor={<span className={lote.rendimiento_fuera_de_rango ? "text-red-700" : ""}>{rendimiento(lote.rendimiento_l_kg)}</span>}
            detalle={rango && `Esperado ${rango.min} a ${rango.max} L/kg`}
          />
        </div>
        {lote.rendimiento_fuera_de_rango && (
          <p role="alert" className="flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">
            <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
            El rendimiento está fuera del rango esperado. Revisá los kg y la leche antes de aprobar.
          </p>
        )}
        {lote.estado === "rechazado" && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800"><strong>Rechazado:</strong> {lote.motivo_estado}</p>
        )}
        {lote.estado === "aprobado" && lote.motivo_estado && (
          <p className="rounded-lg bg-campo-50 px-3 py-2 text-sm text-campo-900"><strong>Comentario:</strong> {lote.motivo_estado}</p>
        )}
        {lote.estado === "anulado" && (
          <p className="rounded-lg bg-stone-100 px-3 py-2 text-sm text-stone-700"><strong>Cancelado:</strong> {lote.motivo_estado}</p>
        )}
        {aviso && <Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso>}
      </section>

      {(lote.estado === "borrador" || lote.estado === "rechazado") && puede("queso.lote.enviar") && (
        <Cierre lote={lote} rango={rango} ocupado={ocupado}
          cerrar={(cuerpo) => accion("cerrar", cuerpo, "Lote cerrado y enviado a aprobación del Administrador.")} />
      )}

      {lote.estado === "borrador" && puede("queso.lote.gestionar") && (propio || puede("queso.lote.aprobar")) && (
        <Cancelar ocupado={ocupado} cancelar={(motivo) => accion("cancelar", { motivo }, "Lote cancelado: se liberaron los insumos y la leche.")} />
      )}

      {lote.estado === "pendiente" &&
        (puede("queso.lote.aprobar") ? (
          <Aprobacion ocupado={ocupado}
            aprobar={(comentario) => accion("aprobar", { comentario }, "Lote aprobado: el queso queda disponible para la venta.")}
            rechazar={(comentario) => accion("rechazar", { comentario }, "Lote rechazado. Quien lo elaboró ve el comentario y puede corregirlo.")} />
        ) : (
          <p className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Esperando la aprobación del Administrador.</p>
        ))}

      {traza && <VistaTrazabilidad t={traza} />}
    </div>
  );
}

function Cierre({ lote, rango, ocupado, cerrar }: {
  lote: LoteQueso; rango: ResumenQueso["rango_rendimiento"] | null; ocupado: boolean; cerrar: (cuerpo: object) => void;
}) {
  const corrigiendo = lote.estado === "rechazado";
  const [kgObt, setKg] = useState(texto(lote.kg_obtenidos));
  const [merma, setMerma] = useState(texto(lote.merma_kg) === "0" ? "" : texto(lote.merma_kg));
  const [consumos, setConsumos] = useState<Record<string, string>>(() =>
    Object.fromEntries(lote.insumos.map((i) => [i.insumo, texto(corrigiendo && i.cantidad_consumida != null ? i.cantidad_consumida : i.cantidad_declarada)])),
  );
  const [observaciones, setObservaciones] = useState(lote.observaciones);
  const [error, setError] = useState("");

  const valor = num(kgObt);
  const rend = valor > 0 ? Number(lote.litros_leche) / valor : null;
  const fuera = rend != null && rango != null && (rend < Number(rango.min) || rend > Number(rango.max));

  function enviar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!(valor > 0)) {
      setError("Cargá los kg de queso obtenidos: sin ese dato el lote no se puede cerrar.");
      return;
    }
    cerrar({
      kg_obtenidos: String(valor),
      merma_kg: String(num(merma)),
      consumos: Object.entries(consumos).map(([insumo, v]) => ({ insumo, cantidad: String(num(v)) })),
      observaciones,
    });
  }

  return (
    <form onSubmit={enviar} className="space-y-4 rounded-2xl border border-campo-200 bg-white p-5" aria-labelledby="t-cierre">
      <div>
        <h3 id="t-cierre" className="font-semibold">{corrigiendo ? "Corregir y volver a enviar" : "Paso 2: cerrar el lote"}</h3>
        <p className="text-sm text-stone-500">Al cerrar, se descuenta lo que se usó de verdad, el queso entra al inventario y el lote pasa a aprobación.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="sm:col-span-2">
          <label htmlFor="kg" className="mb-1 block text-sm font-medium">Kg de queso obtenidos</label>
          <div className="relative">
            <input id="kg" inputMode="decimal" autoComplete="off" placeholder="0" value={kgObt} onChange={(e) => setKg(limpiar(e.target.value))}
              className={`${estiloInput} py-4 pr-12 text-3xl font-semibold tabular-nums`} />
            <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-lg text-stone-400">kg</span>
          </div>
        </div>
        <div>
          <label htmlFor="merma" className="mb-1 block text-sm font-medium">Merma (kg)</label>
          <input id="merma" inputMode="decimal" placeholder="0" value={merma} onChange={(e) => setMerma(limpiar(e.target.value))} className={`${estiloInput} py-4 text-xl tabular-nums`} />
        </div>
      </div>
      <p aria-live="polite" className={`rounded-lg px-3 py-2 text-sm ${fuera ? "bg-red-50 text-red-800" : "bg-stone-50 text-stone-700"}`}>
        {rend == null ? "El rendimiento se calcula al cargar los kg." : (
          <>Rendimiento: <strong>{rendimiento(rend.toFixed(2))}</strong> ({litros(lote.litros_leche)} ÷ {kg(valor)})
            {fuera && rango && <> · fuera del rango esperado ({rango.min} a {rango.max} L/kg)</>}</>
        )}
      </p>

      {lote.insumos.length > 0 && (
        <div>
          <p className="mb-1 text-sm font-medium">Insumos usados de verdad</p>
          <ul className="divide-y divide-stone-100 rounded-xl border border-stone-200">
            {lote.insumos.map((i) => (
              <li key={i.insumo} className="flex items-center gap-3 px-3 py-2">
                <label htmlFor={`c-${i.insumo}`} className="flex-1">
                  {i.nombre}
                  <span className="block text-xs text-stone-500">Declarado: {cantidad(i.cantidad_declarada, i.unidad)}</span>
                </label>
                <div className="relative w-32">
                  <input id={`c-${i.insumo}`} inputMode="decimal" value={consumos[i.insumo] ?? ""}
                    onChange={(e) => setConsumos((c) => ({ ...c, [i.insumo]: limpiar(e.target.value) }))}
                    className={`${estiloInput} py-2 pr-12 text-right tabular-nums`} />
                  <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-stone-400">{i.unidad === "unidad" ? "u." : i.unidad}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div>
        <label htmlFor="obs-c" className="mb-1 block text-xs font-medium">Observaciones</label>
        <textarea id="obs-c" rows={2} value={observaciones} onChange={(e) => setObservaciones(e.target.value)} className={estiloInput} />
      </div>
      {error && <Aviso tipo="error">{error}</Aviso>}
      <button disabled={ocupado} className={`${botonPrimario} w-full py-4 text-lg`}>
        {ocupado ? "Guardando…" : corrigiendo ? "Corregir y enviar a aprobación" : "Cerrar lote y enviar a aprobación"}
      </button>
    </form>
  );
}

function Aprobacion({ ocupado, aprobar, rechazar }: { ocupado: boolean; aprobar: (c: string) => void; rechazar: (c: string) => void }) {
  const [comentario, setComentario] = useState("");
  const [error, setError] = useState("");
  return (
    <section className="space-y-3 rounded-2xl border border-amber-200 bg-amber-50 p-5" aria-labelledby="t-aprob">
      <h3 id="t-aprob" className="font-semibold text-amber-950">Aprobación</h3>
      <div>
        <label htmlFor="comentario" className="mb-1 block text-sm font-medium">Comentario (obligatorio para rechazar)</label>
        <textarea id="comentario" rows={2} value={comentario} onChange={(e) => setComentario(e.target.value)} className={estiloInput} />
      </div>
      {error && <Aviso tipo="error">{error}</Aviso>}
      <div className="flex flex-wrap gap-2">
        <button disabled={ocupado} onClick={() => aprobar(comentario)} className={botonPrimario}>Aprobar</button>
        <button disabled={ocupado} className={`${botonSecundario} border-red-300 text-red-700`}
          onClick={() => (comentario.trim() ? (setError(""), rechazar(comentario)) : setError("Escribí qué hay que corregir."))}>
          Rechazar
        </button>
      </div>
    </section>
  );
}

function Cancelar({ ocupado, cancelar }: { ocupado: boolean; cancelar: (motivo: string) => void }) {
  const [abierto, setAbierto] = useState(false);
  const [motivo, setMotivo] = useState("");
  if (!abierto) {
    return <button onClick={() => setAbierto(true)} className="text-sm font-medium text-red-700 underline">Cancelar esta elaboración</button>;
  }
  return (
    <div className="space-y-2 rounded-2xl border border-red-200 bg-red-50 p-4">
      <label htmlFor="motivo-c" className="block text-sm font-medium text-red-900">¿Por qué se cancela?</label>
      <input id="motivo-c" value={motivo} onChange={(e) => setMotivo(e.target.value)} className={estiloInput} />
      <p className="text-xs text-red-800">Los insumos reservados vuelven al stock y la leche queda otra vez lista para queso.</p>
      <div className="flex gap-2">
        <button disabled={ocupado || !motivo.trim()} onClick={() => cancelar(motivo)} className="rounded-lg bg-red-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">Cancelar lote</button>
        <button onClick={() => setAbierto(false)} className="px-3 py-2 text-sm">Volver</button>
      </div>
    </div>
  );
}

function VistaTrazabilidad({ t }: { t: Trazabilidad }) {
  const vacas = new Set(t.origen_leche.flatMap((o) => o.vacas.map((v) => v.caravana)));
  const eslabones = [
    { titulo: "Vacas", valor: vacas.size ? `${vacas.size} vacas` : "Sin detalle" },
    { titulo: "Lotes de leche", valor: `${t.origen_leche.length}` },
    { titulo: "Lote de queso", valor: t.codigo },
    { titulo: "Clientes", valor: "Fase 4" },
  ];
  return (
    <section className="space-y-5 rounded-2xl border border-stone-200 bg-white p-5" aria-labelledby="t-traza">
      <h3 id="t-traza" className="font-semibold">Trazabilidad</h3>
      <ol className="flex flex-wrap items-center gap-2 text-sm" aria-label="Cadena del lote">
        {eslabones.map((e, i) => (
          <li key={e.titulo} className="flex items-center gap-2">
            <span className={`rounded-lg border px-3 py-2 ${i === 2 ? "border-campo-600 bg-campo-50" : i === 3 ? "border-dashed border-stone-300 text-stone-400" : "border-stone-200"}`}>
              <span className="block text-xs text-stone-500">{e.titulo}</span>
              <span className="font-medium">{e.valor}</span>
            </span>
            {i < eslabones.length - 1 && <ArrowRight className="h-4 w-4 text-stone-400" aria-hidden />}
          </li>
        ))}
      </ol>

      <div>
        <h4 className="mb-2 text-sm font-semibold">De dónde vino la leche</h4>
        <ul className="space-y-2">
          {t.origen_leche.map((o) => (
            <li key={o.lote_leche + o.litros_usados} className="rounded-xl border border-stone-200 p-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <Link href={`/leche/lotes/${o.lote_leche}`} className="font-medium text-campo-800 hover:underline">{o.codigo}</Link>
                <span className="text-sm tabular-nums">{litros(o.litros_usados)} de {litros(o.litros_del_lote)} del lote{!o.vigente && " · liberados al cancelar"}</span>
              </div>
              <p className="text-xs text-stone-500">
                {fechaCorta(o.fecha)}, {o.ordene === "manana" ? "mañana" : "tarde"}
                {o.grasa_pct && ` · grasa ${o.grasa_pct}%`}{o.proteina_pct && ` · proteína ${o.proteina_pct}%`}{o.temperatura_c && ` · ${o.temperatura_c} °C`}
              </p>
              {o.vacas.length > 0 && (
                <details className="mt-2 text-sm">
                  <summary className="cursor-pointer text-campo-700">{o.vacas.length} vacas en ese ordeñe</summary>
                  <ul className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-4">
                    {o.vacas.map((v) => (
                      <li key={v.caravana} className="flex justify-between gap-2 tabular-nums"><span>{v.caravana} {v.nombre}</span><span className="text-stone-500">{litros(v.litros)}</span></li>
                    ))}
                  </ul>
                </details>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div>
        <h4 className="mb-2 text-sm font-semibold">Insumos</h4>
        {t.insumos.length === 0 ? <p className="text-sm text-stone-500">No se declararon insumos.</p> : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-stone-500"><tr><th className="py-1">Insumo</th><th className="py-1 text-right">Declarado</th><th className="py-1 text-right">Consumido</th><th className="hidden py-1 pl-4 sm:table-cell">Lote del proveedor</th></tr></thead>
            <tbody className="divide-y divide-stone-100">
              {t.insumos.map((i) => (
                <tr key={i.insumo}>
                  <td className="py-1.5">{i.nombre}</td>
                  <td className="py-1.5 text-right tabular-nums text-stone-500">{cantidad(i.declarada, i.unidad)}</td>
                  <td className="py-1.5 text-right tabular-nums">{cantidad(i.consumida, i.unidad)}</td>
                  <td className="hidden py-1.5 pl-4 text-stone-500 sm:table-cell">{i.lotes_proveedor_recientes.join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <details>
        <summary className="cursor-pointer text-sm font-semibold">Movimientos de inventario ({t.movimientos.length})</summary>
        <ul className="mt-2 space-y-1 text-sm">
          {t.movimientos.map((m, i) => (
            <li key={i} className="flex flex-wrap justify-between gap-2 border-b border-stone-100 py-1">
              <span>{NOMBRE_TIPO[m.tipo]} · {m.insumo ?? (m.item === "leche" ? `Leche ${m.lote_leche}` : "Queso")} <span className="text-stone-500">({NOMBRE_MOTIVO[m.motivo] ?? m.motivo})</span></span>
              <span className="tabular-nums text-stone-600">{cantidad(m.cantidad, m.unidad)} · {fechaHora(m.fecha)}</span>
            </li>
          ))}
        </ul>
      </details>

      <div>
        <h4 className="mb-2 text-sm font-semibold">Historial</h4>
        <ol className="space-y-1 text-sm">
          {t.historial.filter((h) => NOMBRE_ACCION[h.accion]).map((h, i) => (
            <li key={i} className="flex gap-2">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-campo-600" aria-hidden />
              <span>
                <strong>{NOMBRE_ACCION[h.accion]}</strong> · {h.usuario ?? "sistema"} · {fechaHora(h.fecha)}
                {h.motivo && <span className="text-stone-600"> · “{h.motivo}”</span>}
              </span>
            </li>
          ))}
        </ol>
      </div>
      <p className="text-xs text-stone-500">Los clientes que compraron este queso aparecen acá cuando se registren las ventas (Fase 4).</p>
    </section>
  );
}
