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
  bag: "karung",
};

export function unitLabel(unit: string, locale: Lang): string {
  if (locale !== "id") return unit;
  return UNIT_ID[unit] || unit;
}
