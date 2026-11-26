import { api, ApiError } from "./api";

export type Ordene = "manana" | "tarde";
export type TipoDestino = "venta" | "elaboracion_queso" | "descarte";
export type DestinoResumen = TipoDestino | "pendiente" | "mixto";

export type Destino = {
  id: string;
  tipo: TipoDestino;
  litros: string;
  nota: string;
  creado_por_nombre: string | null;
  fecha_creacion: string;
};

export type Lote = {
  id: string;
  codigo: string;
  fecha: string;
  ordene: Ordene;
  litros: string;
  grasa_pct: string | null;
  proteina_pct: string | null;
  temperatura_c: string | null;
  observaciones: string;
  destino: DestinoResumen;
  litros_asignados: string;
  saldo_disponible: string;
  destinos: Destino[];
  estado: "borrador" | "pendiente" | "aprobado" | "rechazado" | "cerrado" | "anulado";
  motivo_estado: string;
  cambios_propuestos: Record<string, string | null> | null;
  propuesto_por_nombre: string | null;
  creado_por_nombre: string | null;
  aprobado_por_nombre: string | null;
  fecha_creacion: string;
  resultado?: "aplicado" | "pendiente" | "sin_cambios";
};

export type Resumen = {
  fecha: string;
  total_litros: string;
  por_ordene: Record<Ordene, string>;
  por_destino: Record<TipoDestino | "pendiente", string>;
  saldo_disponible: string;
  ordenes_faltantes: Ordene[];
  lotes: number;
};

export type Tablero = {
  fecha: string;
  hoy: Resumen;
  mes: { desde: string; litros: string; dias_con_carga: number; promedio_diario: string };
  ultimos_14_dias: { fecha: string; litros: string }[];
  umbral_litros_diarios: string | null;
  alertas: { nivel: string; fecha: string; mensaje: string }[];
  correcciones_pendientes: number;
  lotes_con_saldo: number;
};

export const ORDENES: { valor: Ordene; nombre: string }[] = [
  { valor: "manana", nombre: "Mañana" },
  { valor: "tarde", nombre: "Tarde" },
];

export const DESTINOS: { valor: TipoDestino | "pendiente"; nombre: string; corto: string }[] = [
  { valor: "elaboracion_queso", nombre: "Elaboración de queso", corto: "Queso" },
  { valor: "venta", nombre: "Venta", corto: "Venta" },
  { valor: "descarte", nombre: "Descarte", corto: "Descarte" },
  { valor: "pendiente", nombre: "Pendiente (decidir después)", corto: "Pendiente" },
];

export const NOMBRE_DESTINO: Record<DestinoResumen, string> = {
  elaboracion_queso: "Queso",
  venta: "Venta",
  descarte: "Descarte",
  pendiente: "Pendiente",
  mixto: "Repartido",
};

export const NOMBRE_ESTADO: Record<Lote["estado"], string> = {
  borrador: "Abierto",
  pendiente: "Corrección pendiente",
  aprobado: "Corrección aprobada",
  rechazado: "Corrección rechazada",
  cerrado: "Cerrado",
  anulado: "Anulado",
};

const numero = new Intl.NumberFormat("es-PY", { maximumFractionDigits: 1 });
export const litros = (v: string | number | null | undefined) => `${numero.format(Number(v ?? 0))} L`;

/** Fecha local de hoy en formato AAAA-MM-DD (no UTC). */
export function hoyISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function fechaCorta(iso: string): string {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(a, m - 1, d).toLocaleDateString("es-PY", { weekday: "short", day: "numeric", month: "short" });
}

// --- Cola sin conexión ---------------------------------------------------------------
// Si al guardar no hay señal, el lote queda en el teléfono y se envía solo al volver la conexión.
// Cada lote lleva un id generado acá: si el envío se repite, el servidor no lo duplica.

export type LoteNuevo = {
  id: string;
  fecha: string;
  ordene: Ordene;
  litros: string;
  destino: TipoDestino | "pendiente";
  grasa_pct?: string | null;
  proteina_pct?: string | null;
  temperatura_c?: string | null;
  observaciones?: string;
};

const CLAVE_COLA = "tambo.cola.lotes_leche";

function leerCola(): LoteNuevo[] {
  try {
    return JSON.parse(localStorage.getItem(CLAVE_COLA) ?? "[]");
  } catch {
    return [];
  }
}

function guardarCola(cola: LoteNuevo[]) {
  try {
    localStorage.setItem(CLAVE_COLA, JSON.stringify(cola));
  } catch {
    /* almacenamiento no disponible */
  }
  window.dispatchEvent(new Event("cola-leche"));
}

export const pendientesEnCola = () => leerCola();

export async function registrarLote(datos: LoteNuevo): Promise<{ lote?: Lote; enCola: boolean }> {
  try {
    const lote = await api<Lote>("/lotes-leche", { method: "POST", body: JSON.stringify(datos) });
    return { lote, enCola: false };
  } catch (error) {
    if (error instanceof ApiError) throw error; // el servidor respondió: es un error real
    guardarCola([...leerCola().filter((l) => l.id !== datos.id), datos]);
    return { enCola: true };
  }
}

let enviando = false;

/** Intenta enviar lo que quedó en el teléfono. Devuelve cuántos se enviaron. */
export async function enviarCola(): Promise<{ enviados: number; errores: string[] }> {
  if (enviando) return { enviados: 0, errores: [] };
  enviando = true;
  let enviados = 0;
  const errores: string[] = [];
  try {
    for (const datos of leerCola()) {
      try {
        await api<Lote>("/lotes-leche", { method: "POST", body: JSON.stringify(datos) });
        enviados++;
        guardarCola(leerCola().filter((l) => l.id !== datos.id));
      } catch (error) {
        if (!(error instanceof ApiError)) break; // sigue sin señal
        if (error.status === 401) break; // sesión vencida: se reintenta al volver a entrar
        errores.push(`${datos.fecha} ${datos.ordene}: ${error.message}`);
        guardarCola(leerCola().filter((l) => l.id !== datos.id));
      }
    }
  } finally {
    enviando = false;
  }
  return { enviados, errores };
}
