"use client";

import { useParams } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function ModuloPendiente() {
  const { modulo } = useParams<{ modulo: string }>();
  const { usuario } = useAuth();
  const m = usuario?.modulos.find((x) => x.codigo === modulo);

  if (!m) {
    return <p className="text-stone-500">No tenés acceso a esta sección.</p>;
  }
  return (
    <div className="mx-auto max-w-xl rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center">
      <h1 className="text-xl font-semibold">{m.nombre}</h1>
      <p className="mt-2 text-stone-500">Este módulo se construye en la Fase {m.fase}.</p>
    </div>
  );
}
