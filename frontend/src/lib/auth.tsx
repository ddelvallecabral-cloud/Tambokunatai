"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, refrescarSesion, setAccessToken, type Perfil } from "./api";

type EstadoAuth = {
  usuario: Perfil | null;
  cargando: boolean;
  ingresar: (usuario: string, clave: string) => Promise<void>;
  salir: () => Promise<void>;
  puede: (permiso: string) => boolean;
  recargar: () => Promise<void>;
};

const AuthContext = createContext<EstadoAuth | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [usuario, setUsuario] = useState<Perfil | null>(null);
  const [cargando, setCargando] = useState(true);

  // Al abrir la app, intenta recuperar la sesión con la cookie de refresh.
  useEffect(() => {
    (async () => {
      try {
        if (await refrescarSesion()) setUsuario(await api<Perfil>("/auth/me"));
      } finally {
        setCargando(false);
      }
    })();
  }, []);

  const ingresar = useCallback(async (nombre: string, clave: string) => {
    const r = await api<{ access: string; usuario: Perfil }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ usuario: nombre, clave }),
    });
    setAccessToken(r.access);
    setUsuario(r.usuario);
  }, []);

  const salir = useCallback(async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    setAccessToken(null);
    setUsuario(null);
  }, []);

  const recargar = useCallback(async () => {
    setUsuario(await api<Perfil>("/auth/me"));
  }, []);

  const puede = useCallback((permiso: string) => !!usuario?.permisos.includes(permiso), [usuario]);

  return <AuthContext.Provider value={{ usuario, cargando, ingresar, salir, puede, recargar }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
