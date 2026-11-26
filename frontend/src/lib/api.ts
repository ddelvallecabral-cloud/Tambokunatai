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
  if (opciones.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const r = await fetch(`/api/v1${ruta}`, { ...opciones, headers, credentials: "same-origin" });

  if (r.status === 401 && reintentar && !ruta.startsWith("/auth/login")) {
    if (await refrescarSesion()) return api<T>(ruta, opciones, false);
  }
  if (!r.ok) {
    const datos = await r.json().catch(() => ({}));
    throw new ApiError(r.status, (datos as { detail?: string }).detail ?? "Error inesperado", datos);
  }
  return (r.status === 204 ? undefined : await r.json()) as T;
}
