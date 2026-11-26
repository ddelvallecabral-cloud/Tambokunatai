export type UsuarioAdmin = {
  id: string;
  usuario: string;
  nombre: string;
  email: string;
  telefono: string;
  activo: boolean;
  debe_cambiar_clave: boolean;
  roles: string[];
  ultimo_acceso: string | null;
  fecha_alta: string;
};

export type Rol = { id: number; codigo: string; nombre: string; descripcion: string; es_sistema: boolean; permisos: string[] };
export type Permiso = { codigo: string; modulo: string; descripcion: string };

export const NOMBRE_MODULO: Record<string, string> = {
  administracion: "Administración", auditoria: "Auditoría", rodeo: "Rodeo", leche: "Leche", queso: "Queso",
  inventario: "Inventario", ventas: "Ventas y cobros", compras: "Compras", gastos: "Gastos", reportes: "Reportes",
  registros: "Registros",
};

/** Primer mensaje de error de un 400 de DRF ({campo: [mensaje]}). */
export function primerError(datos: unknown, porDefecto: string): string {
  if (datos && typeof datos === "object") {
    for (const v of Object.values(datos as Record<string, unknown>)) {
      if (Array.isArray(v) && typeof v[0] === "string") return v[0];
      if (typeof v === "string") return v;
    }
  }
  return porDefecto;
}
