"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Trash2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { DESTINOS, fechaCorta, hoyISO, litros, NOMBRE_DESTINO, NOMBRE_ESTADO, type Lote, type TipoDestino } from "@/lib/leche";

const CAMPOS: { clave: keyof Lote; nombre: string }[] = [
  { clave: "fecha", nombre: "Fecha" },
  { clave: "ordene", nombre: "Ordeñe" },
  { clave: "litros", nombre: "Litros" },
  { clave: "grasa_pct", nombre: "Grasa %" },
  { clave: "proteina_pct", nombre: "Proteína %" },
  { clave: "temperatura_c", nombre: "Temperatura °C" },
  { clave: "observaciones", nombre: "Observaciones" },
];

const estiloInput = "w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-base";
const boton = "rounded-lg px-4 py-2.5 text-sm font-medium disabled:opacity-50";

export default function DetalleLote() {
  const { id } = useParams<{ id: string }>();
  const { puede } = useAuth();
  const admin = puede("leche.lote.aprobar");
  const [lote, setLote] = useState<Lote | null>(null);
  const [aviso, setAviso] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const cargar = useCallback(() => api<Lote>(`/lotes-leche/${id}`).then(setLote), [id]);
  useEffect(() => {
    cargar().catch(() => setAviso({ tipo: "error", texto: "No se encontró el lote." }));
  }, [cargar]);

  async function ejecutar(fn: () => Promise<Lote>, ok: string | ((l: Lote) => string)) {
    setOcupado(true);
    setAviso(null);
    try {
      const l = await fn();
      setLote(l);
      setAviso({ tipo: "ok", texto: typeof ok === "string" ? ok : ok(l) });
      return true;
    } catch (e) {
      setAviso({ tipo: "error", texto: e instanceof ApiError ? e.message : "No se pudo completar." });
      return false;
    } finally {
      setOcupado(false);
    }
  }

  if (!lote) return <p className="text-stone-500">{aviso?.texto ?? "Cargando…"}</p>;

  const saldo = Number(lote.saldo_disponible);
  const abierto = ["borrador", "aprobado", "rechazado"].includes(lote.estado);
  const diaAnterior = lote.fecha < hoyISO();
  const post = (ruta: string, cuerpo?: object) => () =>
    api<Lote>(`/lotes-leche/${lote.id}${ruta}`, { method: "POST", body: JSON.stringify(cuerpo ?? {}) });

  return (
    <div className="space-y-4">
      <Link href="/leche/lotes" className="inline-flex items-center gap-1 text-sm text-stone-600 hover:text-stone-900">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Lotes
      </Link>

      <section className="rounded-2xl border border-stone-200 bg-white p-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="text-sm text-stone-500">{lote.codigo}</p>
            <h2 className="text-xl font-semibold">
              {fechaCorta(lote.fecha)} · ordeñe de la {lote.ordene === "manana" ? "mañana" : "tarde"}
            </h2>
          </div>
          <span className="rounded-full bg-stone-100 px-2.5 py-1 text-xs font-medium" data-testid="estado-lote">{NOMBRE_ESTADO[lote.estado]}</span>
        </div>
        <dl className="mt-4 grid grid-cols-3 gap-3 text-sm">
          <div><dt className="text-stone-500">Litros</dt><dd className="text-2xl font-semibold tabular-nums">{litros(lote.litros)}</dd></div>
          <div><dt className="text-stone-500">Con destino</dt><dd className="text-2xl font-semibold tabular-nums">{litros(lote.litros_asignados)}</dd></div>
          <div><dt className="text-stone-500">Saldo disponible</dt><dd className={`text-2xl font-semibold tabular-nums ${saldo > 0 ? "text-amber-700" : ""}`} data-testid="saldo">{litros(saldo)}</dd></div>
        </dl>
        <p className="mt-3 text-xs text-stone-500">
          Cargado por {lote.creado_por_nombre ?? "—"}
          {lote.grasa_pct && ` · grasa ${lote.grasa_pct}%`}
          {lote.proteina_pct && ` · proteína ${lote.proteina_pct}%`}
          {lote.temperatura_c && ` · ${lote.temperatura_c} °C`}
          {lote.motivo_estado && ` · Motivo: ${lote.motivo_estado}`}
        </p>
        {lote.observaciones && <p className="mt-2 text-sm">{lote.observaciones}</p>}
      </section>

      {aviso && (
        <p role={aviso.tipo === "error" ? "alert" : "status"} className={`rounded-lg px-3 py-2 text-sm ${aviso.tipo === "error" ? "bg-red-50 text-red-700" : "bg-campo-50 text-campo-900"}`}>
          {aviso.texto}
        </p>
      )}

      {lote.estado === "pendiente" && lote.cambios_propuestos && (
        <Correccion lote={lote} admin={admin} ocupado={ocupado}
          aprobar={() => ejecutar(post("/aprobar"), "Corrección aprobada y aplicada.")}
          rechazar={(motivo) => ejecutar(post("/rechazar", { motivo }), "Corrección rechazada.")} />
      )}

      <Destinos lote={lote} abierto={abierto} admin={admin} ocupado={ocupado}
        asignar={(tipo, l) => ejecutar(post("/destinos", { tipo, litros: l }), "Destino asignado.")}
        quitar={(destinoId) => ejecutar(() => api<Lote>(`/lotes-leche/${lote.id}/destinos/${destinoId}`, { method: "DELETE", body: "{}" }), "Destino quitado.")} />

      {lote.estado !== "anulado" && lote.estado !== "pendiente" && (puede("leche.lote.gestionar") && (abierto || admin)) && (
        <Edicion lote={lote} admin={admin} diaAnterior={diaAnterior} ocupado={ocupado}
          guardar={(cambios) => ejecutar(
            () => api<Lote>(`/lotes-leche/${lote.id}`, { method: "PATCH", body: JSON.stringify(cambios) }),
            (l) => l.resultado === "pendiente" ? "Corrección enviada al Administrador para aprobación." : l.resultado === "sin_cambios" ? "No había cambios." : "Cambios guardados.",
          )} />
      )}

      <div className="flex flex-wrap gap-2">
        {abierto && saldo === 0 && puede("leche.lote.cerrar") && (
          <button disabled={ocupado} onClick={() => ejecutar(post("/cerrar"), "Lote cerrado.")} className={`${boton} bg-stone-800 text-white`}>Cerrar lote</button>
        )}
        {admin && <AccionConMotivo etiqueta="Anular lote" visible={lote.estado !== "anulado"} ocupado={ocupado}
          ejecutar={(motivo) => ejecutar(post("/anular", { motivo }), "Lote anulado.")} />}
        {admin && <AccionConMotivo etiqueta="Reabrir" visible={["cerrado", "aprobado"].includes(lote.estado)} ocupado={ocupado}
          ejecutar={(motivo) => ejecutar(post("/reabrir", { motivo }), "Lote reabierto.")} />}
      </div>
    </div>
  );
}

