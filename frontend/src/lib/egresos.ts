export type EstadoGasto = "pendiente" | "aprobado" | "rechazado" | "anulado";

export type Gasto = {
  id: string;
  fecha: string;
  categoria: string;
  centro_costo: string;
  monto: number;
  descripcion: string;
  proveedor: string | null;
  proveedor_nombre: string | null;
  comprobante_numero: string;
  tiene_comprobante: boolean;
  tipo_comprobante: "imagen" | "pdf" | null;
  estado: EstadoGasto;
  motivo_estado: string;
  aprobacion_automatica: boolean;
  creado_por: string;
  creado_por_nombre: string | null;
  fecha_creacion: string;
  aprobado_por_nombre: string | null;
  fecha_aprobacion: string | null;
};

export type ResumenGastos = {
  umbral_aprobacion: number;
  total_aprobado: number;
  pendientes: number;
  total_pendiente: number;
  rechazados: number;
  por_categoria: { categoria: string; total: number; cantidad: number }[];
  por_centro: { centro_costo: string; total: number }[];
};

export type Proveedor = {
  id: string; nombre: string; tipo: string; ruc: string; contacto: string; telefono: string; email: string;
  direccion: string; notas: string; activo: boolean; saldo_pendiente: number; ultima_compra: string | null;
};

export type Pago = { id: string; fecha: string; monto: number; medio: string; referencia: string; usuario_nombre: string; anulado: boolean; motivo_anulacion: string };

export type CuentaPagar = {
  id: string; compra: string; compra_codigo: string; factura: string; proveedor: string; proveedor_nombre: string;
  monto: number; pagado: number; saldo: number; fecha_emision: string; vencimiento: string;
  estado: "pendiente" | "parcial" | "pagada" | "anulada"; pagos: Pago[];
};

export type Compra = {
  id: string; codigo: string; numero: number; fecha: string; proveedor: string; proveedor_nombre: string;
  factura: string; condicion: string; total: number; observaciones: string; estado_compra: "confirmada" | "anulada";
  motivo_estado: string; tiene_comprobante: boolean; tipo_comprobante: "imagen" | "pdf" | null; creado_por_nombre: string | null; fecha_creacion: string;
  items: { insumo: string; insumo_nombre: string; insumo_codigo: string; unidad: string; cantidad: string; precio_unitario: number; subtotal: number; lote_proveedor: string }[];
  cuenta: CuentaPagar;
};

export type Pendientes = { gastos: number; lotes_queso: number; correcciones_leche: number };

export const CATEGORIAS = [
  { valor: "alimentacion", nombre: "Alimentación del ganado" },
  { valor: "sanidad", nombre: "Sanidad" },
  { valor: "servicios", nombre: "Servicios" },
  { valor: "mantenimiento", nombre: "Mantenimiento" },
  { valor: "honorarios", nombre: "Honorarios" },
  { valor: "combustible", nombre: "Combustible" },
  { valor: "otros", nombre: "Otros" },
];
export const NOMBRE_CATEGORIA = Object.fromEntries(CATEGORIAS.map((c) => [c.valor, c.nombre])) as Record<string, string>;

export const CENTROS = [
  { valor: "produccion_leche", nombre: "Producción de leche" },
  { valor: "elaboracion_queso", nombre: "Elaboración de queso" },
  { valor: "administracion", nombre: "Administración" },
];
export const NOMBRE_CENTRO = Object.fromEntries(CENTROS.map((c) => [c.valor, c.nombre])) as Record<string, string>;

export const ESTADO_GASTO: Record<EstadoGasto, { nombre: string; color: string }> = {
  pendiente: { nombre: "Pendiente de aprobación", color: "ambar" },
  aprobado: { nombre: "Aprobado", color: "verde" },
  rechazado: { nombre: "Rechazado", color: "rojo" },
  anulado: { nombre: "Anulado", color: "gris" },
};

export const TIPOS_PROVEEDOR = [
  { valor: "insumos", nombre: "Insumos" },
  { valor: "sanidad", nombre: "Sanidad" },
  { valor: "servicios", nombre: "Servicios" },
  { valor: "combustible", nombre: "Combustible" },
  { valor: "otros", nombre: "Otros" },
];
export const NOMBRE_TIPO_PROVEEDOR = Object.fromEntries(TIPOS_PROVEEDOR.map((c) => [c.valor, c.nombre])) as Record<string, string>;

export const CONDICIONES_COMPRA = [
  { valor: "contado", nombre: "Contado" },
  { valor: "credito_15", nombre: "Crédito 15 días" },
  { valor: "credito_30", nombre: "Crédito 30 días" },
  { valor: "credito_60", nombre: "Crédito 60 días" },
];
export const NOMBRE_CONDICION_COMPRA = Object.fromEntries(CONDICIONES_COMPRA.map((c) => [c.valor, c.nombre])) as Record<string, string>;

export const MEDIOS_PAGO = [
  { valor: "efectivo", nombre: "Efectivo" },
  { valor: "transferencia", nombre: "Transferencia" },
  { valor: "cheque", nombre: "Cheque" },
  { valor: "otro", nombre: "Otro" },
];

export const ESTADO_CUENTA_PAGAR: Record<CuentaPagar["estado"], { nombre: string; color: string }> = {
  pendiente: { nombre: "Pendiente", color: "ambar" },
  parcial: { nombre: "Pagada en parte", color: "azul" },
  pagada: { nombre: "Pagada", color: "verde" },
  anulada: { nombre: "Anulada", color: "gris" },
};

/**
 * Achica una foto antes de subirla (los celulares sacan fotos de 4 a 8 MB).
 * Devuelve un JPEG de hasta 1600 px de lado; un PDF o un archivo que no se pueda leer pasa tal cual.
 */
export async function prepararFoto(archivo: File, lado = 1600): Promise<File> {
  if (!archivo.type.startsWith("image/") || archivo.type === "image/heic" || archivo.type === "image/heif") return archivo;
  try {
    const bitmap = await createImageBitmap(archivo);
    const escala = Math.min(1, lado / Math.max(bitmap.width, bitmap.height));
    if (escala === 1 && archivo.size < 1_500_000) return archivo;
    const lienzo = document.createElement("canvas");
    lienzo.width = Math.round(bitmap.width * escala);
    lienzo.height = Math.round(bitmap.height * escala);
    lienzo.getContext("2d")!.drawImage(bitmap, 0, 0, lienzo.width, lienzo.height);
    const blob = await new Promise<Blob | null>((ok) => lienzo.toBlob(ok, "image/jpeg", 0.82));
    return blob ? new File([blob], archivo.name.replace(/\.\w+$/, "") + ".jpg", { type: "image/jpeg" }) : archivo;
  } catch {
    return archivo;
  }
}
