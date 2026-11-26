import { api, ApiError } from "./api";
import type { Lote, Ordene, TipoDestino } from "./leche";

export type Situacion = "en_ordene" | "seca" | "en_recria" | "vendida" | "muerta";

export type Animal = {
  id: string;
  caravana: string;
  nombre: string;
  categoria: string;
  raza: string;
  fecha_nacimiento: string | null;
  situacion: Situacion;
  observaciones: string;
  promedio_7d: string | null;
  promedio_7d_anterior: string | null;
  tendencia: "sube" | "baja" | "estable" | null;
};

export const SITUACIONES: { valor: Situacion; nombre: string }[] = [
  { valor: "en_ordene", nombre: "En ordeñe" },
  { valor: "seca", nombre: "Seca" },
  { valor: "en_recria", nombre: "En recría" },
  { valor: "vendida", nombre: "Vendida" },
  { valor: "muerta", nombre: "Muerta" },
];
export const NOMBRE_SITUACION = Object.fromEntries(SITUACIONES.map((s) => [s.valor, s.nombre])) as Record<Situacion, string>;

export type Planilla = {
  fecha: string;
  ordene: Ordene;
  lote: { id: string; codigo: string; litros: string; estado: string; con_detalle_por_vaca: boolean } | null;
  vacas: { animal: string; caravana: string; nombre: string; litros: string | null; observaciones: string }[];
};

export type EnvioPlanilla = {
  clave: string; // fecha + ordeñe: la última planilla de una sesión reemplaza a la anterior en la cola
  fecha: string;
  ordene: Ordene;
  destino: TipoDestino | "pendiente";
  items: { animal: string; litros: string }[];
  motivo?: string;
};

export type RespuestaPlanilla = { lote: Lote; creado: boolean; total: string; total_anterior: string | null; vacas_cambiadas: number };

// --- Cola sin conexión ----------------------------------------------------------------
// La planilla se guarda completa: reenviarla no duplica nada, así que se puede reintentar sin miedo.
const CLAVE = "tambo.cola.ordene_vacas";
const CLAVE_RECHAZOS = "tambo.cola.ordene_vacas.rechazados";

function leer<T>(clave: string): T[] {
  try {
    return JSON.parse(localStorage.getItem(clave) ?? "[]");
  } catch {
    return [];
  }
}
function escribir(clave: string, valor: unknown[]) {
  try {
    localStorage.setItem(clave, JSON.stringify(valor));
  } catch {
    /* sin almacenamiento */
  }
  window.dispatchEvent(new Event("cola-rodeo"));
}

export const planillasEnCola = () => leer<EnvioPlanilla>(CLAVE);
export const rechazosRodeo = () => leer<string>(CLAVE_RECHAZOS);
export const descartarRechazosRodeo = () => escribir(CLAVE_RECHAZOS, []);

const cuerpo = (p: EnvioPlanilla) => JSON.stringify({ fecha: p.fecha, ordene: p.ordene, destino: p.destino, items: p.items, motivo: p.motivo ?? "" });

export async function enviarPlanilla(p: EnvioPlanilla): Promise<{ respuesta?: RespuestaPlanilla; enCola: boolean }> {
  try {
    const respuesta = await api<RespuestaPlanilla>("/rodeo/ordene", { method: "POST", body: cuerpo(p) });
    return { respuesta, enCola: false };
  } catch (error) {
    if (error instanceof ApiError) throw error;
    escribir(CLAVE, [...planillasEnCola().filter((x) => x.clave !== p.clave), p]);
    return { enCola: true };
  }
}

let enviando = false;
export async function enviarColaRodeo() {
  if (enviando) return;
  enviando = true;
  try {
    for (const p of planillasEnCola()) {
      try {
        await api("/rodeo/ordene", { method: "POST", body: cuerpo(p) });
        escribir(CLAVE, planillasEnCola().filter((x) => x.clave !== p.clave));
      } catch (error) {
        if (!(error instanceof ApiError) || error.status === 401) break;
        const sesion = p.ordene === "manana" ? "mañana" : "tarde";
        escribir(CLAVE_RECHAZOS, [...rechazosRodeo(), `Ordeñe del ${p.fecha} (${sesion}): ${error.message}`]);
        escribir(CLAVE, planillasEnCola().filter((x) => x.clave !== p.clave));
      }
    }
  } finally {
    enviando = false;
  }
}
