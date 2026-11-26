"use client";

import { Pestanas } from "@/components/Pestanas";
import { useAuth } from "@/lib/auth";

export default function ComprasLayout({ children }: { children: React.ReactNode }) {
  const { puede } = useAuth();
  const pestanas = [{ ruta: "/compras", nombre: "Compras" }];
  if (puede("compras.compra.registrar")) pestanas.push({ ruta: "/compras/registrar", nombre: "Registrar compra" });
  pestanas.push({ ruta: "/compras/proveedores", nombre: "Proveedores" });
  if (puede("compras.pago.registrar")) pestanas.push({ ruta: "/compras/cuentas", nombre: "Cuentas por pagar" });
  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-5 text-2xl font-semibold">Compras</h1>
      <Pestanas etiqueta="Secciones de compras" pestanas={pestanas} />
      {children}
    </div>
  );
}
