"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { decimal1 } from "@/lib/formato";
import { fechaCorta } from "@/lib/leche";
import { NOMBRE_SITUACION, SITUACIONES, type Animal, type Situacion } from "@/lib/rodeo";
import { Tendencia } from "@/components/Tendencia";
import { Aviso, botonPrimario, estiloInput, Tarjeta } from "@/components/ui";

type Dia = { fecha: string; manana: string | null; tarde: string | null; total: string | null };
type Produccion = { promedio_7d?: string | null; promedio_7d_anterior?: string | null; tendencia?: Animal["tendencia"]; serie: Dia[] };

export default function DetalleVaca() {
  const { id } = useParams<{ id: string }>();
  const { puede } = useAuth();
  const [animal, setAnimal] = useState<Animal | null>(null);
  const [prod, setProd] = useState<Produccion | null>(null);
  const [error, setError] = useState("");

  const cargar = useCallback(() => {
    api<Animal>(`/animales/${id}`).then(setAnimal).catch((e) => setError(e.message));
    api<Produccion>(`/animales/${id}/produccion?dias=30`).then(setProd);
  }, [id]);
  useEffect(() => {
    cargar();
  }, [cargar]);

  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!animal) return <p className="text-stone-500">Cargando…</p>;

  const maximo = Math.max(1, ...(prod?.serie ?? []).map((d) => Number(d.total ?? 0)));

  return (
    <div className="space-y-4">
      <Link href="/rodeo" className="inline-flex items-center gap-1 text-sm text-campo-700"><ArrowLeft className="h-4 w-4" aria-hidden /> Vacas</Link>
      <div>
        <h2 className="text-xl font-semibold">{animal.caravana} {animal.nombre && <span className="font-normal text-stone-500">· {animal.nombre}</span>}</h2>
        <p className="text-sm text-stone-500">{[animal.raza, NOMBRE_SITUACION[animal.situacion]].filter(Boolean).join(" · ")}</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Tarjeta titulo="Promedio últimos 7 días" valor={prod?.promedio_7d ? `${decimal1(prod.promedio_7d)} L/día` : "—"} />
        <Tarjeta titulo="7 días anteriores" valor={prod?.promedio_7d_anterior ? `${decimal1(prod.promedio_7d_anterior)} L/día` : "—"} />
        <Tarjeta titulo="Tendencia" valor={<Tendencia valor={prod?.tendencia ?? null} />} />
      </div>

      <section className="rounded-2xl border border-stone-200 bg-white p-5" aria-labelledby="t-serie">
        <h3 id="t-serie" className="mb-1 font-semibold">Litros por día, últimos 30 días</h3>
        <p className="mb-4 flex gap-4 text-xs text-stone-500">
          <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-campo-600" />Mañana</span>
          <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-sm bg-campo-300" />Tarde</span>
        </p>
        <div className="flex h-40 items-end gap-[3px]" role="img" aria-label="Producción diaria de los últimos 30 días">
          {prod?.serie.map((d) => (
            <div key={d.fecha} className="flex h-full flex-1 flex-col justify-end" title={`${fechaCorta(d.fecha)}: ${d.total ? `${decimal1(d.total)} L` : "sin registro"}`}>
              <div className="rounded-t-sm bg-campo-300" style={{ height: `${(Number(d.tarde ?? 0) / maximo) * 100}%` }} />
              <div className="bg-campo-600" style={{ height: `${(Number(d.manana ?? 0) / maximo) * 100}%` }} />
            </div>
          ))}
        </div>
        <div className="mt-1 flex justify-between text-xs text-stone-400">
          <span>{prod?.serie[0] && fechaCorta(prod.serie[0].fecha)}</span>
          <span>Hoy</span>
        </div>
      </section>

      {puede("rodeo.animal.gestionar") && <Edicion animal={animal} alGuardar={setAnimal} />}
    </div>
  );
}

function Edicion({ animal, alGuardar }: { animal: Animal; alGuardar: (a: Animal) => void }) {
  const [situacion, setSituacion] = useState<Situacion>(animal.situacion);
  const [nombre, setNombre] = useState(animal.nombre);
  const [raza, setRaza] = useState(animal.raza);
  const [observaciones, setObservaciones] = useState(animal.observaciones);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    try {
      const a = await api<Animal>(`/animales/${animal.id}`, { method: "PATCH", body: JSON.stringify({ situacion, nombre, raza, observaciones }) });
      alGuardar(a);
      setAviso({ tipo: "ok", texto: "Cambios guardados." });
    } catch (err) {
      setAviso({ tipo: "error", texto: err instanceof ApiError ? err.message : "No se pudo guardar." });
    }
  }

  return (
    <form onSubmit={guardar} className="grid gap-3 rounded-2xl border border-stone-200 bg-white p-5 sm:grid-cols-3" aria-label="Editar vaca">
      <h3 className="font-semibold sm:col-span-3">Datos</h3>
      <div>
        <label htmlFor="situacion" className="mb-1 block text-xs font-medium">Situación</label>
        <select id="situacion" value={situacion} onChange={(e) => setSituacion(e.target.value as Situacion)} className={estiloInput}>
          {SITUACIONES.map((s) => <option key={s.valor} value={s.valor}>{s.nombre}</option>)}
        </select>
      </div>
      <div>
        <label htmlFor="nombre" className="mb-1 block text-xs font-medium">Nombre</label>
        <input id="nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} className={estiloInput} />
      </div>
      <div>
        <label htmlFor="raza" className="mb-1 block text-xs font-medium">Raza</label>
        <input id="raza" value={raza} onChange={(e) => setRaza(e.target.value)} className={estiloInput} />
      </div>
      <div className="sm:col-span-3">
        <label htmlFor="obs" className="mb-1 block text-xs font-medium">Observaciones</label>
        <textarea id="obs" rows={2} value={observaciones} onChange={(e) => setObservaciones(e.target.value)} className={estiloInput} />
      </div>
      {aviso && <div className="sm:col-span-3"><Aviso tipo={aviso.tipo}>{aviso.texto}</Aviso></div>}
      <div><button className={`${botonPrimario} py-2.5`}>Guardar</button></div>
    </form>
  );
}
