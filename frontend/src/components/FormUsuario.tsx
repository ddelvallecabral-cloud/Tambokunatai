"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { primerError, type Rol, type UsuarioAdmin } from "@/lib/usuarios";
import { Aviso, botonPrimario, botonSecundario, estiloInput } from "@/components/ui";

/** Alta o edición de un usuario por el Administrador. */
export function FormUsuario({ usuario, onGuardado, onCancelar }: {
  usuario?: UsuarioAdmin; onGuardado: (u: UsuarioAdmin) => void; onCancelar: () => void;
}) {
  const [roles, setRoles] = useState<Rol[]>([]);
  const [nombreUsuario, setNombreUsuario] = useState(usuario?.usuario ?? "");
  const [nombre, setNombre] = useState(usuario?.nombre ?? "");
  const [telefono, setTelefono] = useState(usuario?.telefono ?? "");
  const [email, setEmail] = useState(usuario?.email ?? "");
  const [elegidos, setElegidos] = useState<string[]>(usuario?.roles ?? []);
  const [clave, setClave] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    api<Rol[]>("/roles").then(setRoles);
  }, []);

  const alternar = (codigo: string) => setElegidos((r) => (r.includes(codigo) ? r.filter((x) => x !== codigo) : [...r, codigo]));

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!elegidos.length) return setError("Asigná al menos un rol.");
    setOcupado(true);
    const datos: Record<string, unknown> = { nombre, telefono, email, roles: elegidos };
    if (!usuario) datos.usuario = nombreUsuario;
    if (clave) datos.clave = clave;
    try {
      onGuardado(await api<UsuarioAdmin>(usuario ? `/usuarios/${usuario.id}` : "/usuarios", {
        method: usuario ? "PATCH" : "POST", body: JSON.stringify(datos),
      }));
    } catch (err) {
      setError(err instanceof ApiError ? primerError(err.datos, err.message) : "No se pudo guardar.");
    } finally {
      setOcupado(false);
    }
  }

  return (
    <form onSubmit={guardar} className="space-y-4 rounded-2xl border border-stone-200 bg-white p-5">
      <h2 className="font-semibold">{usuario ? "Editar usuario" : "Usuario nuevo"}</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label htmlFor="u-nombre" className="mb-1 block text-sm font-medium">Nombre y apellido</label>
          <input id="u-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} className={estiloInput} required />
        </div>
        <div>
          <label htmlFor="u-usuario" className="mb-1 block text-sm font-medium">Usuario para entrar</label>
          <input id="u-usuario" value={nombreUsuario} onChange={(e) => setNombreUsuario(e.target.value.replace(/\s/g, "").toLowerCase())}
            className={estiloInput} disabled={!!usuario} required autoCapitalize="none" />
        </div>
        <div>
          <label htmlFor="u-tel" className="mb-1 block text-sm font-medium">Teléfono</label>
          <input id="u-tel" value={telefono} onChange={(e) => setTelefono(e.target.value)} inputMode="tel" className={estiloInput} />
        </div>
        <div>
          <label htmlFor="u-email" className="mb-1 block text-sm font-medium">Correo (opcional)</label>
          <input id="u-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} className={estiloInput} />
        </div>
      </div>
      <fieldset>
        <legend className="mb-2 text-sm font-medium">Rol</legend>
        <div className="grid gap-2 sm:grid-cols-3">
          {roles.map((r) => (
            <label key={r.codigo} className={`flex cursor-pointer gap-3 rounded-xl border p-3 ${elegidos.includes(r.codigo) ? "border-campo-600 bg-campo-50" : "border-stone-200"}`}>
              <input type="checkbox" checked={elegidos.includes(r.codigo)} onChange={() => alternar(r.codigo)} className="mt-1 h-4 w-4" />
              <span>
                <span className="block text-sm font-medium">{r.nombre}</span>
                <span className="block text-xs text-stone-500">{r.descripcion}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <div>
        <label htmlFor="u-clave" className="mb-1 block text-sm font-medium">
          {usuario ? "Clave nueva (solo si querés restablecerla)" : "Clave provisoria"}
        </label>
        <input id="u-clave" type="text" value={clave} onChange={(e) => setClave(e.target.value)} className={estiloInput}
          required={!usuario} minLength={8} autoComplete="off" />
        <p className="mt-1 text-xs text-stone-500">La persona la va a tener que cambiar por una propia la primera vez que entre.</p>
      </div>
      {error && <Aviso tipo="error">{error}</Aviso>}
      <div className="flex gap-2">
        <button type="submit" disabled={ocupado} className={botonPrimario}>{ocupado ? "Guardando…" : "Guardar"}</button>
        <button type="button" onClick={onCancelar} className={botonSecundario}>Cancelar</button>
      </div>
    </form>
  );
}
