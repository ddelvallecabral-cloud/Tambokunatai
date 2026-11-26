import { Pestanas } from "@/components/Pestanas";

export default function InventarioLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-5 text-2xl font-semibold">Inventario</h1>
      <Pestanas
        etiqueta="Secciones del inventario"
        pestanas={[
          { ruta: "/inventario", nombre: "Insumos" },
          { ruta: "/inventario/leche", nombre: "Leche" },
          { ruta: "/inventario/queso", nombre: "Queso" },
          { ruta: "/inventario/movimientos", nombre: "Movimientos" },
        ]}
      />
      {children}
    </div>
  );
}
