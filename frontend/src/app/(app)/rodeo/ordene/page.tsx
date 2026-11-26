"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { DESTINOS, hoyISO, litros as fmtLitros, ORDENES, type Ordene, type TipoDestino } from "@/lib/leche";
import { enviarPlanilla, type Planilla } from "@/lib/rodeo";
import { Aviso, botonPrimario, estiloInput } from "@/components/ui";

const ordenePorHora = (): Ordene => (new Date().getHours() < 13 ? "manana" : "tarde");
const limpiar = (v: string) => v.replace(/[^0-9.,]/g, "");
const valor = (v: string) => Number(v.replace(",", "."));

export default function OrdenePorVaca() {
  const [fecha, setFecha] = useState(hoyISO);
  const [ordene, setOrdene] = useState<Ordene>(ordenePorHora);
  const [planilla, setPlanilla] = useState<Planilla | null>(null);
  const [litros, setLitros] = useState<Record<string, string>>({});
  const [destino, setDestino] = useState<TipoDestino | "pendiente">("pendiente");
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState("");
  const [exito, setExito] = useState<{ texto: string; id?: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const campos = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    setPlanilla(null);
    setError("");
    api<Planilla>(`/rodeo/ordene?fecha=${fecha}&ordene=${ordene}`)
      .then((p) => {
        setPlanilla(p);
        setLitros(Object.fromEntries(p.vacas.map((v) => [v.animal, v.litros == null ? "" : String(Number(v.litros)).replace(".", ",")])));
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Sin señal: no se pudo traer la lista de vacas."));
  }, [fecha, ordene]);

  const cargadas = Object.entries(litros).filter(([, v]) => v.trim() !== "");
  const total = cargadas.reduce((s, [, v]) => s + (valor(v) || 0), 0);
  const lote = planilla?.lote;
  const diaAnterior = fecha < hoyISO();

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setExito(null);
    if (!cargadas.length || total <= 0) {
      setError("Cargá los litros de al menos una vaca.");
      campos.current[0]?.focus();
      return;
    }
    setOcupado(true);
    try {
      const r = await enviarPlanilla({
        clave: `${fecha}-${ordene}`, fecha, ordene, destino,
        items: cargadas.map(([animal, v]) => ({ animal, litros: String(valor(v)) })),
        motivo,
      });
      const sesion = ordene === "manana" ? "mañana" : "tarde";
      if (r.enCola) {
        setExito({ texto: `Sin señal: la planilla de la ${sesion} (${fmtLitros(total)}) quedó guardada en el teléfono.` });
      } else {
        const res = r.respuesta!;
        const cambio = res.total_anterior && Number(res.total_anterior) !== Number(res.total)
          ? ` El lote pasó de ${fmtLitros(res.total_anterior)} a ${fmtLitros(res.total)}.` : "";
        setExito({ texto: `Listo: ${res.lote.codigo} con ${fmtLitros(res.total)} de ${cargadas.length} vacas.${cambio}`, id: res.lote.id });
        setPlanilla((p) => (p ? { ...p, lote: { id: res.lote.id, codigo: res.lote.codigo, litros: res.lote.litros, estado: res.lote.estado, con_detalle_por_vaca: true } } : p));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar.");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <form onSubmit={guardar} className="space-y-5 rounded-2xl border border-stone-200 bg-white p-5 sm:p-6" aria-label="Ordeñe por vaca">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="fecha" className="mb-1 block text-sm font-medium">Fecha</label>
          <input id="fecha" type="date" max={hoyISO()} required value={fecha} onChange={(e) => setFecha(e.target.value)} className={estiloInput} />
        </div>
        <fieldset>
          <legend className="mb-1 block text-sm font-medium">Ordeñe</legend>
          <div className="grid grid-cols-2 gap-1 rounded-lg bg-stone-100 p-1">
            {ORDENES.map((o) => (
              <button key={o.valor} type="button" aria-pressed={ordene === o.valor} onClick={() => setOrdene(o.valor)}
                className={`rounded-md py-2 text-sm font-medium ${ordene === o.valor ? "bg-white shadow-sm" : "text-stone-600"}`}>
                {o.nombre}
              </button>
            ))}
          </div>
        </fieldset>
      </div>

      {lote && (
        <Aviso tipo="alerta">
          Esta sesión ya tiene el lote <Link href={`/leche/lotes/${lote.id}`} className="font-medium underline">{lote.codigo}</Link> con {fmtLitros(lote.litros)}
          {lote.con_detalle_por_vaca ? ". Al guardar, la planilla reemplaza la anterior." : ", cargado como total. Al guardar, el total pasa a ser la suma de las vacas."}
        </Aviso>
      )}

      {planilla && planilla.vacas.length === 0 && (
        <Aviso tipo="alerta">No hay vacas en ordeñe. <Link href="/rodeo" className="font-medium underline">Cargalas en el rodeo</Link>.</Aviso>
      )}

      {planilla && planilla.vacas.length > 0 && (
        <ul className="divide-y divide-stone-100 rounded-xl border border-stone-200" aria-label="Litros por vaca">
          {planilla.vacas.map((v, i) => (
            <li key={v.animal} className="flex items-center gap-3 px-3 py-2">
              <label htmlFor={`v-${v.animal}`} className="min-w-0 flex-1">
                <span className="font-semibold">{v.caravana}</span>
                {v.nombre && <span className="ml-2 text-sm text-stone-500">{v.nombre}</span>}
              </label>
              <div className="relative w-28">
                <input
                  id={`v-${v.animal}`}
                  ref={(el) => { campos.current[i] = el; }}
                  inputMode="decimal"
                  autoComplete="off"
                  enterKeyHint={i === planilla.vacas.length - 1 ? "done" : "next"}
                  placeholder="—"
                  value={litros[v.animal] ?? ""}
                  onChange={(e) => setLitros((l) => ({ ...l, [v.animal]: limpiar(e.target.value) }))}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && i < planilla.vacas.length - 1) {
                      e.preventDefault();
                      campos.current[i + 1]?.focus();
                    }
                  }}
                  className={`${estiloInput} py-2 pr-8 text-right text-lg font-semibold tabular-nums`}
                />
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm text-stone-400">L</span>
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-baseline justify-between rounded-xl bg-stone-50 px-4 py-3">
        <span className="text-sm text-stone-600">{cargadas.length} vacas cargadas</span>
        <span className="text-2xl font-semibold tabular-nums" aria-live="polite">Total {fmtLitros(total)}</span>
      </div>

      {!lote && (
        <fieldset>
          <legend className="mb-1 block text-sm font-medium">Destino del lote</legend>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {DESTINOS.map((d) => (
              <button key={d.valor} type="button" aria-pressed={destino === d.valor} onClick={() => setDestino(d.valor)}
                className={`rounded-lg border px-3 py-3 text-sm font-medium ${destino === d.valor ? "border-campo-600 bg-campo-50 text-campo-900 ring-1 ring-campo-600" : "border-stone-300 text-stone-700"}`}>
                {d.corto}
              </button>
            ))}
          </div>
        </fieldset>
      )}

      {lote && diaAnterior && (
        <div>
          <label htmlFor="motivo" className="mb-1 block text-sm font-medium">Motivo de la corrección</label>
          <input id="motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} className={estiloInput} placeholder="Solo el Administrador corrige días anteriores" />
        </div>
      )}

      {error && <Aviso tipo="error">{error}</Aviso>}
      {exito && (
        <p role="status" className="flex items-start gap-2 rounded-lg bg-campo-50 px-3 py-2 text-sm text-campo-900">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>{exito.texto} {exito.id && <Link href={`/leche/lotes/${exito.id}`} className="font-medium underline">Ver lote</Link>}</span>
        </p>
      )}

      <button type="submit" disabled={ocupado} className={`${botonPrimario} w-full py-4 text-lg`}>
        {ocupado ? "Guardando…" : "Guardar planilla"}
      </button>
    </form>
  );
}
