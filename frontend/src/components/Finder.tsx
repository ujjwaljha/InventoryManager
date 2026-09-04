import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { StatusTag } from "./ui";
import { type MsgKey, useI18n } from "../i18n";
import { money, when } from "../money";
import type { Invoice, PurchaseOrder } from "../types";

export type PageResult<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export const PAGE_SIZE = 25;

export function FinderBar({
  q,
  onQ,
  dateFrom,
  dateTo,
  onDateFrom,
  onDateTo,
  statuses,
  status,
  onStatus,
  hint,
  onSubmit,
}: {
  q: string;
  onQ: (v: string) => void;
  dateFrom: string;
  dateTo: string;
  onDateFrom: (v: string) => void;
  onDateTo: (v: string) => void;
  statuses: string[];
  status: string;
  onStatus: (v: string) => void;
  hint?: string;
  onSubmit: () => void;
}) {
  const { t } = useI18n();
  return (
    <form
      className="card filter-card"
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      {hint ? <p className="muted" style={{ margin: 0 }}>{hint}</p> : null}
      <div className="toolbar">
        <input className="search" value={q} onChange={(e) => onQ(e.target.value)} placeholder={t("searchOrders")} />
        <button className="btn" type="submit">
          {t("findReceipt")}
        </button>
      </div>
      <div className="chips">
        <button type="button" className={`chip ${status === "" ? "on" : ""}`} onClick={() => onStatus("")}>
          {t("all")}
        </button>
        {statuses.map((s) => (
          <button key={s} type="button" className={`chip ${status === s ? "on" : ""}`} onClick={() => onStatus(s)}>
            {t(`status_${s}` as MsgKey)}
          </button>
        ))}
      </div>
      <div className="finder-dates">
        <label>
          {t("dateFrom")}
          <input type="date" value={dateFrom} onChange={(e) => onDateFrom(e.target.value)} />
        </label>
        <label>
          {t("dateTo")}
          <input type="date" value={dateTo} onChange={(e) => onDateTo(e.target.value)} />
        </label>
      </div>
    </form>
  );
}

export function Pager({
  total,
  limit,
  offset,
  onOffset,
}: {
  total: number;
  limit: number;
  offset: number;
  onOffset: (next: number) => void;
}) {
  const { t } = useI18n();
  if (total === 0) return null;
  const from = offset + 1;
  const to = Math.min(offset + limit, total);
  return (
    <div className="pager">
      <span className="muted">{t("showingRange", { from, to, total })}</span>
      <div className="row">
        <button className="btn ghost" type="button" disabled={offset <= 0} onClick={() => onOffset(Math.max(0, offset - limit))}>
          {t("previous")}
        </button>
        <button
          className="btn ghost"
          type="button"
          disabled={offset + limit >= total}
          onClick={() => onOffset(offset + limit)}
        >
          {t("next")}
        </button>
      </div>
    </div>
  );
}

function lineSummary(lines: { sku: string; name: string; name_id?: string }[], pick: (en: string, id?: string | null) => string): string {
  return lines
    .slice(0, 4)
    .map((ln) => `${ln.sku} ${pick(ln.name, ln.name_id)}`)
    .join(" · ");
}

export function ResultList({ children }: { children: ReactNode }) {
  return <div className="result-list card">{children}</div>;
}

export function InvoiceResultCard({ invoice }: { invoice: Invoice }) {
  const { t, pick, locale } = useI18n();
  return (
    <Link className="result-row" to={`/receipts/${invoice.id}`}>
      <div>
        <b>{invoice.number}</b> <StatusTag status={invoice.status} />
        <div className="muted">
          {invoice.shopper_name} · {invoice.shopper_phone} · {when(invoice.issued_at, locale)}
        </div>
        {invoice.salesperson_name ? (
          <div className="muted">
            {t("soldBy")}: {invoice.salesperson_name}
          </div>
        ) : null}
        {invoice.lines?.length ? <div className="muted">{lineSummary(invoice.lines, pick)}</div> : null}
      </div>
      <div className="price">{money(invoice.total_cents, invoice.currency_symbol)}</div>
    </Link>
  );
}

export function OrderResultCard({ order }: { order: PurchaseOrder }) {
  const { t, pick, locale } = useI18n();
  const href = order.invoice ? `/receipts/${order.invoice.id}` : `/orders`;
  const inner: ReactNode = (
    <>
      <div>
        <b>{order.number}</b> <StatusTag status={order.status} />
        {order.invoice ? (
          <>
            {" "}
            <span className="muted">{order.invoice.number}</span> <StatusTag status={order.invoice.status} />
          </>
        ) : null}
        <div className="muted">
          {order.shopper_name} · {order.shopper_phone} · {when(order.placed_at || order.created_at, locale)}
        </div>
        {order.invoice?.salesperson_name ? (
          <div className="muted">
            {t("soldBy")}: {order.invoice.salesperson_name}
          </div>
        ) : null}
        {order.lines?.length ? <div className="muted">{lineSummary(order.lines, pick)}</div> : null}
      </div>
      <div className="price">{money(order.total_cents, order.currency_symbol)}</div>
    </>
  );
  if (!order.invoice) {
    return <div className="result-row">{inner}</div>;
  }
  return (
    <Link className="result-row" to={href}>
      {inner}
    </Link>
  );
}

export function useDebounced<T>(value: T, ms = 280): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return debounced;
}

export function buildQuery(params: Record<string, string | number | undefined>): string {
  const sp = new URLSearchParams();
  for (const [key, val] of Object.entries(params)) {
    if (val === undefined || val === "") continue;
    sp.set(key, String(val));
  }
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}
