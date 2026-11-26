"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";

export default function Reportes() {
  const { puede } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (puede("reportes.financieros")) router.replace("/reportes/resultados");
    else if (puede("reportes.operativos")) router.replace("/reportes/alertas");
    else if (puede("reportes.ventas_propias")) router.replace("/reportes/mis-ventas");
  }, [puede, router]);
  return null;
}
