"use client";

import { Pestanas } from "@/components/Pestanas";
import { useAuth } from "@/lib/auth";

export default function QuesoLayout({ children }: { children: React.ReactNode }) {
  const { puede } = useAuth();
  const pestanas = [{ ruta: "/queso", nombre: "Lotes" }];
  if (puede("queso.lote.gestionar")) pestanas.push({ ruta: "/queso/iniciar", nombre: "Iniciar lote" });
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-5 text-2xl font-semibold">Queso</h1>
      <Pestanas etiqueta="Secciones de queso" pestanas={pestanas} />
      {children}
    </div>
  );
}
