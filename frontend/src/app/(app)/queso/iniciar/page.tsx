"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { cantidad } from "@/lib/formato";
import { fechaCorta, hoyISO, litros } from "@/lib/leche";
import type { Insumo } from "@/lib/inventario";
import type { LecheDisponible, LoteQueso } from "@/lib/queso";
import { Pasos } from "@/components/Pasos";
import { Aviso, botonPrimario, estiloInput } from "@/components/ui";

const limpiar = (v: string) => v.replace(/[^0-9.,]/g, "");
const num = (v: string) => Number((v || "0").replace(",", "."));

export default function IniciarLote() {
  const router = useRouter();
  const [fecha, setFecha] = useState(hoyISO);
  const [leche, setLeche] = useState<LecheDisponible[] | null>(null);
  const [insumos, setInsumos] = useState<Insumo[]>([]);
  const [usar, setUsar] = useState<Record<string, string>>({});
  const [cantidades, setCantidades] = useState<Record<string, string>>({});
  const [observaciones, setObservaciones] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [id] = useState(() => crypto.randomUUID());

  useEffect(() => {
    api<LecheDisponible[]>(`/queso/leche-disponible?fecha=${fecha}`).then((l) => {
      setLeche(l);
      setUsar({});
    });
  }, [fecha]);
  useEffect(() => {
    api<{ results: Insumo[] }>("/insumos?activo=1&page_size=200").then((p) => setInsumos(p.results));
  }, []);

  const totalLitros = useMemo(() => Object.values(usar).reduce((s, v) => s + num(v), 0), [usar]);

  async function iniciar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const origenes = Object.entries(usar).filter(([, v]) => num(v) > 0).map(([lote_leche, v]) => ({ lote_leche, litros: String(num(v)) }));
    if (!origenes.length) {
      setError("Elegí de qué lotes de leche sale este queso.");
      return;
    }
    const declarados = Object.entries(cantidades).filter(([, v]) => num(v) > 0).map(([insumo, v]) => ({ insumo, cantidad: String(num(v)) }));
    setOcupado(true);
    try {
      const lote = await api<LoteQueso>("/lotes-queso", {
        method: "POST",
        body: JSON.stringify({ id, fecha, origenes, insumos: declarados, observaciones }),
      });
      router.push(`/queso/${lote.id}?iniciado=1`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo iniciar el lote. Revisá la señal y probá de nuevo.");
      setOcupado(false);
    }
  }

  return (
    <form onSubmit={iniciar} className="space-y-5" aria-label="Iniciar lote de queso">
      <Pasos actual={1} />

      <section className="space-y-3 rounded-2xl border border-stone-200 bg-white p-5" aria-labelledby="t-leche">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 id="t-leche" className="font-semibold">Leche de origen</h2>
          <div className="w-44">
            <label htmlFor="fecha" className="mb-1 block text-xs font-medium">Fecha de elaboración</label>
            <input id="fecha" type="date" max={hoyISO()} value={fecha} onChange={(e) => setFecha(e.target.value)} className={estiloInput} />
          </div>
        </div>
        {!leche ? (
          <p className="text-sm text-stone-500">Cargando…</p>
        ) : leche.length === 0 ? (
          <Aviso tipo="alerta">No hay leche disponible de los últimos 7 días. Cargá el ordeñe o destiná litros a queso desde Leche.</Aviso>
        ) : (
          <ul className="divide-y divide-stone-100 rounded-xl border border-stone-200">
            {leche.map((l) => {
              const elegido = l.id in usar;
              return (
                <li key={l.id} className="flex flex-wrap items-center gap-3 px-3 py-2.5">
                  <label className="flex min-w-0 flex-1 items-center gap-3">
                    <input
                      type="checkbox"
                      checked={elegido}
                      onChange={(e) =>
                        setUsar((u) => {
                          const n = { ...u };
                          if (e.target.checked) n[l.id] = String(Number(l.total)).replace(".", ",");
                          else delete n[l.id];
                          return n;
                        })
                      }
                      className="h-5 w-5"
                    />
                    <span>
                      <span className="font-medium">{l.codigo}</span>
                      <span className="ml-2 text-sm text-stone-500">{fechaCorta(l.fecha)}, {l.ordene === "manana" ? "mañana" : "tarde"}</span>
                      <span className="block text-xs text-stone-500">
                        {litros(l.total)} disponibles
                        {Number(l.destinado_a_queso) > 0 && Number(l.sin_destino) > 0 && ` (${litros(l.destinado_a_queso)} ya para queso, ${litros(l.sin_destino)} sin destino)`}
                      </span>
                    </span>
                  </label>
                  {elegido && (
                    <div className="relative w-28">
                      <input
                        aria-label={`Litros de ${l.codigo}`}
                        inputMode="decimal"
                        value={usar[l.id]}
                        onChange={(e) => setUsar((u) => ({ ...u, [l.id]: limpiar(e.target.value) }))}
                        className={`${estiloInput} py-2 pr-7 text-right font-semibold tabular-nums ${num(usar[l.id]) > Number(l.total) ? "border-red-400" : ""}`}
                      />
                      <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm text-stone-400">L</span>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        <p className="text-right text-lg font-semibold tabular-nums" aria-live="polite">Total {litros(totalLitros)}</p>
      </section>

      <section className="space-y-3 rounded-2xl border border-stone-200 bg-white p-5" aria-labelledby="t-insumos">
        <div>
          <h2 id="t-insumos" className="font-semibold">Insumos que vas a usar</h2>
          <p className="text-sm text-stone-500">Se reservan ahora. Al cerrar el lote cargás lo que realmente se usó.</p>
        </div>
        <ul className="divide-y divide-stone-100 rounded-xl border border-stone-200">
          {insumos.map((i) => (
            <li key={i.id} className="flex items-center gap-3 px-3 py-2">
              <label htmlFor={`i-${i.id}`} className="min-w-0 flex-1">
                <span className="font-medium">{i.nombre}</span>
                <span className={`block text-xs ${i.bajo_minimo ? "text-red-700" : "text-stone-500"}`}>
                  {cantidad(i.disponible, i.unidad)} disponibles{i.bajo_minimo && " · bajo el mínimo"}
                </span>
              </label>
              <div className="relative w-32">
                <input
                  id={`i-${i.id}`}
                  inputMode="decimal"
                  placeholder="0"
                  value={cantidades[i.id] ?? ""}
                  onChange={(e) => setCantidades((c) => ({ ...c, [i.id]: limpiar(e.target.value) }))}
                  className={`${estiloInput} py-2 pr-12 text-right tabular-nums ${num(cantidades[i.id] ?? "") > Number(i.disponible) ? "border-red-400" : ""}`}
                />
                <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-stone-400">{i.unidad === "unidad" ? "u." : i.unidad}</span>
              </div>
            </li>
          ))}
        </ul>
        <div>
          <label htmlFor="obs" className="mb-1 block text-xs font-medium">Observaciones</label>
          <textarea id="obs" rows={2} value={observaciones} onChange={(e) => setObservaciones(e.target.value)} className={estiloInput} />
        </div>
      </section>

      {error && <Aviso tipo="error">{error}</Aviso>}
      <button type="submit" disabled={ocupado} className={`${botonPrimario} w-full py-4 text-lg`}>
        {ocupado ? "Iniciando…" : `Iniciar lote con ${litros(totalLitros)}`}
      </button>
    </form>
  );
}
