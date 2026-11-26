"use client";

import { Pestanas } from "@/components/Pestanas";
import { useAuth } from "@/lib/auth";

export default function GastosLayout({ children }: { children: React.ReactNode }) {
  const { puede } = useAuth();
  const pestanas = [{ ruta: "/gastos", nombre: "Gastos" }];
  if (puede("gastos.gasto.registrar")) pestanas.push({ ruta: "/gastos/cargar", nombre: "Cargar gasto" });
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-5 text-2xl font-semibold">Gastos</h1>
      <Pestanas etiqueta="Secciones de gastos" pestanas={pestanas} />
      {children}
    </div>
  );
}
