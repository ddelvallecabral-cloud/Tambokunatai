"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { CheckCircle2, ChevronDown } from "lucide-react";
import { ApiError } from "@/lib/api";
import { DESTINOS, hoyISO, litros as fmtLitros, ORDENES, registrarLote, type Ordene, type TipoDestino } from "@/lib/leche";

const ordenePorHora = (): Ordene => (new Date().getHours() < 13 ? "manana" : "tarde");

export default function RegistrarLeche() {
  const [fecha, setFecha] = useState(hoyISO);
  const [ordene, setOrdene] = useState<Ordene>(ordenePorHora);
  const [litros, setLitros] = useState("");
  const [destino, setDestino] = useState<TipoDestino | "pendiente">("pendiente");
  const [verCalidad, setVerCalidad] = useState(false);
  const [grasa, setGrasa] = useState("");
  const [proteina, setProteina] = useState("");
  const [temperatura, setTemperatura] = useState("");
  const [observaciones, setObservaciones] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");
  const [exito, setExito] = useState<{ texto: string; id?: string } | null>(null);
  const campoLitros = useRef<HTMLInputElement>(null);

  const numero = (v: string) => (v.trim() === "" ? null : v.replace(",", "."));

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setExito(null);
    const valor = Number(litros.replace(",", "."));
    if (!valor || valor <= 0) {
      setError("Ingresá los litros.");
      campoLitros.current?.focus();
      return;
    }
    setEnviando(true);
    try {
      const r = await registrarLote({
        id: crypto.randomUUID(),
        fecha,
        ordene,
        litros: String(valor),
        destino,
        grasa_pct: numero(grasa),
        proteina_pct: numero(proteina),
        temperatura_c: numero(temperatura),
        observaciones,
      });
      const sesion = ORDENES.find((o) => o.valor === ordene)?.nombre.toLowerCase();
      setExito(
        r.enCola
          ? { texto: `Sin señal: ${fmtLitros(valor)} del ordeñe de la ${sesion} quedaron guardados en el teléfono.` }
          : { texto: `Listo: ${r.lote!.codigo} con ${fmtLitros(valor)}.`, id: r.lote!.id },
      );
      setLitros("");
      setGrasa("");
      setProteina("");
      setTemperatura("");
      setObservaciones("");
      if (ordene === "manana") setOrdene("tarde");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar.");
    } finally {
      setEnviando(false);
    }
  }

  const estiloInput =
    "w-full rounded-lg border border-stone-300 bg-white px-3 py-2.5 text-base outline-none focus:border-campo-500 focus:ring-2 focus:ring-campo-100";

  return (
    <form onSubmit={guardar} className="space-y-5 rounded-2xl border border-stone-200 bg-white p-5 sm:p-6" aria-label="Registro diario de leche">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="fecha" className="mb-1 block text-sm font-medium">Fecha</label>
          <input id="fecha" type="date" max={hoyISO()} required value={fecha} onChange={(e) => setFecha(e.target.value)} className={estiloInput} />
        </div>
        <fieldset>
          <legend className="mb-1 block text-sm font-medium">Ordeñe</legend>
          <div className="grid grid-cols-2 gap-1 rounded-lg bg-stone-100 p-1">
            {ORDENES.map((o) => (
              <button
                key={o.valor}
                type="button"
                aria-pressed={ordene === o.valor}
                onClick={() => setOrdene(o.valor)}
                className={`rounded-md py-2 text-sm font-medium ${ordene === o.valor ? "bg-white shadow-sm" : "text-stone-600"}`}
              >
                {o.nombre}
              </button>
            ))}
          </div>
        </fieldset>
      </div>

      <div>
        <label htmlFor="litros" className="mb-1 block text-sm font-medium">Litros</label>
        <div className="relative">
          <input
            id="litros"
            ref={campoLitros}
            inputMode="decimal"
            autoComplete="off"
            placeholder="0"
            value={litros}
            onChange={(e) => setLitros(e.target.value.replace(/[^0-9.,]/g, ""))}
            className={`${estiloInput} py-4 pr-12 text-3xl font-semibold tabular-nums`}
            autoFocus
          />
          <span className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-lg text-stone-400">L</span>
        </div>
      </div>

      <fieldset>
        <legend className="mb-1 block text-sm font-medium">Destino</legend>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {DESTINOS.map((d) => (
            <button
              key={d.valor}
              type="button"
              aria-pressed={destino === d.valor}
              onClick={() => setDestino(d.valor)}
              className={`rounded-lg border px-3 py-3 text-sm font-medium ${
                destino === d.valor ? "border-campo-600 bg-campo-50 text-campo-900 ring-1 ring-campo-600" : "border-stone-300 text-stone-700"
              }`}
            >
              {d.corto}
            </button>
          ))}
        </div>
        <p className="mt-1.5 text-xs text-stone-500">
          {destino === "pendiente"
            ? "Podés repartir los litros entre queso, venta y descarte después, desde el lote."
            : "Todos los litros van a este destino. Si después hay que repartir, se hace desde el lote."}
        </p>
      </fieldset>

      <div>
        <button type="button" onClick={() => setVerCalidad((v) => !v)} aria-expanded={verCalidad} className="flex items-center gap-1 text-sm font-medium text-campo-700">
          <ChevronDown className={`h-4 w-4 transition-transform ${verCalidad ? "rotate-180" : ""}`} aria-hidden />
          Calidad y observaciones (opcional)
        </button>
        {verCalidad && (
          <div className="mt-3 space-y-3">
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label htmlFor="grasa" className="mb-1 block text-xs font-medium">Grasa %</label>
                <input id="grasa" inputMode="decimal" value={grasa} onChange={(e) => setGrasa(e.target.value)} className={estiloInput} />
              </div>
              <div>
                <label htmlFor="proteina" className="mb-1 block text-xs font-medium">Proteína %</label>
                <input id="proteina" inputMode="decimal" value={proteina} onChange={(e) => setProteina(e.target.value)} className={estiloInput} />
              </div>
              <div>
                <label htmlFor="temperatura" className="mb-1 block text-xs font-medium">Temp. °C</label>
                <input id="temperatura" inputMode="decimal" value={temperatura} onChange={(e) => setTemperatura(e.target.value)} className={estiloInput} />
              </div>
            </div>
            <div>
              <label htmlFor="observaciones" className="mb-1 block text-xs font-medium">Observaciones</label>
              <textarea id="observaciones" rows={2} value={observaciones} onChange={(e) => setObservaciones(e.target.value)} className={estiloInput} />
            </div>
          </div>
        )}
      </div>

      {error && <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
      {exito && (
        <p role="status" className="flex items-start gap-2 rounded-lg bg-campo-50 px-3 py-2 text-sm text-campo-900">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>
            {exito.texto}{" "}
            {exito.id && <Link href={`/leche/lotes/${exito.id}`} className="font-medium underline">Ver lote</Link>}
          </span>
        </p>
      )}

      <button type="submit" disabled={enviando} className="w-full rounded-xl bg-campo-700 py-4 text-lg font-semibold text-white hover:bg-campo-900 disabled:opacity-60">
        {enviando ? "Guardando…" : "Guardar"}
      </button>
    </form>
  );
}
