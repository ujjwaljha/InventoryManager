import type { MsgKey } from "./i18n";
import { formatQty, money, unitLabel, whenFull, type Lang } from "./money";
import type { Invoice } from "./types";

type TFn = (key: MsgKey, vars?: Record<string, string | number>) => string;
type PickFn = (en: string, id?: string | null) => string;

const DASH = "--------------------------------";

export function receiptPlainText(
  invoice: Invoice,
  t: TFn,
  pick: PickFn,
  locale: Lang,
): string {
  const lines: string[] = [invoice.shop_name];
  if (invoice.shop_address) lines.push(invoice.shop_address);
  if (invoice.shop_phone) lines.push(invoice.shop_phone);
  lines.push(DASH);
  lines.push(`${t("receipt")} ${invoice.number}`);
  lines.push(`${t("dateTime")}: ${whenFull(invoice.issued_at, locale)}`);
  if (invoice.due_date) lines.push(`${t("dueDate")}: ${invoice.due_date}`);
  if (invoice.salesperson_name) lines.push(`${t("soldBy")}: ${invoice.salesperson_name}`);
  lines.push(`${t("customer")}: ${invoice.shopper_name}`);
  lines.push(`${t("phone")}: ${invoice.shopper_phone}`);
  lines.push(t(`status_${invoice.status}` as MsgKey));
  lines.push(DASH);
  for (const ln of invoice.lines) {
    lines.push(pick(ln.name, ln.name_id));
    lines.push(
      `${formatQty(ln.quantity)} ${unitLabel(ln.unit || "ea", locale)} × ${money(ln.unit_price_cents, invoice.currency_symbol)}  ${money(ln.line_total_cents, invoice.currency_symbol)}`,
    );
  }
  lines.push(DASH);
  lines.push(`${t("subtotal")}  ${money(invoice.subtotal_cents, invoice.currency_symbol)}`);
  if (invoice.tax_cents > 0) {
    lines.push(`${t("tax")} ${(invoice.tax_bps / 100).toFixed(2)}%  ${money(invoice.tax_cents, invoice.currency_symbol)}`);
  }
  lines.push(`${t("total")}  ${money(invoice.total_cents, invoice.currency_symbol)}`);
  lines.push(DASH);
  lines.push(t("thankYou"));
  return lines.join("\n");
}

export type ShareOutcome = "shared" | "copied" | "aborted";

export async function shareReceipt(title: string, text: string, filename: string): Promise<ShareOutcome> {
  const file = new File([`\uFEFF${text}`], filename, { type: "text/plain;charset=utf-8" });
  const payload: ShareData = { title, text };
  if (typeof navigator.share === "function") {
    try {
      const withFile = { ...payload, files: [file] };
      if (navigator.canShare?.(withFile)) {
        await navigator.share(withFile);
        return "shared";
      }
      if (!navigator.canShare || navigator.canShare(payload)) {
        await navigator.share(payload);
        return "shared";
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return "aborted";
    }
  }
  await navigator.clipboard.writeText(text);
  return "copied";
}
