export type Insumo = {
  id: string;
  codigo: string;
  nombre: string;
  categoria: string;
  unidad: string;
  stock_minimo: string;
  activo: boolean;
  stock: string;
  reservado: string;
  disponible: string;
  bajo_minimo: boolean;
};

export type Movimiento = {
  id: string;
  fecha: string;
  item: "insumo" | "leche" | "queso";
  tipo: "entrada" | "salida" | "reserva" | "liberacion";
  motivo: string;
  cantidad: string;
  unidad: string;
  insumo_nombre: string | null;
  lote_leche: string | null;
  lote_leche_codigo: string | null;
  lote_queso: string | null;
  lote_queso_codigo: string | null;
  lote_proveedor: string;
  nota: string;
  usuario_nombre: string | null;
};

export const CATEGORIAS = [
  { valor: "cuajo", nombre: "Cuajo" }, { valor: "sal", nombre: "Sal" }, { valor: "cultivo", nombre: "Cultivo" },
  { valor: "aditivo", nombre: "Aditivo" }, { valor: "envase", nombre: "Envase" }, { valor: "limpieza", nombre: "Limpieza" },
  { valor: "otro", nombre: "Otro" },
];
export const UNIDADES = [
  { valor: "kg", nombre: "kg" }, { valor: "g", nombre: "g" }, { valor: "l", nombre: "litros" },
  { valor: "ml", nombre: "ml" }, { valor: "unidad", nombre: "unidades" },
];
export const NOMBRE_TIPO: Record<string, string> = { entrada: "Entrada", salida: "Salida", reserva: "Reserva", liberacion: "Liberación" };
export const NOMBRE_MOTIVO: Record<string, string> = {
  compra: "Compra", ajuste: "Ajuste", elaboracion: "Elaboración", produccion: "Producción", correccion: "Corrección",
  cancelacion: "Cancelación", venta: "Venta", merma: "Merma",
};
