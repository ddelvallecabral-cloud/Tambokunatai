"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ResumenGastos } from "@/lib/egresos";
import { FormGasto } from "@/components/FormGasto";

export default function CargarGasto() {
  const router = useRouter();
  const [umbral, setUmbral] = useState<number>();
  useEffect(() => {
    api<ResumenGastos>("/gastos/resumen").then((r) => setUmbral(r.umbral_aprobacion));
  }, []);
  return <FormGasto umbral={umbral} onGuardado={(g) => router.push(`/gastos/${g.id}?cargado=1`)} />;
}
