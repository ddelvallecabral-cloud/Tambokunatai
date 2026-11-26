"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { LogOut, Menu, Milk, X } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { useAuth } from "@/lib/auth";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { usuario, cargando, salir } = useAuth();
  const router = useRouter();
  const [menuAbierto, setMenuAbierto] = useState(false);

  useEffect(() => {
    if (!cargando && !usuario) router.replace("/login");
  }, [cargando, usuario, router]);

  if (cargando || !usuario) {
    return <div className="flex min-h-screen items-center justify-center text-stone-500">Cargando…</div>;
  }

  async function cerrarSesion() {
    await salir();
    router.replace("/login");
  }

  const rol = usuario.roles.map((r) => r.nombre).join(", ");

  return (
    <div className="min-h-screen lg:flex">
      {/* Barra superior en celular */}
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-stone-200 bg-white px-4 py-3 lg:hidden">
        <button onClick={() => setMenuAbierto(true)} aria-label="Abrir menú" className="-ml-1 p-1">
          <Menu className="h-6 w-6" />
        </button>
        <span className="font-semibold">Tambo Kuñatai</span>
        <span className="w-6" />
      </header>

      {menuAbierto && (
        <div className="fixed inset-0 z-30 bg-black/30 lg:hidden" onClick={() => setMenuAbierto(false)} aria-hidden />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-stone-200 bg-white transition-transform lg:sticky lg:top-0 lg:h-screen lg:translate-x-0 ${
          menuAbierto ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-stone-200 px-4 py-4">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-campo-700 p-1.5 text-white">
              <Milk className="h-5 w-5" aria-hidden />
            </div>
            <span className="font-semibold">Tambo Kuñatai</span>
          </div>
          <button onClick={() => setMenuAbierto(false)} aria-label="Cerrar menú" className="lg:hidden">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <Sidebar modulos={usuario.modulos} onNavegar={() => setMenuAbierto(false)} />
        </div>

        <div className="border-t border-stone-200 p-3">
          <div className="mb-2 px-3">
            <p className="truncate text-sm font-medium" data-testid="usuario-nombre">{usuario.nombre}</p>
            <p className="truncate text-xs text-stone-500" data-testid="usuario-rol">{rol}</p>
          </div>
          <button
            onClick={cerrarSesion}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-stone-700 hover:bg-stone-100"
          >
            <LogOut className="h-4 w-4" aria-hidden />
            Cerrar sesión
          </button>
        </div>
      </aside>

      <main className="flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
    </div>
  );
}
