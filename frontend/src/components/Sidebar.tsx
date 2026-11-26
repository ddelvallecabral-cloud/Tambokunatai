"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Beef, BarChart3, CheckCheck, ClipboardList, Home, Milk, Package, Receipt,
  ShieldCheck, ShoppingCart, Users, Wallet, type LucideIcon,
} from "lucide-react";
import type { Modulo } from "@/lib/api";

const ICONOS: Record<string, LucideIcon> = {
  inicio: Home,
  rodeo: Beef,
  leche: Milk,
  queso: ClipboardList,
  inventario: Package,
  compras: ShoppingCart,
  ventas: Receipt,
  gastos: Wallet,
  aprobaciones: CheckCheck,
  reportes: BarChart3,
  auditoria: ShieldCheck,
  usuarios: Users,
};

export function Sidebar({ modulos, onNavegar }: { modulos: Modulo[]; onNavegar?: () => void }) {
  const ruta = usePathname();

  return (
    <nav aria-label="Módulos" className="flex flex-col gap-0.5 p-3">
      {modulos.map((m) => {
        const Icono = ICONOS[m.codigo] ?? Home;
        const activo = m.ruta === "/" ? ruta === "/" : ruta.startsWith(m.ruta);

        if (!m.disponible) {
          return (
            <span
              key={m.codigo}
              aria-disabled="true"
              title={`Disponible en la Fase ${m.fase}`}
              data-modulo={m.codigo}
              className="flex cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2 text-sm text-stone-400"
            >
              <Icono className="h-4 w-4 shrink-0" aria-hidden />
              <span className="flex-1">{m.nombre}</span>
              <span className="rounded bg-stone-100 px-1.5 py-0.5 text-[10px] font-medium text-stone-400">
                Fase {m.fase}
              </span>
            </span>
          );
        }

        return (
          <Link
            key={m.codigo}
            href={m.ruta}
            onClick={onNavegar}
            data-modulo={m.codigo}
            aria-current={activo ? "page" : undefined}
            className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium ${
              activo ? "bg-campo-100 text-campo-900" : "text-stone-700 hover:bg-stone-100"
            }`}
          >
            <Icono className="h-4 w-4 shrink-0" aria-hidden />
            {m.nombre}
          </Link>
        );
      })}
    </nav>
  );
}
