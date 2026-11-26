"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Download } from "lucide-react";
import { descargar } from "@/lib/api";
import { hoyISO } from "@/lib/leche";
import { Aviso, estiloInput } from "@/components/ui";

function corrida(dias: number) {
  const d = new Date();
  d.setDate(d.getDate() - dias);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function mesAnterior(): [string, string] {
  const d = new Date();
  const inicio = new Date(d.getFullYear(), d.getMonth() - 1, 1);
  const fin = new Date(d.getFullYear(), d.getMonth(), 0);
  const f = (x: Date) => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, "0")}-${String(x.getDate()).padStart(2, "0")}`;
  return [f(inicio), f(fin)];
}

/** Lee el período de la URL (?desde=&hasta=). Por defecto, el mes en curso (o el año, para el flujo mensual). */
export function usePeriodo(porDefecto: "mes" | "anio" = "mes"): { desde: string; hasta: string; consulta: string } {
  const params = useSearchParams();
  const hoy = hoyISO();
  const hasta = params.get("hasta") || hoy;
  const desde = params.get("desde") || (porDefecto === "mes" ? `${hasta.slice(0, 7)}-01` : `${hasta.slice(0, 4)}-01-01`);
  return { desde, hasta, consulta: `desde=${desde}&hasta=${hasta}` };
}

/** Elegir período + botones para bajar el reporte en PDF y Excel. */
export function Periodo({ reporte, porDefecto = "mes" }: { reporte?: string; porDefecto?: "mes" | "anio" }) {
  const router = useRouter();
  const ruta = usePathname();
  const params = useSearchParams();
  const { desde, hasta, consulta } = usePeriodo(porDefecto);
  const [error, setError] = useState("");
  const [bajando, setBajando] = useState("");

  const fijar = (d: string, h: string) => {
    const q = new URLSearchParams(params.toString());
    q.set("desde", d);
    q.set("hasta", h);
    router.replace(`${ruta}?${q}`);
  };
  async function bajar(formato: "pdf" | "xlsx") {
    setError(""); setBajando(formato);
    try {
      await descargar(`/reportes/${reporte}.${formato}?${consulta}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo generar el archivo.");
    } finally {
      setBajando("");
    }
  }
  const hoy = hoyISO();
  const atajos: [string, string, string][] = [
    ["Este mes", `${hoy.slice(0, 7)}-01`, hoy],
    ["Mes pasado", ...mesAnterior()],
    ["Últimos 30 días", corrida(29), hoy],
    ["Este año", `${hoy.slice(0, 4)}-01-01`, hoy],
  ];

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label htmlFor="p-desde" className="mb-1 block text-xs font-medium">Desde</label>
          <input id="p-desde" type="date" value={desde} max={hasta} onChange={(e) => e.target.value && fijar(e.target.value, hasta)} className={estiloInput} />
        </div>
        <div>
          <label htmlFor="p-hasta" className="mb-1 block text-xs font-medium">Hasta</label>
          <input id="p-hasta" type="date" value={hasta} min={desde} onChange={(e) => e.target.value && fijar(desde, e.target.value)} className={estiloInput} />
        </div>
        <div className="flex flex-wrap gap-1">
          {atajos.map(([nombre, d, h]) => (
            <button key={nombre} type="button" onClick={() => fijar(d, h)} aria-pressed={d === desde && h === hasta}
              className={`rounded-lg px-2.5 py-2 text-sm ${d === desde && h === hasta ? "bg-campo-100 font-medium text-campo-900" : "text-stone-600 hover:bg-stone-100"}`}>
              {nombre}
            </button>
          ))}
        </div>
        {reporte && (
          <div className="ml-auto flex gap-2">
            {(["pdf", "xlsx"] as const).map((f) => (
              <button key={f} type="button" disabled={!!bajando} onClick={() => bajar(f)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-medium hover:bg-stone-50 disabled:opacity-60">
                <Download className="h-4 w-4" aria-hidden /> {bajando === f ? "Generando…" : f === "pdf" ? "PDF" : "Excel"}
              </button>
            ))}
          </div>
        )}
      </div>
      {error && <Aviso tipo="error">{error}</Aviso>}
    </div>
  );
}
