"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { primerError } from "@/lib/usuarios";
import { Aviso, botonPrimario, estiloInput } from "@/components/ui";

export default function MiCuenta() {
  const { usuario, recargar } = useAuth();
  const router = useRouter();
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [repetida, setRepetida] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  if (!usuario) return null;
  const obligado = usuario.debe_cambiar_clave;

  async function cambiar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setOk(false);
    if (nueva !== repetida) return setError("Las dos claves nuevas no coinciden.");
    setOcupado(true);
    try {
      await api("/auth/cambiar-clave", { method: "POST", body: JSON.stringify({ clave_actual: actual, clave_nueva: nueva }) });
      setActual(""); setNueva(""); setRepetida("");
      setOk(true);
      await recargar();
      if (obligado) router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? primerError(err.datos, err.message) : "No se pudo cambiar la clave.");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-5">
      <h1 className="text-2xl font-semibold">Mi cuenta</h1>
      <div className="rounded-2xl border border-stone-200 bg-white p-5 text-sm">
        <p className="font-medium">{usuario.nombre}</p>
        <p className="text-stone-500">Usuario: {usuario.usuario} · {usuario.roles.map((r) => r.nombre).join(", ")}</p>
      </div>
      {obligado && <Aviso tipo="alerta">El Administrador te dio una clave provisoria. Elegí una clave propia para seguir.</Aviso>}
      <form onSubmit={cambiar} className="space-y-3 rounded-2xl border border-stone-200 bg-white p-5">
        <h2 className="font-semibold">Cambiar clave</h2>
        <div>
          <label htmlFor="actual" className="mb-1 block text-sm font-medium">Clave actual</label>
          <input id="actual" type="password" autoComplete="current-password" value={actual} onChange={(e) => setActual(e.target.value)} className={estiloInput} required />
        </div>
        <div>
          <label htmlFor="nueva" className="mb-1 block text-sm font-medium">Clave nueva</label>
          <input id="nueva" type="password" autoComplete="new-password" value={nueva} onChange={(e) => setNueva(e.target.value)} className={estiloInput} minLength={8} required />
          <p className="mt-1 text-xs text-stone-500">Al menos 8 caracteres, que no sea solo números ni muy común.</p>
        </div>
        <div>
          <label htmlFor="repetida" className="mb-1 block text-sm font-medium">Repetí la clave nueva</label>
          <input id="repetida" type="password" autoComplete="new-password" value={repetida} onChange={(e) => setRepetida(e.target.value)} className={estiloInput} required />
        </div>
        {error && <Aviso tipo="error">{error}</Aviso>}
        {ok && <Aviso tipo="ok">Listo, la clave quedó cambiada.</Aviso>}
        <button type="submit" disabled={ocupado} className={`${botonPrimario} w-full`}>{ocupado ? "Guardando…" : "Cambiar clave"}</button>
      </form>
    </div>
  );
}
