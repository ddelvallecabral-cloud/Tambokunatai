export const estiloInput =
  "w-full rounded-lg border border-stone-300 bg-white px-3 py-2.5 text-base outline-none focus:border-campo-500 focus:ring-2 focus:ring-campo-100";

export const botonPrimario =
  "rounded-xl bg-campo-700 px-4 py-3 font-semibold text-white hover:bg-campo-900 disabled:opacity-60";

export const botonSecundario =
  "rounded-xl border border-stone-300 bg-white px-4 py-3 font-medium text-stone-700 hover:bg-stone-50 disabled:opacity-60";

const COLORES: Record<string, string> = {
  verde: "bg-campo-50 text-campo-800 ring-campo-200",
  ambar: "bg-amber-50 text-amber-800 ring-amber-200",
  rojo: "bg-red-50 text-red-700 ring-red-200",
  azul: "bg-sky-50 text-sky-800 ring-sky-200",
  gris: "bg-stone-100 text-stone-600 ring-stone-200",
};

export function Insignia({ color = "gris", children }: { color?: keyof typeof COLORES | string; children: React.ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${COLORES[color] ?? COLORES.gris}`}>
      {children}
    </span>
  );
}

export function Aviso({ tipo, children }: { tipo: "error" | "ok" | "alerta"; children: React.ReactNode }) {
  const estilo = { error: "bg-red-50 text-red-700", ok: "bg-campo-50 text-campo-900", alerta: "bg-amber-50 text-amber-800" }[tipo];
  return (
    <p role={tipo === "error" ? "alert" : "status"} className={`rounded-lg px-3 py-2 text-sm ${estilo}`}>
      {children}
    </p>
  );
}

export function Tarjeta({ titulo, valor, detalle }: { titulo: string; valor: React.ReactNode; detalle?: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-4">
      <p className="text-sm text-stone-500">{titulo}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{valor}</p>
      {detalle && <p className="mt-1 text-xs text-stone-500">{detalle}</p>}
    </div>
  );
}

/** Estado vacío de un listado: qué significa que no haya nada y, si corresponde, qué hacer. */
export function Vacio({ children, accion }: { children: React.ReactNode; accion?: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-stone-300 bg-white p-8 text-center text-sm text-stone-500">
      <p>{children}</p>
      {accion && <div className="mt-3">{accion}</div>}
    </div>
  );
}
