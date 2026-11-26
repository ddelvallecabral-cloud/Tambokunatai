"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { ArrowLeft, CheckCircle2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fechaHora } from "@/lib/formato";
import { fechaCorta } from "@/lib/leche";
import { gs } from "@/lib/ventas";
import { ESTADO_GASTO, NOMBRE_CATEGORIA, NOMBRE_CENTRO, type Gasto } from "@/lib/egresos";
import { VerComprobante } from "@/components/Comprobante";
import { FormGasto } from "@/components/FormGasto";
import { DecidirAprobacion } from "@/components/DecidirAprobacion";
import { Aviso, estiloInput, Insignia } from "@/components/ui";

export default function DetalleGasto() {
  return (
    <Suspense fallback={<p className="text-stone-500">Cargando…</p>}>
      <Detalle />
    </Suspense>
  );
}

function Detalle() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const { usuario, puede } = useAuth();
  const [g, setG] = useState<Gasto | null>(null);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [corrigiendo, setCorrigiendo] = useState(false);
  const [version, setVersion] = useState(0);

  const cargar = useCallback(() => api<Gasto>(`/gastos/${id}`).then(setG).catch(() => setError("No se encontró el gasto.")), [id]);
  useEffect(() => {
    cargar();
  }, [cargar]);
  useEffect(() => {
    if (g && params.get("cargado")) {
      setAviso(g.estado === "pendiente" ? "Gasto guardado. Quedó pendiente hasta que lo apruebe el Administrador." : "Gasto guardado y aprobado.");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [g?.id]);

  async function accion(ruta: string, cuerpo: object, mensaje: string) {
    setError(""); setAviso("");
    try {
      setG(await api<Gasto>(`/gastos/${id}/${ruta}`, { method: "POST", body: JSON.stringify(cuerpo) }));
      setAviso(mensaje);
      return true;
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar.");
      return false;
    }
  }

  if (!g) return error ? <Aviso tipo="error">{error}</Aviso> : <p className="text-stone-500">Cargando…</p>;
  const estado = ESTADO_GASTO[g.estado];
  const esMio = usuario?.id === g.creado_por;
  const admin = puede("gastos.gasto.aprobar");

  return (
    <div className="space-y-5">
      <Link href="/gastos" className="inline-flex items-center gap-1 text-sm text-stone-600 hover:text-stone-900">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Gastos
      </Link>
      {aviso && <Aviso tipo="ok">{aviso}</Aviso>}
      {error && <Aviso tipo="error">{error}</Aviso>}
      {g.estado === "rechazado" && <Aviso tipo="error">Rechazado por el Administrador: “{g.motivo_estado}”. {esMio && "Corregilo y volvé a enviarlo."}</Aviso>}
      {g.estado === "anulado" && <Aviso tipo="alerta">Anulado: “{g.motivo_estado}”.</Aviso>}

      <section className="space-y-3 rounded-2xl border border-stone-200 bg-white p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm text-stone-500">{fechaCorta(g.fecha)} · {NOMBRE_CATEGORIA[g.categoria]} · {NOMBRE_CENTRO[g.centro_costo]}</p>
            <h2 className="text-xl font-semibold">{g.descripcion}</h2>
            {g.proveedor_nombre && <p className="text-sm text-stone-600">Proveedor: {g.proveedor_nombre}</p>}
            {g.comprobante_numero && <p className="text-sm text-stone-600">Comprobante n.º {g.comprobante_numero}</p>}
          </div>
          <div className="text-right">
            <p className="text-3xl font-semibold tabular-nums">{gs(g.monto)}</p>
            <Insignia color={estado.color}>{estado.nombre}</Insignia>
          </div>
        </div>
        <ol className="space-y-1 border-t border-stone-100 pt-3 text-sm">
          <li className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 text-campo-600" aria-hidden />Cargado por {g.creado_por_nombre ?? "—"} · {fechaHora(g.fecha_creacion)}</li>
          {g.estado === "aprobado" && (
            <li className="flex gap-2"><CheckCircle2 className="mt-0.5 h-4 w-4 text-campo-600" aria-hidden />
              {g.aprobacion_automatica ? "Aprobado automáticamente (no supera el monto que pide aprobación)" : `Aprobado por ${g.aprobado_por_nombre ?? "—"}`}
              {g.fecha_aprobacion && ` · ${fechaHora(g.fecha_aprobacion)}`}
              {!g.aprobacion_automatica && g.motivo_estado && ` · “${g.motivo_estado}”`}
            </li>
          )}
        </ol>
      </section>

      <section className="space-y-2 rounded-2xl border border-stone-200 bg-white p-5">
        <h3 className="font-semibold">Comprobante</h3>
        {g.tiene_comprobante ? <VerComprobante key={version} ruta={`/gastos/${g.id}/comprobante`} tipo={g.tipo_comprobante} />
          : <p className="text-sm text-stone-500">No se adjuntó foto del comprobante.</p>}
      </section>

      {esMio && (g.estado === "rechazado" || g.estado === "pendiente") && (corrigiendo ? (
        <FormGasto gasto={g} onGuardado={(n) => { setG(n); setCorrigiendo(false); setVersion((v) => v + 1); setAviso(n.estado === "aprobado" ? "Corregido y aprobado." : "Corregido y enviado de nuevo al Administrador."); }} />
      ) : (
        <button onClick={() => setCorrigiendo(true)} className="text-sm font-medium text-campo-700 hover:underline">Corregir este gasto</button>
      ))}

      {admin && g.estado === "pendiente" && <DecidirAprobacion onAprobar={(c) => accion("aprobar", { comentario: c }, "Gasto aprobado.")} onRechazar={(c) => accion("rechazar", { comentario: c }, "Gasto rechazado. Quien lo cargó ve tu comentario.")} />}
      {admin && g.estado !== "anulado" && g.estado !== "pendiente" && <Anular onAnular={(m) => accion("anular", { motivo: m }, "Gasto anulado.")} />}
    </div>
  );
}

function Anular({ onAnular }: { onAnular: (m: string) => Promise<boolean> }) {
  const [abierto, setAbierto] = useState(false);
  const [motivo, setMotivo] = useState("");
  if (!abierto) return <button onClick={() => setAbierto(true)} className="text-sm font-medium text-red-700 hover:underline">Anular gasto</button>;
  return (
    <div className="space-y-2 rounded-2xl border border-red-200 bg-red-50 p-4">
      <label htmlFor="motivo" className="block text-sm font-medium text-red-900">¿Por qué se anula?</label>
      <input id="motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)} className={estiloInput} />
      <div className="flex gap-2">
        <button disabled={!motivo.trim()} onClick={async () => (await onAnular(motivo)) && setAbierto(false)} className="rounded-lg bg-red-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">Anular</button>
        <button onClick={() => setAbierto(false)} className="px-3 py-2 text-sm">Volver</button>
      </div>
    </div>
  );
}
