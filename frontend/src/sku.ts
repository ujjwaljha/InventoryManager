import type { Item } from "./types";

/** Match a barcode/QR payload to a catalog SKU. Typed search may be fuzzy; scans are exact. */
export function matchScannedCode(items: Item[], code: string): Item | null {
  const n = code.trim().toLowerCase();
  if (!n) return null;
  const exact = items.find((i) => i.sku.toLowerCase() === n);
  if (exact) return exact;
  const stripped = n.replace(/^0+/, "");
  if (stripped && stripped !== n) {
    const hit = items.find((i) => i.sku.toLowerCase() === stripped);
    if (hit) return hit;
  }
  return null;
}

export function shortScanCode(code: string): string {
  const n = code.trim();
  if (n.length <= 40) return n;
  return `${n.slice(0, 37)}…`;
}
