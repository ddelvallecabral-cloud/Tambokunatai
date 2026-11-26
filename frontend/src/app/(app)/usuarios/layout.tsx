import { Pestanas } from "@/components/Pestanas";

export default function UsuariosLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-5 text-2xl font-semibold">Usuarios y roles</h1>
      <Pestanas etiqueta="Secciones de usuarios" pestanas={[{ ruta: "/usuarios", nombre: "Usuarios" }, { ruta: "/usuarios/roles", nombre: "Roles y permisos" }]} />
      {children}
    </div>
  );
}
