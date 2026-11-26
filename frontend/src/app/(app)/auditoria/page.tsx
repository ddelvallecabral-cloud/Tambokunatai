"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ShieldAlert, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { fechaHora } from "@/lib/formato";
import { useAuth } from "@/lib/auth";
import { Periodo, usePeriodo } from "@/components/Periodo";
import { Aviso, botonSecundario, estiloInput } from "@/components/ui";

type Fila = {
  id: number; fecha: string; usuario_nombre: string | null; rol_activo: string; accion: string; entidad: string;
  entidad_id: string; cambios: Record<string, unknown>; motivo: string; ip: string | null; dispositivo: string;
};
type Pagina = { count: number; next: string | null; results: Fila[] };
type Verificacion = { integra: boolean; filas_revisadas: number; primera_fila_alterada: number | null };

const ACCIONES: Record<string, string> = {
  crear: "Creó", editar: "Editó", enviar: "Envió a aprobar", aprobar: "Aprobó", rechazar: "Rechazó", cerrar: "Cerró",
  reabrir: "Reabrió", anular: "Anuló", editar_bloqueado: "Editó un registro cerrado", aplicar_correccion: "Aplicó una corrección",
  login: "Entró al sistema", login_fallido: "Intento de entrada fallido", logout: "Salió del sistema", cambio_clave: "Cambió la clave",
  cambio_permisos: "Cambió roles o permisos", registrar_venta: "Registró una venta", registrar_cobro: "Registró un cobro",
  anular_cobro: "Anuló un cobro", registrar_compra: "Registró una compra", registrar_pago: "Registró un pago",
  anular_pago: "Anuló un pago", entregar: "Entregó", usar_en_queso: "Destinó leche a queso", iniciar_elaboracion: "Inició la elaboración",
  ordene_por_vaca: "Cargó el ordeñe por vaca", configurar_alertas: "Configuró las alertas", revisar: "Marcó como revisado",
};
const ENTIDADES: Record<string, string> = {
  usuarios: "Usuarios", lotes_leche: "Lotes de leche", lotes_queso: "Lotes de queso", gastos: "Gastos", ventas: "Ventas",
  compras: "Compras", cuentas_por_cobrar: "Cuentas por cobrar", cuentas_por_pagar: "Cuentas por pagar", insumos: "Insumos",
  clientes: "Clientes", proveedores: "Proveedores", animales: "Animales", configuracion: "Configuración", auditoria: "Auditoría",
};
const nombre = (mapa: Record<string, string>, v: string) => mapa[v] ?? v.replace(/_/g, " ");

export default function PaginaAuditoria() {
  return <Suspense fallback={<p className="text-stone-500">Cargando…</p>}><Auditoria /></Suspense>;
}

