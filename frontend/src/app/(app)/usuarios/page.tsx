"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Search, UserPlus } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fechaHora } from "@/lib/formato";
import { FormUsuario } from "@/components/FormUsuario";
import type { Rol, UsuarioAdmin } from "@/lib/usuarios";
import { Aviso, botonPrimario, estiloInput, Insignia } from "@/components/ui";

export default function Usuarios() {
  const { puede } = useAuth();
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[] | null>(null);
  const [roles, setRoles] = useState<Rol[]>([]);
  const [buscar, setBuscar] = useState("");
  const [rol, setRol] = useState("");
  const [nuevo, setNuevo] = useState(false);
  const [aviso, setAviso] = useState("");
  const [version, setVersion] = useState(0);

  useEffect(() => {
    api<Rol[]>("/roles").then(setRoles);
  }, []);
  useEffect(() => {
    const t = setTimeout(() => {
      const q = new URLSearchParams({ page_size: "200", buscar: buscar.trim(), rol });
      api<{ results: UsuarioAdmin[] }>(`/usuarios?${q}`).then((p) => setUsuarios(p.results));
    }, 200);
    return () => clearTimeout(t);
  }, [buscar, rol, version]);

  const nombreRol = (c: string) => roles.find((r) => r.codigo === c)?.nombre ?? c;

  return (
    <div className="space-y-5">
      {puede("usuarios.gestionar") && (nuevo ? (
        <FormUsuario onCancelar={() => setNuevo(false)} onGuardado={(u) => {
          setNuevo(false); setVersion((v) => v + 1);
          setAviso(`Usuario ${u.usuario} creado. Pasale la clave provisoria: la va a cambiar al entrar.`);
        }} />
      ) : (
        <button onClick={() => { setNuevo(true); setAviso(""); }} className={`${botonPrimario} flex items-center gap-2`}>
          <UserPlus className="h-5 w-5" aria-hidden /> Usuario nuevo
        </button>
      ))}
      {aviso && <Aviso tipo="ok">{aviso}</Aviso>}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div className="relative col-span-2">
          <Search className="pointer-events-none absolute left-3 top-3 h-5 w-5 text-stone-400" aria-hidden />
          <input aria-label="Buscar usuario" value={buscar} onChange={(e) => setBuscar(e.target.value)} placeholder="Nombre o usuario" className={`${estiloInput} pl-10`} />
        </div>
        <select aria-label="Rol" value={rol} onChange={(e) => setRol(e.target.value)} className={`${estiloInput} col-span-2 sm:col-span-1`}>
          <option value="">Todos los roles</option>
          {roles.map((r) => <option key={r.codigo} value={r.codigo}>{r.nombre}</option>)}
        </select>
      </div>

      {!usuarios ? <p className="text-stone-500">Cargando…</p> : (
        <ul className="divide-y divide-stone-100 overflow-hidden rounded-2xl border border-stone-200 bg-white">
          {usuarios.map((u) => (
            <li key={u.id}>
              <Link href={`/usuarios/${u.id}`} className={`flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 hover:bg-stone-50 ${u.activo ? "" : "opacity-60"}`}>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{u.nombre}</span>
                  <span className="block text-xs text-stone-500">{u.usuario}{u.telefono && ` · ${u.telefono}`}</span>
                </span>
                <span className="flex flex-wrap gap-1">
                  {u.roles.map((r) => <Insignia key={r} color={r === "ADMIN" ? "verde" : "azul"}>{nombreRol(r)}</Insignia>)}
                  {!u.activo && <Insignia>Desactivado</Insignia>}
                  {u.activo && u.debe_cambiar_clave && <Insignia color="ambar">Clave provisoria</Insignia>}
                </span>
                <span className="w-36 text-right text-xs text-stone-500">{u.ultimo_acceso ? `Entró ${fechaHora(u.ultimo_acceso)}` : "Nunca entró"}</span>
              </Link>
            </li>
          ))}
          {usuarios.length === 0 && <li className="p-6 text-center text-stone-500">No hay usuarios con esos filtros.</li>}
        </ul>
      )}
    </div>
  );
}
