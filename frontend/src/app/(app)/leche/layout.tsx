"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { AlertTriangle, CloudOff } from "lucide-react";
import { descartarRechazados, enviarCola, pendientesEnCola, rechazadosDeCola } from "@/lib/leche";

const PESTANAS = [
  { ruta: "/leche", nombre: "Panel" },
  { ruta: "/leche/registrar", nombre: "Registrar" },
  { ruta: "/leche/lotes", nombre: "Lotes" },
];

export default function LecheLayout({ children }: { children: React.ReactNode }) {
  const ruta = usePathname();
  const [enCola, setEnCola] = useState(0);
  const [rechazados, setRechazados] = useState<string[]>([]);

  useEffect(() => {
    const actualizar = () => {
      setEnCola(pendientesEnCola().length);
      setRechazados(rechazadosDeCola());
    };
    const intentar = async () => {
      if (pendientesEnCola().length) await enviarCola();
      actualizar();
    };
    actualizar();
    intentar();
    window.addEventListener("online", intentar);
    window.addEventListener("cola-leche", actualizar);
    const reloj = setInterval(intentar, 30_000);
    return () => {
      window.removeEventListener("online", intentar);
      window.removeEventListener("cola-leche", actualizar);
      clearInterval(reloj);
    };
  }, []);

  return (
    <div className="mx-auto max-w-4xl">
      <div className="mb-5 flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">Leche</h1>
      </div>
      <nav className="mb-6 flex gap-1 rounded-xl bg-stone-200/60 p-1" aria-label="Secciones de leche">
        {PESTANAS.map((p) => {
          const activa = p.ruta === "/leche" ? ruta === "/leche" : ruta.startsWith(p.ruta);
          return (
            <Link
              key={p.ruta}
              href={p.ruta}
              aria-current={activa ? "page" : undefined}
              className={`flex-1 rounded-lg px-3 py-2 text-center text-sm font-medium ${
                activa ? "bg-white text-stone-900 shadow-sm" : "text-stone-600 hover:text-stone-900"
              }`}
            >
              {p.nombre}
            </Link>
          );
        })}
      </nav>
      {enCola > 0 && (
        <div role="status" className="mb-4 flex items-center gap-2 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <CloudOff className="h-4 w-4 shrink-0" aria-hidden />
          {enCola === 1 ? "1 lote guardado" : `${enCola} lotes guardados`} en este teléfono. Se envían solos cuando vuelva la señal.
        </div>
      )}
      {rechazados.length > 0 && (
        <div role="alert" className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-800">
          <p className="flex items-center gap-2 font-medium">
            <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
            Al volver la señal, el sistema no aceptó {rechazados.length === 1 ? "un lote guardado" : `${rechazados.length} lotes guardados`} en el teléfono:
          </p>
          <ul className="mt-1 list-disc pl-6">
            {rechazados.map((r) => <li key={r}>{r}</li>)}
          </ul>
          <button onClick={descartarRechazados} className="mt-2 font-medium underline">Entendido</button>
        </div>
      )}
      {children}
    </div>
  );
}
