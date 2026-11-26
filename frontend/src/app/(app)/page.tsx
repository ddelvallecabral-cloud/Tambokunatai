"use client";

import { useAuth } from "@/lib/auth";
import { Tablero } from "@/components/Tablero";

export default function InicioPage() {
  const { usuario, puede } = useAuth();
  if (!usuario) return null;
  if (puede("reportes.operativos") || puede("reportes.financieros")) {
    return (
      <div className="mx-auto max-w-5xl">
        <h1 className="mb-5 text-2xl font-semibold">Hola, {usuario.nombre.split(" ")[0]}</h1>
        <Tablero />
      </div>
    );
  }
  const proximos = usuario.modulos.filter((m) => !m.disponible);

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-semibold">Hola, {usuario.nombre.split(" ")[0]}</h1>
      <p className="mt-1 text-stone-500">
        Ingresaste como {usuario.roles.map((r) => r.nombre).join(", ")}.
      </p>

      <section className="mt-8 rounded-2xl border border-stone-200 bg-white p-6">
        <h2 className="font-semibold">Tus módulos</h2>
        <p className="mt-1 text-sm text-stone-500">
          Estos son los módulos a los que tenés acceso. Se van habilitando en cada fase.
        </p>
        <ul className="mt-4 grid gap-2 sm:grid-cols-2">
          {proximos.map((m) => (
            <li key={m.codigo} className="flex items-center justify-between rounded-lg bg-stone-50 px-4 py-3 text-sm">
              <span>{m.nombre}</span>
              <span className="text-xs text-stone-400">Fase {m.fase}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
