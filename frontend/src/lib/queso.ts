export type EstadoQueso = "borrador" | "pendiente" | "aprobado" | "rechazado" | "anulado";

export type LoteQueso = {
  id: string;
  codigo: string;
  numero: number;
  fecha: string;
  litros_leche: string;
  kg_obtenidos: string | null;
  merma_kg: string;
  kg_netos: string | null;
  rendimiento_l_kg: string | null;
  rendimiento_fuera_de_rango: boolean;
  observaciones: string;
  estado: EstadoQueso;
  motivo_estado: string;
  origenes: { lote_leche: string; codigo: string; fecha: string; ordene: string; litros: string; vigente: boolean }[];
  insumos: { insumo: string; nombre: string; unidad: string; cantidad_declarada: string; cantidad_consumida: string | null }[];
  creado_por: string | null;
  creado_por_nombre: string | null;
  fecha_creacion: string;
  cerrado_por_nombre: string | null;
  fecha_cierre: string | null;
  aprobado_por_nombre: string | null;
  fecha_aprobacion: string | null;
};

export const ESTADOS_QUESO: { valor: EstadoQueso; nombre: string; color: string }[] = [
  { valor: "borrador", nombre: "En elaboración", color: "azul" },
  { valor: "pendiente", nombre: "Pendiente de aprobación", color: "ambar" },
  { valor: "aprobado", nombre: "Aprobado", color: "verde" },
  { valor: "rechazado", nombre: "Rechazado", color: "rojo" },
  { valor: "anulado", nombre: "Cancelado", color: "gris" },
];
export const ESTADO_QUESO = Object.fromEntries(ESTADOS_QUESO.map((e) => [e.valor, e])) as Record<EstadoQueso, (typeof ESTADOS_QUESO)[number]>;

export type LecheDisponible = {
  id: string;
  codigo: string;
  fecha: string;
  ordene: string;
  litros: string;
  estado: string;
  destinado_a_queso: string;
  sin_destino: string;
  total: string;
};

export type Trazabilidad = {
  codigo: string;
  estado: EstadoQueso;
  origen_leche: {
    lote_leche: string; codigo: string; fecha: string; ordene: string; litros_usados: string; litros_del_lote: string;
    vigente: boolean; grasa_pct: string | null; proteina_pct: string | null; temperatura_c: string | null;
    vacas: { caravana: string; nombre: string; litros: string }[];
  }[];
  insumos: { insumo: string; nombre: string; unidad: string; declarada: string; consumida: string | null; lotes_proveedor_recientes: string[] }[];
  movimientos: { fecha: string; item: string; tipo: string; motivo: string; cantidad: string; unidad: string; insumo: string | null; lote_leche: string | null; usuario: string | null }[];
  queso_en_stock_kg: string;
  clientes: { cliente: string; nombre: string; venta: string; codigo_venta: string; fecha: string; kg: string }[];
  historial: { fecha: string; accion: string; usuario: string | null; motivo: string }[];
};

export type ResumenQueso = {
  rango_rendimiento: { min: string; max: string };
  en_elaboracion: number;
  pendientes_aprobacion: number;
  rechazados: number;
  mes: { lotes: number; kg_obtenidos: string; litros_leche: string; rendimiento_l_kg: string | null; fuera_de_rango: number };
  leche_disponible_litros: string;
  queso: { kg_disponibles: string; kg_en_revision: string };
};

export const NOMBRE_ACCION: Record<string, string> = {
  crear: "Creado", iniciar_elaboracion: "Elaboración iniciada", enviar: "Cerrado y enviado a aprobación",
  aprobar: "Aprobado", rechazar: "Rechazado", anular: "Cancelado", editar: "Datos actualizados",
};
