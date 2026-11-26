export type Alerta = { tipo: "produccion_baja" | "rendimiento" | "stock_bajo" | "cuenta_vencida"; nivel: string; fecha: string; texto: string; ruta: string };

export type Tablero = {
  operativo: {
    fecha: string;
    leche: { hoy: string; mes: string; ultimos_30: { fecha: string; litros: string }[] };
    queso: { hoy_kg: string; mes_kg: string; mes_merma: string; mes_lotes: number; mes_litros: string; rendimiento_mes: string | null };
  };
  alertas: Alerta[];
  financiero?: {
    ingresos_mes: { leche: number; queso: number; total: number };
    gastos_mes: {
      por_categoria: { categoria: string; total: number; cantidad: number }[];
      por_centro: { centro_costo: string; total: number; cantidad: number }[];
      total: number;
      pendientes: { total: number; cantidad: number };
    };
    compras_mes: number;
    resultado_mes: number;
    margen_productos: MargenProducto[];
    cuentas: { por_cobrar: ResumenCuentas; por_pagar: ResumenCuentas };
  };
  pendientes?: { gastos: number; lotes_queso: number; correcciones_leche: number; registros_editados: number };
};

export type ResumenCuentas = { total: number; vencido: number; cuentas: number; vencidas: number };

export type MargenProducto = {
  producto: "leche" | "queso"; nombre: string; cantidad: string; unidad: string; ventas: number;
  ingresos: number; costo: number; margen: number; margen_pct: number | null; precio_promedio: number | null; costo_unitario: number | null;
};

export type EstadoResultados = {
  desde: string; hasta: string;
  ingresos: { concepto: string; producto: string; monto: number; cantidad: string }[];
  total_ingresos: number;
  gastos_por_categoria: { categoria: string; total: number; cantidad: number }[];
  gastos_por_centro: { centro_costo: string; total: number; cantidad: number }[];
  total_gastos: number; compras_insumos: number; cantidad_compras: number; total_egresos: number;
  resultado: number; margen_pct: number | null; gastos_pendientes: { total: number; cantidad: number };
};

export type FilaFlujo = { periodo: string; cobros: number; pagos_proveedores: number; gastos: number; salidas: number; neto: number; acumulado: number };
export type FlujoCaja = { desde: string; hasta: string; agrupar: "dia" | "mes"; filas: FilaFlujo[]; totales: Omit<FilaFlujo, "periodo" | "acumulado"> };

export type FilaLote = {
  lote: string; codigo: string; fecha: string; estado: string; litros: string; kg: string; rendimiento: string | null;
  costo_leche: number; costo_insumos: number; costo_elaboracion: number; costo_total: number; costo_kg: number | null;
  kg_vendidos: string; kg_sin_vender: string; ingresos: number; precio_promedio_kg: number | null;
  costo_de_lo_vendido: number; margen_vendido: number; resultado: number; insumos_sin_precio: string[];
};
export type RentabilidadLotes = { lotes: FilaLote[]; totales: Record<string, number | string> };

export type RentabilidadProductos = {
  productos: MargenProducto[]; total: { ingresos: number; costo: number; margen: number };
  gastos_administracion: number; costo_litro_por_mes: { mes: string; gastos: number; litros: string; por_litro: number }[];
};

export type FilaAuditoria = {
  id: number | null; fecha: string; usuario: string; accion: string; accion_nombre: string; entidad: string; entidad_nombre: string;
  registro: string; ruta: string | null; motivo: string; cambios: Record<string, unknown>;
  revisado?: { por: string; fecha: string; nota: string } | null;
};

export type ConfigAlertas = {
  produccion_baja: { activa: boolean; litros_minimos: number };
  rendimiento: { activa: boolean; minimo: number; maximo: number };
  stock_bajo: { activa: boolean };
  cuentas_vencidas: { activa: boolean; dias_gracia: number };
};

export const NOMBRE_ALERTA: Record<Alerta["tipo"], string> = {
  produccion_baja: "Producción baja",
  rendimiento: "Rendimiento de queso",
  stock_bajo: "Stock bajo",
  cuenta_vencida: "Cuenta vencida",
};

/** Gs. con signo: -1.234 → "−Gs. 1.234". */
export function gsSigno(v: number): string {
  const t = `Gs. ${Math.abs(Math.round(v)).toLocaleString("es-PY")}`;
  return v < 0 ? `−${t}` : t;
}

export const pct = (v: number | null | undefined) => (v == null ? "—" : `${v.toLocaleString("es-PY", { maximumFractionDigits: 1 })} %`);

export function primerDiaMes(iso: string): string {
  return `${iso.slice(0, 7)}-01`;
}

export type MisVentas = {
  desde: string; hasta: string; total: number; cantidad_ventas: number; cobrado: number; por_cobrar: number; vencido: number;
  por_producto: { producto: "leche" | "queso"; nombre: string; unidad: string; ventas: number; cantidad: string; total: number }[];
  ventas: { id: string; codigo: string; fecha: string; cliente: string; producto: string; cantidad: string; unidad: string; total: number; saldo: number }[];
};
