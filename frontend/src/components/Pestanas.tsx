"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Pestañas de sección. La primera ruta es la raíz del módulo y solo se marca si coincide exacta. */
export function Pestanas({ pestanas, etiqueta }: { pestanas: { ruta: string; nombre: string }[]; etiqueta: string }) {
  const ruta = usePathname();
  const raiz = pestanas[0].ruta;
  const activa = (p: string) =>
    p === raiz
      ? ruta === raiz || (ruta.startsWith(`${raiz}/`) && !pestanas.some((x) => x.ruta !== raiz && ruta.startsWith(x.ruta)))
      : ruta.startsWith(p);
  return (
    <nav className="mb-6 flex gap-1 overflow-x-auto rounded-xl bg-stone-200/60 p-1" aria-label={etiqueta}>
      {pestanas.map((p) => (
        <Link
          key={p.ruta}
          href={p.ruta}
          aria-current={activa(p.ruta) ? "page" : undefined}
          className={`flex-1 whitespace-nowrap rounded-lg px-3 py-2 text-center text-sm font-medium ${
            activa(p.ruta) ? "bg-white text-stone-900 shadow-sm" : "text-stone-600 hover:text-stone-900"
          }`}
        >
          {p.nombre}
        </Link>
      ))}
    </nav>
  );
}
