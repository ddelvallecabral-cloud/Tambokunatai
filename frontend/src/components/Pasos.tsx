import { Check } from "lucide-react";

const PASOS = ["Iniciar lote", "Cerrar con kg obtenidos"];

/** Indicador del asistente de 2 pasos de elaboración de queso. `actual` 3 = los dos hechos. */
export function Pasos({ actual }: { actual: 1 | 2 | 3 }) {
  return (
    <ol className="flex items-center gap-3 text-sm" aria-label="Pasos del lote">
      {PASOS.map((p, i) => {
        const n = i + 1;
        const hecho = n < actual;
        const activo = n === actual;
        return (
          <li key={p} className="flex flex-1 items-center gap-2" aria-current={activo ? "step" : undefined}>
            <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
              hecho ? "bg-campo-700 text-white" : activo ? "border-2 border-campo-700 text-campo-800" : "border border-stone-300 text-stone-400"}`}>
              {hecho ? <Check className="h-4 w-4" aria-label="hecho" /> : n}
            </span>
            <span className={activo ? "font-semibold" : hecho ? "text-stone-700" : "text-stone-400"}>Paso {n}: {p}</span>
          </li>
        );
      })}
    </ol>
  );
}
