"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Pencil } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fechaHora } from "@/lib/formato";
import { FormUsuario } from "@/components/FormUsuario";
import { NOMBRE_MODULO, primerError, type Rol, type UsuarioAdmin } from "@/lib/usuarios";
import { Aviso, botonSecundario, Insignia } from "@/components/ui";

export default function DetalleUsuario() {
  const { id } = useParams<{ id: string }>();
  const { usuario: yo, puede } = useAuth();
  const [u, setU] = useState<UsuarioAdmin | null>(null);
  const [roles, setRoles] = useState<Rol[]>([]);
  const [editando, setEditando] = useState(false);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");

  const cargar = useCallback(() => api<UsuarioAdmin>(`/usuarios/${id}`).then(setU).catch(() => setError("No se encontró el usuario.")), [id]);
  useEffect(() => {
    cargar();
    api<Rol[]>("/roles").then(setRoles);
  }, [cargar]);

  async function activar(activo: boolean) {
    setError(""); setAviso("");
    try {
      setU(await api<UsuarioAdmin>(`/usuarios/${id}`, { method: "PATCH", body: JSON.stringify({ activo }) }));
      setAviso(activo ? "Usuario reactivado." : "Usuario desactivado: ya no puede entrar.");
    } catch (err) {
      setError(err instanceof ApiError ? primerError(err.datos, err.message) : "No se pudo guardar.");
    }
  }

  if (!u) return error ? <Aviso tipo="error">{error}</Aviso> : <p className="text-stone-500">Cargando…</p>;
  const gestiona = puede("usuarios.gestionar");
  const esYo = yo?.id === u.id;
  const susRoles = roles.filter((r) => u.roles.includes(r.codigo));
  const permisos = new Set(susRoles.flatMap((r) => r.permisos));
  const modulos = [...new Set([...permisos].map((p) => p.split(".")[0]))];

  return (
    <div className="space-y-5">
      <Link href="/usuarios" className="inline-flex items-center gap-1 text-sm text-stone-600 hover:text-stone-900">
        <ArrowLeft className="h-4 w-4" aria-hidden /> Usuarios
      </Link>
      {aviso && <Aviso tipo="ok">{aviso}</Aviso>}
      {error && <Aviso tipo="error">{error}</Aviso>}
      {editando ? (
        <FormUsuario usuario={u} onCancelar={() => setEditando(false)} onGuardado={(n) => { setU(n); setEditando(false); setAviso("Cambios guardados."); }} />
      ) : (
        <div className="flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-stone-200 bg-white p-5">
          <div className="space-y-1">
            <h2 className="text-xl font-semibold">{u.nombre} {esYo && <span className="text-sm font-normal text-stone-500">(vos)</span>}</h2>
            <p className="text-sm text-stone-600">Usuario: {u.usuario}{u.telefono && ` · ${u.telefono}`}{u.email && ` · ${u.email}`}</p>
            <div className="flex flex-wrap gap-1">
              {susRoles.map((r) => <Insignia key={r.codigo} color={r.codigo === "ADMIN" ? "verde" : "azul"}>{r.nombre}</Insignia>)}
              {!u.activo && <Insignia>Desactivado</Insignia>}
              {u.activo && u.debe_cambiar_clave && <Insignia color="ambar">Clave provisoria</Insignia>}
            </div>
            <p className="text-xs text-stone-500">
              Alta {fechaHora(u.fecha_alta)} · {u.ultimo_acceso ? `último ingreso ${fechaHora(u.ultimo_acceso)}` : "nunca entró"}
            </p>
          </div>
          {gestiona && (
            <div className="flex flex-wrap gap-2">
              <button onClick={() => setEditando(true)} className={`${botonSecundario} flex items-center gap-2 py-2`}>
                <Pencil className="h-4 w-4" aria-hidden /> Editar o restablecer clave
              </button>
              {!esYo && (u.activo ? (
                <button onClick={() => activar(false)} className="rounded-xl px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50">Desactivar</button>
              ) : (
                <button onClick={() => activar(true)} className="rounded-xl px-3 py-2 text-sm font-medium text-campo-700 hover:bg-campo-50">Reactivar</button>
              ))}
            </div>
          )}
        </div>
      )}
      <section className="rounded-2xl border border-stone-200 bg-white p-5">
        <h3 className="mb-1 font-semibold">Qué puede hacer</h3>
        <p className="mb-3 text-sm text-stone-500">Según su rol. Los usuarios no se borran: se desactivan, así su historial queda en la auditoría.</p>
        <div className="flex flex-wrap gap-1.5">
          {modulos.map((m) => <Insignia key={m}>{NOMBRE_MODULO[m] ?? m}</Insignia>)}
        </div>
        <Link href="/usuarios/roles" className="mt-3 inline-block text-sm text-campo-700 hover:underline">Ver el detalle de permisos por rol</Link>
      </section>
    </div>
  );
}