function Auditoria() {
  const { puede } = useAuth();
  const params = useSearchParams();
  const router = useRouter();
  const ruta = usePathname();
  const { consulta } = usePeriodo();
  const entidad = params.get("entidad") ?? "";
  const accion = params.get("accion") ?? "";
  const [filas, setFilas] = useState<Fila[] | null>(null);
  const [total, setTotal] = useState(0);
  const [siguiente, setSiguiente] = useState(1);
  const [error, setError] = useState("");
  const [abierta, setAbierta] = useState<number | null>(null);
  const [verif, setVerif] = useState<Verificacion | null>(null);
  const [verificando, setVerificando] = useState(false);

  const base = `/auditoria?${consulta}&page_size=50${entidad ? `&entidad=${entidad}` : ""}${accion ? `&accion=${accion}` : ""}`;
  useEffect(() => {
    setFilas(null); setError("");
    api<Pagina>(`${base}&page=1`).then((p) => { setFilas(p.results); setTotal(p.count); setSiguiente(p.next ? 2 : 0); })
      .catch(() => setError("No se pudo cargar la auditoría."));
  }, [base]);

  async function masFilas() {
    const p = await api<Pagina>(`${base}&page=${siguiente}`);
    setFilas((f) => [...(f ?? []), ...p.results]);
    setSiguiente(p.next ? siguiente + 1 : 0);
  }
  async function verificar() {
    setVerificando(true);
    try { setVerif(await api<Verificacion>("/auditoria/verificar")); } finally { setVerificando(false); }
  }
  const filtrar = (clave: string, v: string) => {
    const q = new URLSearchParams(params.toString());
    if (v) q.set(clave, v); else q.delete(clave);
    router.replace(`${ruta}?${q}`);
  };

  if (!puede("auditoria.ver")) return <Aviso tipo="error">Tu rol no puede consultar la auditoría.</Aviso>;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Auditoría</h1>
        <p className="mt-1 text-sm text-stone-500">Todo lo que se hizo en el sistema, quién lo hizo y cuándo. Nadie puede borrar ni modificar esta lista.</p>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-2xl border border-stone-200 bg-white p-4" data-testid="verificacion">
        {verif ? (
          verif.integra ? (
            <p className="flex items-center gap-2 text-sm text-campo-800"><ShieldCheck className="h-5 w-5" aria-hidden />
              Intacta: se revisaron {verif.filas_revisadas.toLocaleString("es-PY")} registros y ninguno fue alterado.</p>
          ) : (
            <p className="flex items-center gap-2 text-sm font-medium text-red-700"><ShieldAlert className="h-5 w-5" aria-hidden />
              ¡Atención! El registro n.º {verif.primera_fila_alterada} fue alterado fuera del sistema.</p>
          )
        ) : <p className="text-sm text-stone-600">Comprobá que nadie haya tocado la auditoría directamente en la base de datos.</p>}
        <button type="button" onClick={verificar} disabled={verificando} className={`${botonSecundario} ml-auto`}>
          {verificando ? "Verificando…" : "Verificar integridad"}
        </button>
      </div>

      <Periodo />
      <div className="grid max-w-xl gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="f-ent" className="mb-1 block text-xs font-medium">Sobre qué</label>
          <select id="f-ent" value={entidad} onChange={(e) => filtrar("entidad", e.target.value)} className={estiloInput}>
            <option value="">Todo</option>
            {Object.entries(ENTIDADES).map(([v, n]) => <option key={v} value={v}>{n}</option>)}
          </select>
        </div>
        <div>
          <label htmlFor="f-acc" className="mb-1 block text-xs font-medium">Acción</label>
          <select id="f-acc" value={accion} onChange={(e) => filtrar("accion", e.target.value)} className={estiloInput}>
            <option value="">Todas</option>
            {Object.entries(ACCIONES).map(([v, n]) => <option key={v} value={v}>{n}</option>)}
          </select>
        </div>
      </div>

      {error ? <Aviso tipo="error">{error}</Aviso> : !filas ? <p className="text-stone-500">Cargando…</p> : filas.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-stone-500">No hay movimientos con esos filtros.</p>
      ) : (
        <>
          <p className="text-sm text-stone-500">{total.toLocaleString("es-PY")} {total === 1 ? "movimiento" : "movimientos"}</p>
          <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white" aria-label="Registro de auditoría">
            {filas.map((f) => {
              const cambios = Object.keys(f.cambios ?? {}).length > 0;
              return (
                <li key={f.id} className="text-sm">
                  <button type="button" onClick={() => setAbierta(abierta === f.id ? null : f.id)} aria-expanded={abierta === f.id}
                    className="flex w-full flex-wrap items-start gap-x-4 gap-y-1 px-4 py-3 text-left hover:bg-stone-50">
                    <span className="w-32 shrink-0 text-stone-500">{fechaHora(f.fecha)}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block"><b>{f.usuario_nombre ?? "Sistema"}</b> · {nombre(ACCIONES, f.accion).toLowerCase()}{" "}
                        <span className="text-stone-500">({nombre(ENTIDADES, f.entidad).toLowerCase()})</span></span>
                      {f.motivo && <span className="block text-xs text-stone-500">“{f.motivo}”</span>}
                    </span>
                  </button>
                  {abierta === f.id && (
                    <div className="space-y-2 bg-stone-50 px-4 py-3 text-xs text-stone-600">
                      <p>Registro {f.entidad_id || "—"} · rol {f.rol_activo || "—"} · IP {f.ip || "—"} · {f.dispositivo || "dispositivo desconocido"}</p>
                      {cambios && <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded-lg bg-white p-2 font-mono text-[11px]">{JSON.stringify(f.cambios, null, 2)}</pre>}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
          {siguiente > 0 && <button type="button" onClick={masFilas} className={botonSecundario}>Ver más</button>}
        </>
      )}
    </div>
  );
}
