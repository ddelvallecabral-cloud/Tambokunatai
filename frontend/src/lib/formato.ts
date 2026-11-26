const n1 = new Intl.NumberFormat("es-PY", { maximumFractionDigits: 1 });
const n2 = new Intl.NumberFormat("es-PY", { maximumFractionDigits: 2 });
const n3 = new Intl.NumberFormat("es-PY", { maximumFractionDigits: 3 });

export const kg = (v: string | number | null | undefined) => (v == null || v === "" ? "—" : `${n2.format(Number(v))} kg`);
export const decimal1 = (v: string | number | null | undefined) => (v == null || v === "" ? "—" : n1.format(Number(v)));
export const rendimiento = (v: string | number | null | undefined) => (v == null ? "—" : `${n2.format(Number(v))} L/kg`);

const UNIDADES: Record<string, string> = { kg: "kg", g: "g", l: "L", ml: "ml", unidad: "u." };
export const cantidad = (v: string | number | null | undefined, unidad: string) =>
  v == null || v === "" ? "—" : `${n3.format(Number(v))} ${UNIDADES[unidad] ?? unidad}`;

export const fechaHora = (iso: string) =>
  new Date(iso).toLocaleString("es-PY", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });

/** "12,5" → "12.5"; vacío → null. */
export const aNumero = (v: string) => (v.trim() === "" ? null : v.replace(",", "."));
