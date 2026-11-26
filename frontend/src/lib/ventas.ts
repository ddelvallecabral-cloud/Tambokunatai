export type Producto = "queso" | "leche";
export type TipoCliente = "minorista" | "mayorista" | "distribuidor" | "tienda_propia";
export type CondicionPago = "contado" | "credito_7" | "credito_15" | "credito_30";
export type EstadoVenta = "pendiente" | "entregada" | "cobrada" | "anulada";
export type EstadoCuenta = "pendiente" | "parcial" | "cobrada" | "anulada";

export type Cliente = {
  id: string;
  nombre: string;
  tipo: TipoCliente;
  documento: string;
  telefono: string;
  email: string;
  direccion: string;
  condicion_pago: CondicionPago;
  activo: boolean;
  notas: string;
  saldo_pendiente: number;
  ultima_compra: string | null;
  fecha_creacion: string;
};

export type Precio = {
  id: string;
  producto: Producto;
  tipo_cliente: TipoCliente | "";
  cantidad_minima: string;
  precio_unitario: number;
  activo: boolean;
  fecha_modificacion: string;
};

export type Cobro = {
  id: string; fecha: string; monto: number; medio: string; referencia: string; usuario_nombre: string | null;
  anulado: boolean; motivo_anulacion: string; fecha_creacion: string;
};

export type Venta = {
  id: string;
  codigo: string;
  numero: number;
  fecha: string;
  cliente: string;
  cliente_nombre: string;
  cliente_tipo: TipoCliente;
  producto: Producto;
  unidad: "kg" | "l";
  cantidad: string;
  precio_unitario: number;
  precio_de_lista: number;
  total: number;
  estado_venta: EstadoVenta;
  fecha_entrega: string | null;
  observaciones: string;
  lotes: { lote: string; codigo: string; tipo: Producto; cantidad: string }[];
  cuenta: { id: string; monto: number; cobrado: number; saldo: number; vencimiento: string; estado: EstadoCuenta } | null;
  motivo_estado: string;
  creado_por_nombre: string | null;
  fecha_creacion: string;
};

export type Cuenta = {
  id: string; venta: string; venta_codigo: string; cliente: string; cliente_nombre: string;
  monto: number; cobrado: number; saldo: number; fecha_emision: string; vencimiento: string; estado: EstadoCuenta;
  cobros: Cobro[];
};

export type Cotizacion = {
  producto: Producto;
  stock_disponible: string;
  lotes_disponibles: { id: string; codigo: string; fecha: string; disponible: string }[];
  precio_unitario: number | null;
  total: number | null;
  regla?: Precio;
  error_precio?: string;
};

export type Historial = {
  cliente: Cliente;
  totales: { compras: number; total_comprado: number; kg_queso: string; litros_leche: string; saldo_pendiente: number; ultima_compra: string | null };
  lotes_entregados: { tipo: Producto; lote: string; codigo: string; fecha_lote: string; cantidad: string; unidad: string; ventas: string[] }[];
  ventas: Venta[];
};

export type ResumenCuentas = {
  fecha: string; total_por_cobrar: number; vencido: number; vendido_mes: number; cobrado_mes: number;
  por_cliente: { cliente: string; nombre: string; saldo: number; vencido: number; cuentas: number }[];
};

export const PRODUCTOS: { valor: Producto; nombre: string; unidad: string }[] = [
  { valor: "queso", nombre: "Queso Paraguay", unidad: "kg" },
  { valor: "leche", nombre: "Leche cruda", unidad: "L" },
];
export const NOMBRE_PRODUCTO: Record<Producto, string> = { queso: "Queso Paraguay", leche: "Leche cruda" };

export const TIPOS_CLIENTE: { valor: TipoCliente; nombre: string }[] = [
  { valor: "minorista", nombre: "Minorista" },
  { valor: "mayorista", nombre: "Mayorista" },
  { valor: "distribuidor", nombre: "Distribuidor" },
  { valor: "tienda_propia", nombre: "Tienda propia" },
];
export const NOMBRE_TIPO_CLIENTE = Object.fromEntries(TIPOS_CLIENTE.map((t) => [t.valor, t.nombre])) as Record<TipoCliente, string>;

export const CONDICIONES: { valor: CondicionPago; nombre: string }[] = [
  { valor: "contado", nombre: "Contado" },
  { valor: "credito_7", nombre: "Crédito 7 días" },
  { valor: "credito_15", nombre: "Crédito 15 días" },
  { valor: "credito_30", nombre: "Crédito 30 días" },
];
export const NOMBRE_CONDICION = Object.fromEntries(CONDICIONES.map((t) => [t.valor, t.nombre])) as Record<CondicionPago, string>;

export const ESTADOS_VENTA: { valor: EstadoVenta; nombre: string; color: string }[] = [
  { valor: "pendiente", nombre: "Pendiente de entrega", color: "ambar" },
  { valor: "entregada", nombre: "Entregada", color: "azul" },
  { valor: "cobrada", nombre: "Cobrada", color: "verde" },
  { valor: "anulada", nombre: "Anulada", color: "gris" },
];
export const ESTADO_VENTA = Object.fromEntries(ESTADOS_VENTA.map((e) => [e.valor, e])) as Record<EstadoVenta, (typeof ESTADOS_VENTA)[number]>;

export const ESTADO_CUENTA: Record<EstadoCuenta, { nombre: string; color: string }> = {
  pendiente: { nombre: "Pendiente", color: "ambar" },
  parcial: { nombre: "Cobrada en parte", color: "azul" },
  cobrada: { nombre: "Cobrada", color: "verde" },
  anulada: { nombre: "Anulada", color: "gris" },
};

export const MEDIOS = [
  { valor: "efectivo", nombre: "Efectivo" },
  { valor: "transferencia", nombre: "Transferencia" },
  { valor: "otro", nombre: "Otro" },
];
export const NOMBRE_MEDIO = Object.fromEntries(MEDIOS.map((m) => [m.valor, m.nombre])) as Record<string, string>;

const gs0 = new Intl.NumberFormat("es-PY", { maximumFractionDigits: 0 });
/** Guaraníes: "Gs. 486.000". */
export const gs = (v: number | string | null | undefined) => (v == null || v === "" ? "—" : `Gs. ${gs0.format(Number(v))}`);

const n2 = new Intl.NumberFormat("es-PY", { maximumFractionDigits: 2 });
export const cantidadVenta = (v: string | number, unidad: string) => `${n2.format(Number(v))} ${unidad === "l" ? "L" : unidad}`;

/** Una venta vencida: con saldo y con fecha de vencimiento ya pasada. */
export const vencida = (vencimiento: string, hoy: string) => vencimiento < hoy;