function Correccion({ lote, admin, ocupado, aprobar, rechazar }: {
  lote: Lote; admin: boolean; ocupado: boolean; aprobar: () => void; rechazar: (motivo: string) => Promise<boolean>;
}) {
  const [motivo, setMotivo] = useState("");
  const cambios = lote.cambios_propuestos!;
  return (
    <section className="rounded-2xl border border-sky-200 bg-sky-50 p-5" aria-labelledby="correccion">
      <h3 id="correccion" className="font-semibold text-sky-900">Corrección esperando aprobación</h3>
      <p className="mt-1 text-sm text-sky-900">
        Propuesta por {lote.propuesto_por_nombre ?? "—"}{cambios._motivo ? `: “${cambios._motivo}”` : ""}. Los valores del lote no cambian hasta que se apruebe.
      </p>
      <table className="mt-3 w-full text-sm">
        <thead><tr className="text-left text-sky-800"><th className="py-1 font-medium">Campo</th><th className="font-medium">Ahora</th><th className="font-medium">Propuesto</th></tr></thead>
        <tbody>
          {CAMPOS.filter((c) => c.clave in cambios).map((c) => (
            <tr key={c.clave} className="border-t border-sky-200">
              <td className="py-1.5">{c.nombre}</td>
              <td className="tabular-nums">{String(lote[c.clave] ?? "—")}</td>
              <td className="font-semibold tabular-nums">{cambios[c.clave] ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {admin && (
        <div className="mt-4 flex flex-col gap-2 sm:flex-row">
          <button disabled={ocupado} onClick={aprobar} className={`${boton} bg-campo-700 text-white`}>Aprobar</button>
          <input value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Motivo del rechazo" className={`${estiloInput} sm:flex-1`} />
          <button disabled={ocupado || !motivo.trim()} onClick={() => rechazar(motivo)} className={`${boton} border border-red-300 bg-white text-red-700`}>Rechazar</button>
        </div>
      )}
    </section>
  );
}

function Destinos({ lote, abierto, admin, ocupado, asignar, quitar }: {
  lote: Lote; abierto: boolean; admin: boolean; ocupado: boolean;
  asignar: (tipo: TipoDestino, litros: string) => Promise<boolean>; quitar: (id: string) => void;
}) {
  const saldo = Number(lote.saldo_disponible);
  const [tipo, setTipo] = useState<TipoDestino>("elaboracion_queso");
  const [cantidad, setCantidad] = useState("");
  const puedeQuitar = admin || (abierto && lote.fecha >= hoyISO());

  return (
    <section className="rounded-2xl border border-stone-200 bg-white p-5" aria-labelledby="destinos">
      <h3 id="destinos" className="font-semibold">Destinos · {NOMBRE_DESTINO[lote.destino]}</h3>
      {lote.destinos.length === 0 ? (
        <p className="mt-2 text-sm text-stone-500">Todavía no se asignaron litros.</p>
      ) : (
        <ul className="mt-2 divide-y divide-stone-100">
          {lote.destinos.map((d) => (
            <li key={d.id} className="flex items-center gap-3 py-2 text-sm">
              <span className="flex-1">{NOMBRE_DESTINO[d.tipo]}{d.nota && <span className="text-stone-500"> · {d.nota}</span>}</span>
              <span className="font-medium tabular-nums">{litros(d.litros)}</span>
              {puedeQuitar && (
                <button disabled={ocupado} onClick={() => quitar(d.id)} aria-label={`Quitar ${NOMBRE_DESTINO[d.tipo]}`} className="text-stone-400 hover:text-red-600">
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {abierto && saldo > 0 && (
        <form
          className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-[1fr_8rem_auto]"
          onSubmit={async (e) => {
            e.preventDefault();
            if (await asignar(tipo, (cantidad || String(saldo)).replace(",", "."))) setCantidad("");
          }}
        >
          <select value={tipo} onChange={(e) => setTipo(e.target.value as TipoDestino)} className={`${estiloInput} col-span-2 sm:col-span-1`} aria-label="Destino">
            {DESTINOS.filter((d) => d.valor !== "pendiente").map((d) => <option key={d.valor} value={d.valor}>{d.nombre}</option>)}
          </select>
          <input inputMode="decimal" value={cantidad} onChange={(e) => setCantidad(e.target.value)} placeholder={`${saldo}`} aria-label="Litros a asignar" className={estiloInput} />
          <button disabled={ocupado} className={`${boton} bg-campo-700 text-white`}>Asignar</button>
          <p className="col-span-2 text-xs text-stone-500 sm:col-span-3">Disponibles: {litros(saldo)}. Si dejás vacío, se asigna todo el saldo.</p>
        </form>
      )}
    </section>
  );
}

function Edicion({ lote, admin, diaAnterior, ocupado, guardar }: {
  lote: Lote; admin: boolean; diaAnterior: boolean; ocupado: boolean; guardar: (c: Record<string, string | null>) => Promise<boolean>;
}) {
  const [abierta, setAbierta] = useState(false);
  const inicial = () => ({
    litros: lote.litros, grasa_pct: lote.grasa_pct ?? "", proteina_pct: lote.proteina_pct ?? "",
    temperatura_c: lote.temperatura_c ?? "", observaciones: lote.observaciones, motivo: "",
  });
  const [v, setV] = useState(inicial);
  const bloqueado = ["cerrado", "aprobado"].includes(lote.estado);
  const pideAprobacion = !admin && diaAnterior;
  const motivoObligatorio = admin && bloqueado;

  if (!abierta) {
    return (
      <button onClick={() => { setV(inicial()); setAbierta(true); }} className={`${boton} border border-stone-300 bg-white`}>
        Corregir datos del lote
      </button>
    );
  }
  const campo = (k: keyof typeof v, nombre: string) => (
    <label className="text-xs font-medium text-stone-600">
      {nombre}
      <input inputMode={k === "observaciones" || k === "motivo" ? "text" : "decimal"} value={v[k]} onChange={(e) => setV({ ...v, [k]: e.target.value })} className={`${estiloInput} mt-1`} />
    </label>
  );

  return (
    <form
      className="space-y-3 rounded-2xl border border-stone-200 bg-white p-5"
      onSubmit={async (e) => {
        e.preventDefault();
        const n = (x: string) => (x.trim() === "" ? null : x.replace(",", "."));
        const ok = await guardar({
          litros: n(v.litros), grasa_pct: n(v.grasa_pct), proteina_pct: n(v.proteina_pct),
          temperatura_c: n(v.temperatura_c), observaciones: v.observaciones, motivo: v.motivo,
        });
        if (ok) setAbierta(false);
      }}
    >
      <h3 className="font-semibold">Corregir datos</h3>
      {pideAprobacion && (
        <p className="rounded-lg bg-sky-50 px-3 py-2 text-sm text-sky-900">
          Este lote es de un día anterior: tu corrección queda pendiente hasta que el Administrador la apruebe.
        </p>
      )}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {campo("litros", "Litros")}
        {campo("grasa_pct", "Grasa %")}
        {campo("proteina_pct", "Proteína %")}
        {campo("temperatura_c", "Temp. °C")}
      </div>
      {campo("observaciones", "Observaciones")}
      {campo("motivo", motivoObligatorio ? "Motivo (obligatorio)" : "Motivo de la corrección")}
      <div className="flex gap-2">
        <button disabled={ocupado || (motivoObligatorio && !v.motivo.trim())} className={`${boton} bg-campo-700 text-white`}>
          {pideAprobacion ? "Enviar a aprobación" : "Guardar cambios"}
        </button>
        <button type="button" onClick={() => setAbierta(false)} className={`${boton} border border-stone-300`}>Cancelar</button>
      </div>
    </form>
  );
}

function AccionConMotivo({ etiqueta, visible, ocupado, ejecutar }: {
  etiqueta: string; visible: boolean; ocupado: boolean; ejecutar: (motivo: string) => Promise<boolean>;
}) {
  const [abierta, setAbierta] = useState(false);
  const [motivo, setMotivo] = useState("");
  if (!visible) return null;
  if (!abierta) return <button onClick={() => setAbierta(true)} className={`${boton} border border-stone-300 bg-white`}>{etiqueta}</button>;
  return (
    <div className="flex w-full flex-col gap-2 sm:flex-row">
      <input autoFocus value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder={`Motivo para ${etiqueta.toLowerCase()}`} className={`${estiloInput} sm:flex-1`} />
      <button disabled={ocupado || !motivo.trim()} onClick={async () => { if (await ejecutar(motivo)) setAbierta(false); }} className={`${boton} bg-stone-800 text-white`}>{etiqueta}</button>
      <button onClick={() => setAbierta(false)} className={`${boton} border border-stone-300`}>Cancelar</button>
    </div>
  );
}
