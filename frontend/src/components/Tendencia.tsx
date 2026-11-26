import { ArrowDownRight, ArrowRight, ArrowUpRight } from "lucide-react";
import type { Animal } from "@/lib/rodeo";

export function Tendencia({ valor }: { valor: Animal["tendencia"] }) {
  if (valor === "sube") return <span className="inline-flex items-center gap-1 text-campo-700"><ArrowUpRight className="h-4 w-4" aria-hidden />Sube</span>;
  if (valor === "baja") return <span className="inline-flex items-center gap-1 font-medium text-red-700"><ArrowDownRight className="h-4 w-4" aria-hidden />Baja</span>;
  if (valor === "estable") return <span className="inline-flex items-center gap-1 text-stone-500"><ArrowRight className="h-4 w-4" aria-hidden />Estable</span>;
  return <span className="text-stone-400">Sin datos</span>;
}
