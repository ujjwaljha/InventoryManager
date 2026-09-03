export type Lang = "en" | "id";

export function money(cents: number, _symbol = "Rp"): string {
  const rupiah = Math.round(Number(cents) / 100);
  const formatted = new Intl.NumberFormat("id-ID", {
    maximumFractionDigits: 0,
    minimumFractionDigits: 0,
  }).format(rupiah);
  return `Rp\u00a0${formatted}`;
}

export function rupiahFromCents(cents: number): string {
  return String(Math.round(Number(cents) / 100));
}

export function centsFromRupiah(raw: string): number {
  const n = Number(String(raw).replace(/[^\d-]/g, ""));
  if (!Number.isFinite(n)) return 0;
  return Math.round(n * 100);
}

export function when(iso: string | null | undefined, locale: Lang = "id"): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.replace("T", " ");
  const tag = locale === "id" ? "id-ID" : "en-GB";
  return d.toLocaleString(tag, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const UNIT_ID: Record<string, string> = {
  kg: "kg",
  L: "L",
  l: "L",
  btl: "btl",
  pack: "bks",
  ctn: "pkt",
  ea: "pcs",
  pcs: "pcs",
  bag: "sak",
  stick: "btg",
  pail: "kaleng",
  m: "m",
  m3: "m³",
  sheet: "lembar",
  box: "dus",
  set: "set",
  roll: "rol",
  m2: "m²",
};

const FRACTION_UNITS = new Set(["m3", "m", "m2", "kg", "L", "l"]);

export function qtyStep(unit: string): number {
  if (unit === "m3" || unit === "m2") return 0.5;
  if (unit === "m" || unit === "kg" || unit === "L" || unit === "l") return 1;
  return 1;
}

export function nudgeQty(current: number, unit: string, dir: 1 | -1): number {
  return Math.round((Number(current) + dir * qtyStep(unit)) * 1000) / 1000;
}

export function formatQty(n: number): string {
  const v = Number(n);
  if (!Number.isFinite(v)) return "0";
  const rounded = Math.round(v * 1000) / 1000;
  if (Math.abs(rounded - Math.round(rounded)) < 1e-9) return String(Math.round(rounded));
  return String(rounded);
}

export function qtyMoney(qty: number, unitCents: number): number {
  return Math.round((Math.round(Number(qty) * 1000) / 1000) * Number(unitCents));
}

export function allowsFraction(unit: string): boolean {
  return FRACTION_UNITS.has(unit);
}

export function whenFull(iso: string | null | undefined, locale: Lang = "id"): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.replace("T", " ");
  const tag = locale === "id" ? "id-ID" : "en-GB";
  return d.toLocaleString(tag, {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function marginPct(bps: number): string {
  return `${(Number(bps) / 100).toFixed(1)}%`;
}

export function todayInput(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function addDays(iso: string, days: number): string {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + days);
  return isoDate(d);
}

export function weekStartMonday(iso: string): string {
  const d = new Date(`${iso}T12:00:00`);
  const dow = d.getDay();
  const back = dow === 0 ? 6 : dow - 1;
  return addDays(iso, -back);
}

export function monthStart(iso: string): string {
  return `${iso.slice(0, 8)}01`;
}

export function unitLabel(unit: string, locale: Lang): string {
  if (locale !== "id") return unit;
  return UNIT_ID[unit] || unit;
}
