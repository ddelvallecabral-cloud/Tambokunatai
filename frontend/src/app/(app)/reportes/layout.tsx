"use client";

import { Pestanas } from "@/components/Pestanas";
import { useAuth } from "@/lib/auth";

export default function ReportesLayout({ children }: { children: React.ReactNode }) {
  const { puede } = useAuth();
  const pestanas: { ruta: string; nombre: string }[] = [];
  if (puede("reportes.financieros")) {
    pestanas.push(
      { ruta: "/reportes/resultados", nombre: "Resultados" },
      { ruta: "/reportes/flujo", nombre: "Flujo de caja" },
      { ruta: "/reportes/lotes", nombre: "Por lote de queso" },
      { ruta: "/reportes/productos", nombre: "Por producto" },
    );
  }
  if (puede("auditoria.ver")) pestanas.push({ ruta: "/reportes/aprobaciones", nombre: "Aprobaciones" });
  if (puede("reportes.operativos") || puede("reportes.financieros")) pestanas.push({ ruta: "/reportes/alertas", nombre: "Alertas" });
  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="mb-5 text-2xl font-semibold">Reportes</h1>
      {pestanas.length ? <><Pestanas etiqueta="Reportes" pestanas={pestanas} />{children}</> : (
        <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">Tu rol todavía no tiene reportes. Los de ventas propias llegan en una próxima fase.</p>
      )}
    </div>
  );
}
