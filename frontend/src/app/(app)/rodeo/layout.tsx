"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CloudOff } from "lucide-react";
import { Pestanas } from "@/components/Pestanas";
import { descartarRechazosRodeo, enviarColaRodeo, planillasEnCola, rechazosRodeo } from "@/lib/rodeo";

export default function RodeoLayout({ children }: { children: React.ReactNode }) {
  const [enCola, setEnCola] = useState(0);
  const [rechazos, setRechazos] = useState<string[]>([]);

  useEffect(() => {
    const actualizar = () => {
      setEnCola(planillasEnCola().length);
      setRechazos(rechazosRodeo());
    };
    const intentar = async () => {
      if (planillasEnCola().length) await enviarColaRodeo();
      actualizar();
    };
    intentar();
    window.addEventListener("online", intentar);
    window.addEventListener("cola-rodeo", actualizar);
    const reloj = setInterval(intentar, 30_000);
    return () => {
      window.removeEventListener("online", intentar);
      window.removeEventListener("cola-rodeo", actualizar);
      clearInterval(reloj);
    };
  }, []);

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-5 text-2xl font-semibold">Rodeo</h1>
      <Pestanas etiqueta="Secciones del rodeo" pestanas={[{ ruta: "/rodeo", nombre: "Vacas" }, { ruta: "/rodeo/ordene", nombre: "Ordeñe por vaca" }]} />
      {enCola > 0 && (
        <div role="status" className="mb-4 flex items-center gap-2 rounded-lg bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <CloudOff className="h-4 w-4 shrink-0" aria-hidden />
          {enCola === 1 ? "1 planilla guardada" : `${enCola} planillas guardadas`} en este teléfono. Se envían solas cuando vuelva la señal.
        </div>
      )}
      {rechazos.length > 0 && (
        <div role="alert" className="mb-4 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-800">
          <p className="flex items-center gap-2 font-medium">
            <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
            Al volver la señal, el sistema no aceptó {rechazos.length === 1 ? "una planilla" : `${rechazos.length} planillas`}:
          </p>
          <ul className="mt-1 list-disc pl-6">{rechazos.map((r) => <li key={r}>{r}</li>)}</ul>
          <button onClick={descartarRechazosRodeo} className="mt-2 font-medium underline">Entendido</button>
        </div>
      )}
      {children}
    </div>
  );
}
