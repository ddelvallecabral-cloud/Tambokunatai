"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Milk } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const { usuario, cargando, ingresar } = useAuth();
  const router = useRouter();
  const [nombre, setNombre] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (!cargando && usuario) router.replace("/");
  }, [cargando, usuario, router]);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setEnviando(true);
    try {
      await ingresar(nombre, clave);
      router.replace("/");
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 429
          ? "Demasiados intentos. Esperá un minuto."
          : err instanceof ApiError && err.status === 401
            ? "Usuario o clave incorrectos."
            : "No se pudo conectar con el servidor.",
      );
    } finally {
      setEnviando(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-b from-campo-50 to-stone-100 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <div className="mb-3 rounded-2xl bg-campo-700 p-3 text-white">
            <Milk className="h-8 w-8" aria-hidden />
          </div>
          <h1 className="text-2xl font-semibold">Tambo Kuñatai</h1>
          <p className="text-sm text-stone-500">Sistema de gestión</p>
        </div>

        <form onSubmit={enviar} className="space-y-4 rounded-2xl border border-stone-200 bg-white p-6 shadow-sm">
          <div>
            <label htmlFor="usuario" className="mb-1 block text-sm font-medium">
              Usuario
            </label>
            <input
              id="usuario"
              autoComplete="username"
              autoCapitalize="none"
              required
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
              className="w-full rounded-lg border border-stone-300 px-3 py-2.5 text-base outline-none focus:border-campo-500 focus:ring-2 focus:ring-campo-100"
            />
          </div>
          <div>
            <label htmlFor="clave" className="mb-1 block text-sm font-medium">
              Clave
            </label>
            <input
              id="clave"
              type="password"
              autoComplete="current-password"
              required
              value={clave}
              onChange={(e) => setClave(e.target.value)}
              className="w-full rounded-lg border border-stone-300 px-3 py-2.5 text-base outline-none focus:border-campo-500 focus:ring-2 focus:ring-campo-100"
            />
          </div>
          {error && (
            <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={enviando}
            className="w-full rounded-lg bg-campo-700 py-2.5 font-medium text-white hover:bg-campo-900 disabled:opacity-60"
          >
            {enviando ? "Ingresando…" : "Ingresar"}
          </button>
        </form>
      </div>
    </main>
  );
}
