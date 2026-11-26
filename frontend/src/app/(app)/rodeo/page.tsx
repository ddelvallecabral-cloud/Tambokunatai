"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { Tendencia } from "@/components/Tendencia";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { decimal1 } from "@/lib/formato";
import { NOMBRE_SITUACION, SITUACIONES, type Animal, type Situacion } from "@/lib/rodeo";
import { Aviso, botonPrimario, estiloInput, Insignia } from "@/components/ui";

export default function Vacas() {
  const { puede } = useAuth();
  const [animales, setAnimales] = useState<Animal[] | null>(null);
  const [bajas, setBajas] = useState(false);
  const [nueva, setNueva] = useState(false);

  const cargar = useCallback(
    () => api<{ results: Animal[] }>(`/animales?page_size=500${bajas ? "&incluir_bajas=1" : ""}`).then((p) => setAnimales(p.results)),
    [bajas],
  );
  useEffect(() => {
    cargar();
  }, [cargar]);

  const enOrdene = animales?.filter((a) => a.situacion === "en_ordene") ?? [];
  const bajando = enOrdene.filter((a) => a.tendencia === "baja");
  // Las que bajan primero: son las que hay que mirar.
  const orden = { baja: 0, estable: 1, sube: 2 } as Record<string, number>;
  const lista = [...(animales ?? [])].sort(
    (a, b) => (orden[a.tendencia ?? ""] ?? 3) - (orden[b.tendencia ?? ""] ?? 3) || a.caravana.localeCompare(b.caravana, "es", { numeric: true }),
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-stone-600">
          {animales ? `${enOrdene.length} vacas en ordeñe` : "Cargando…"}
          {bajando.length > 0 && <> · <span className="font-medium text-red-700">{bajando.length} bajando su producción</span></>}
        </p>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-stone-600">
            <input type="checkbox" checked={bajas} onChange={(e) => setBajas(e.target.checked)} /> Ver vendidas y muertas
          </label>
          {puede("rodeo.animal.gestionar") && (
            <button onClick={() => setNueva((v) => !v)} className="inline-flex items-center gap-1 rounded-lg bg-campo-700 px-3 py-2 text-sm font-medium text-white">
              <Plus className="h-4 w-4" aria-hidden /> Nueva vaca
            </button>
          )}
        </div>
      </div>

      {nueva && <NuevaVaca alGuardar={() => { setNueva(false); cargar(); }} />}

      <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white">
        <table className="w-full text-sm">
          <thead className="bg-stone-50 text-left text-xs uppercase tracking-wide text-stone-500">
            <tr>
              <th className="px-4 py-2.5">Caravana</th>
              <th className="px-4 py-2.5">Situación</th>
              <th className="px-4 py-2.5 text-right">L/día (7 días)</th>
              <th className="hidden px-4 py-2.5 text-right sm:table-cell">Semana anterior</th>
              <th className="px-4 py-2.5">Tendencia</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100">
            {lista.map((a) => (
              <tr key={a.id} className="hover:bg-stone-50">
                <td className="px-4 py-3">
                  <Link href={`/rodeo/${a.id}`} className="font-medium text-campo-800 hover:underline">{a.caravana}</Link>
                  {a.nombre && <span className="ml-2 text-stone-500">{a.nombre}</span>}
                </td>
                <td className="px-4 py-3">
                  <Insignia color={a.situacion === "en_ordene" ? "verde" : a.situacion === "seca" ? "ambar" : "gris"}>{NOMBRE_SITUACION[a.situacion]}</Insignia>
                </td>
                <td className="px-4 py-3 text-right tabular-nums">{a.promedio_7d ? `${decimal1(a.promedio_7d)} L` : "—"}</td>
                <td className="hidden px-4 py-3 text-right tabular-nums text-stone-500 sm:table-cell">{a.promedio_7d_anterior ? `${decimal1(a.promedio_7d_anterior)} L` : "—"}</td>
                <td className="px-4 py-3"><Tendencia valor={a.tendencia} /></td>
              </tr>
            ))}
            {animales?.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-stone-500">Todavía no hay animales cargados.</td></tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-stone-500">La tendencia compara el promedio diario de los últimos 7 días con el de los 7 anteriores (±5 %).</p>
    </div>
  );
}

function NuevaVaca({ alGuardar }: { alGuardar: () => void }) {
  const [caravana, setCaravana] = useState("");
  const [nombre, setNombre] = useState("");
  const [raza, setRaza] = useState("");
  const [situacion, setSituacion] = useState<Situacion>("en_ordene");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setOcupado(true);
    setError("");
    try {
      await api("/animales", { method: "POST", body: JSON.stringify({ caravana, nombre, raza, situacion }) });
      alGuardar();
    } catch (err) {
      const datos = err instanceof ApiError ? (err.datos as Record<string, string[]>) : null;
      setError(datos?.caravana ? "Ya hay un animal con esa caravana." : err instanceof ApiError ? err.message : "No se pudo guardar.");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <form onSubmit={guardar} className="grid gap-3 rounded-2xl border border-stone-200 bg-white p-4 sm:grid-cols-5" aria-label="Nueva vaca">
      <div>
        <label htmlFor="caravana" className="mb-1 block text-xs font-medium">Caravana</label>
        <input id="caravana" required value={caravana} onChange={(e) => setCaravana(e.target.value)} className={estiloInput} />
      </div>
      <div>
        <label htmlFor="nombre" className="mb-1 block text-xs font-medium">Nombre</label>
        <input id="nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} className={estiloInput} />
      </div>
      <div>
        <label htmlFor="raza" className="mb-1 block text-xs font-medium">Raza</label>
        <input id="raza" value={raza} onChange={(e) => setRaza(e.target.value)} className={estiloInput} />
      </div>
      <div>
        <label htmlFor="situacion" className="mb-1 block text-xs font-medium">Situación</label>
        <select id="situacion" value={situacion} onChange={(e) => setSituacion(e.target.value as Situacion)} className={estiloInput}>
          {SITUACIONES.slice(0, 3).map((s) => <option key={s.valor} value={s.valor}>{s.nombre}</option>)}
        </select>
      </div>
      <div className="flex items-end">
        <button disabled={ocupado} className={`${botonPrimario} w-full py-2.5`}>Agregar</button>
      </div>
      {error && <div className="sm:col-span-5"><Aviso tipo="error">{error}</Aviso></div>}
    </form>
  );
}
