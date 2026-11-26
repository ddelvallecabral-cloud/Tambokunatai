// Cliente HTTP del ERP.
// - El access token vive solo en memoria (no en localStorage) y dura 15 minutos.
// - El refresh token viaja en una cookie httpOnly que el navegador manda solo a /api/v1/auth/.
// - Ante un 401, se intenta refrescar una vez y se repite la petición.

export type Modulo = { codigo: string; nombre: string; ruta: string; disponible: boolean; fase: number };
export type Perfil = {
  id: string;
  usuario: string;
  nombre: string;
  email: string;
  activo: boolean;
  debe_cambiar_clave: boolean;
  roles: { codigo: string; nombre: string }[];
  permisos: string[];
  modulos: Modulo[];
};

export class ApiError extends Error {
  constructor(public status: number, message: string, public datos?: unknown) {
    super(message);
  }
}

/** true si el servidor respondió (error real); false si no hubo conexión (status 0). */
export const respondioElServidor = (e: unknown): e is ApiError => e instanceof ApiError && e.status !== 0;

const SIN_CONEXION = "No hay conexión con el sistema. Revisá la señal o el wifi y probá de nuevo.";

/** Arma un mensaje que el usuario entiende a partir de la respuesta de error del servidor. */
export function mensajeDeError(status: number, datos: unknown): string {
  const d = (datos ?? {}) as Record<string, unknown>;
  if (typeof d.detail === "string" && d.detail) return d.detail;
  if (status === 400) {
    // Errores por campo: {"monto": ["Debe ser mayor a 0."]} → "Monto: Debe ser mayor a 0."
    for (const [campo, valor] of Object.entries(d)) {
      const msj = Array.isArray(valor) ? valor[0] : typeof valor === "string" ? valor : null;
      if (typeof msj === "string") {
        const nombre = campo === "non_field_errors" ? "" : `${campo[0].toUpperCase()}${campo.slice(1).replace(/_/g, " ")}: `;
        return `Revisá los datos. ${nombre}${msj}`;
      }
    }
    return "Revisá los datos cargados.";
  }
  if (status === 403) return "Tu rol no tiene permiso para hacer esto.";
  if (status === 404) return "No se encontró el registro. Puede que lo hayan anulado o que el enlace esté mal.";
  if (status === 413) return "El archivo es demasiado grande. Probá con una foto más chica.";
  if (status === 429) return "Demasiados intentos seguidos. Esperá un momento y probá de nuevo.";
  if (status >= 500) return "El sistema tuvo un problema. Probá de nuevo en un rato; si sigue, avisale al administrador.";
  return "No se pudo completar la acción.";
}

async function pedir(url: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch {
    throw new ApiError(0, SIN_CONEXION);
  }
}

let accessToken: string | null = null;
let refrescando: Promise<boolean> | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export async function refrescarSesion(): Promise<boolean> {
  if (!refrescando) {
    refrescando = fetch("/api/v1/auth/refresh", { method: "POST", credentials: "same-origin" })
      .then(async (r) => {
        if (!r.ok) {
          accessToken = null;
          return false;
        }
        accessToken = (await r.json()).access;
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refrescando = null;
      });
  }
  return refrescando;
}

export async function api<T = unknown>(ruta: string, opciones: RequestInit = {}, reintentar = true): Promise<T> {
  const headers = new Headers(opciones.headers);
  // Con FormData (fotos) el navegador arma el Content-Type con su separador.
  if (opciones.body && !(opciones.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const r = await pedir(`/api/v1${ruta}`, { ...opciones, headers, credentials: "same-origin" });

  if (r.status === 401 && reintentar && !ruta.startsWith("/auth/login")) {
    if (await refrescarSesion()) return api<T>(ruta, opciones, false);
  }
  if (!r.ok) {
    const datos = await r.json().catch(() => ({}));
    throw new ApiError(r.status, mensajeDeError(r.status, datos), datos);
  }
  return (r.status === 204 ? undefined : await r.json()) as T;
}

/** Baja un archivo protegido (p. ej. la foto de un comprobante) y devuelve una URL local para mostrarlo. */
export async function archivoProtegido(ruta: string, reintentar = true): Promise<string> {
  const headers = new Headers();
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const r = await pedir(`/api/v1${ruta}`, { headers, credentials: "same-origin" });
  if (r.status === 401 && reintentar && (await refrescarSesion())) return archivoProtegido(ruta, false);
  if (!r.ok) throw new ApiError(r.status, "No se pudo abrir el comprobante.");
  return URL.createObjectURL(await r.blob());
}

/** Baja un archivo generado por el servidor (PDF, Excel) y lo guarda con su nombre. */
export async function descargar(ruta: string, reintentar = true): Promise<void> {
  const headers = new Headers();
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  const r = await pedir(`/api/v1${ruta}`, { headers, credentials: "same-origin" });
  if (r.status === 401 && reintentar && (await refrescarSesion())) return descargar(ruta, false);
  if (!r.ok) throw new ApiError(r.status, r.status === 403 ? "No tenés permiso para este reporte." : "No se pudo generar el archivo.");
  const nombre = /filename="([^"]+)"/.exec(r.headers.get("Content-Disposition") ?? "")?.[1] ?? "reporte";
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
