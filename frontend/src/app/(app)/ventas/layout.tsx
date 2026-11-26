"use client";

import { Pestanas } from "@/components/Pestanas";
import { useAuth } from "@/lib/auth";

export default function VentasLayout({ children }: { children: React.ReactNode }) {
  const { puede } = useAuth();
  const pestanas = [{ ruta: "/ventas", nombre: "Ventas" }];
  if (puede("ventas.venta.registrar")) pestanas.push({ ruta: "/ventas/registrar", nombre: "Registrar venta" });
  pestanas.push({ ruta: "/ventas/clientes", nombre: "Clientes" });
  if (puede("reportes.financieros")) pestanas.push({ ruta: "/ventas/cuentas", nombre: "Cuentas por cobrar" });
  pestanas.push({ ruta: "/ventas/precios", nombre: "Precios" });
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-5 text-2xl font-semibold">Ventas y cobros</h1>
      <Pestanas etiqueta="Secciones de ventas" pestanas={pestanas} />
      {children}
    </div>
  );
}
