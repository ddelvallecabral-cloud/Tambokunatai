"use client";

import { Fragment, useEffect, useState } from "react";
import { Check, Minus } from "lucide-react";
import { api } from "@/lib/api";
import { NOMBRE_MODULO, type Permiso, type Rol } from "@/lib/usuarios";

export default function Roles() {
  const [roles, setRoles] = useState<Rol[] | null>(null);
  const [permisos, setPermisos] = useState<Permiso[]>([]);

  useEffect(() => {
    api<Rol[]>("/roles").then((r) => setRoles([...r].sort((a, b) => (a.codigo === "ADMIN" ? -1 : b.codigo === "ADMIN" ? 1 : a.nombre.localeCompare(b.nombre)))));
    api<Permiso[]>("/permisos").then(setPermisos);
  }, []);

  if (!roles) return <p className="text-stone-500">Cargando…</p>;
  const modulos = [...new Set(permisos.map((p) => p.modulo))];

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-3">
        {roles.map((r) => (
          <div key={r.codigo} className="rounded-2xl border border-stone-200 bg-white p-4">
            <p className="font-semibold">{r.nombre}</p>
            <p className="text-sm text-stone-500">{r.descripcion}</p>
            <p className="mt-1 text-xs text-stone-500">{r.permisos.length} permisos</p>
          </div>
        ))}
      </div>
      <div className="overflow-x-auto rounded-2xl border border-stone-200 bg-white">
        <table className="w-full min-w-[560px] text-sm">
          <thead className="sticky top-0 bg-stone-50 text-left text-xs text-stone-500">
            <tr>
              <th className="px-4 py-2">Permiso</th>
              {roles.map((r) => <th key={r.codigo} className="w-24 px-2 py-2 text-center">{r.nombre}</th>)}
            </tr>
          </thead>
          <tbody>
            {modulos.map((m) => (
              <Fragment key={m}>
                <tr className="bg-stone-50/60"><th colSpan={roles.length + 1} className="px-4 pb-1 pt-3 text-left text-xs font-semibold uppercase tracking-wide text-stone-500">{NOMBRE_MODULO[m] ?? m}</th></tr>
                {permisos.filter((p) => p.modulo === m).map((p) => (
                  <tr key={p.codigo} className="border-t border-stone-100">
                    <td className="px-4 py-1.5">{p.descripcion || p.codigo}</td>
                    {roles.map((r) => (
                      <td key={r.codigo} className="px-2 py-1.5 text-center">
                        {r.permisos.includes(p.codigo)
                          ? <Check className="mx-auto h-4 w-4 text-campo-700" aria-label="Sí" />
                          : <Minus className="mx-auto h-4 w-4 text-stone-300" aria-label="No" />}
                      </td>
                    ))}
                  </tr>
                ))}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-stone-500">Los roles son fijos por ahora. Si necesitás uno nuevo (por ejemplo, un encargado que apruebe lotes de queso), se agrega en el sistema.</p>
    </div>
  );
}
