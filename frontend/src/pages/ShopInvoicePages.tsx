import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { DocToolbar, InvoiceSheet, PageHeader, ShareReceiptButton, StatusTag, ThermalReceipt } from "../components/ui";
import { ResultList } from "../components/Finder";
import { useI18n } from "../i18n";
import { money, when } from "../money";
import type { Invoice, PurchaseOrder } from "../types";

export function ShopInvoices() {
  const { t, locale } = useI18n();
  const [rows, setRows] = useState<Invoice[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api<Invoice[]>("/api/shop/invoices"), api<PurchaseOrder[]>("/api/shop/orders")])
      .then(([invs, pos]) => {
        setRows(invs);
        setOrders(pos);
      })
      .catch((e) => setError(e.message));
  }, []);
  const needle = q.trim().toLowerCase();
  const digits = needle.replace(/\D/g, "");
  function matchesInvoice(inv: Invoice) {
    if (!needle) return true;
    const blob = [inv.number, inv.shopper_name, inv.shopper_phone, inv.salesperson_name, ...(inv.lines || []).flatMap((ln) => [ln.sku, ln.name, ln.name_id])]
      .join(" ")
      .toLowerCase();
    return blob.includes(needle) || (digits.length >= 4 && (inv.shopper_phone || "").includes(digits));
  }
  function matchesOrder(po: PurchaseOrder) {
    if (!needle) return true;
    const blob = [po.number, po.shopper_name, po.shopper_phone, po.note, po.invoice?.number, po.invoice?.salesperson_name, ...(po.lines || []).flatMap((ln) => [ln.sku, ln.name, ln.name_id])]
      .join(" ")
      .toLowerCase();
    return blob.includes(needle) || (digits.length >= 4 && (po.shopper_phone || "").includes(digits));
  }
  const shownInv = rows.filter(matchesInvoice);
  const shownPo = orders.filter(matchesOrder);
  if (error) return <div className="banner">{error}</div>;
  if (rows.length === 0 && orders.length === 0) {
    return (
      <div className="card empty-state">
        <h2>{t("noInvoices")}</h2>
        <p className="muted">{t("noInvoicesHint")}</p>
      </div>
    );
  }
  return (
    <div className="grid">
      <PageHeader title={t("yourInvoices")} />
      <div className="card filter-card">
        <input className="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("searchOrders")} />
      </div>
      {shownInv.length === 0 && <p className="empty-state">{t("noInvoices")}</p>}
      {shownInv.length > 0 ? (
        <ResultList>
          {shownInv.map((inv) => (
            <Link className="result-row" key={inv.id} to={`/shop/invoices/${inv.id}`}>
              <div>
                <b>{inv.number}</b>
                <div className="muted">{when(inv.issued_at, locale)}</div>
              </div>
              <div className="split-amount">
                <StatusTag status={inv.status} />
                <div className="price">{money(inv.total_cents, inv.currency_symbol)}</div>
              </div>
            </Link>
          ))}
        </ResultList>
      ) : null}
      <h3>{t("yourOrders")}</h3>
      {shownPo.length === 0 && <p className="empty-state">{t("noOrders")}</p>}
      {shownPo.length > 0 ? (
        <ResultList>
          {shownPo.map((po) => {
            const href = po.invoice ? `/shop/invoices/${po.invoice.id}` : "/shop/invoices";
            return (
              <Link className="result-row" key={po.id} to={href}>
                <div>
                  <b>{po.number}</b> <StatusTag status={po.status} />
                  <div className="muted">{when(po.placed_at || po.created_at, locale)}</div>
                </div>
                <div className="price">{money(po.total_cents, po.currency_symbol)}</div>
              </Link>
            );
          })}
        </ResultList>
      ) : null}
    </div>
  );
}

export function ShopInvoiceDetail() {
  const { t } = useI18n();
  const { id } = useParams();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Invoice>(`/api/shop/invoices/${id}`)
      .then(setInvoice)
      .catch((e) => setError(e.message));
  }, [id]);
  if (error) return <div className="banner">{error}</div>;
  if (!invoice) return <p className="muted">{t("loadingInvoice")}</p>;
  return (
    <div className="grid print-thermal">
      <div className="no-print">
        <PageHeader
          kicker={invoice.number}
          title={invoice.shopper_name || t("yourInvoices")}
          hint={invoice.shopper_phone}
          actions={
            <>
              <Link className="btn ghost" to="/shop/invoices">
                {t("backInvoices")}
              </Link>
              <button className="btn" onClick={() => window.print()}>
                {t("printThermal")}
              </button>
              <ShareReceiptButton invoice={invoice} />
            </>
          }
        />
      </div>
      {(invoice.status === "issued" || invoice.status === "paid") && (
        <DocToolbar>
          {invoice.status === "issued" ? (
            <>
              <button
                className="btn"
                onClick={async () => {
                  const next = await api<Invoice>(`/api/shop/invoices/${invoice.id}/mark-paid`, { method: "POST" });
                  setInvoice(next);
                }}
              >
                {t("markPaid")}
              </button>
              <button
                className="btn warn"
                onClick={async () => {
                  if (!window.confirm(t("confirmCancel"))) return;
                  const next = await api<Invoice>(`/api/shop/invoices/${invoice.id}/cancel`, { method: "POST" });
                  setInvoice(next);
                }}
              >
                {t("cancelOrder")}
              </button>
            </>
          ) : null}
          {invoice.status === "paid" ? (
            <button
              className="btn ghost"
              onClick={async () => {
                if (!window.confirm(t("confirmUnpay"))) return;
                const next = await api<Invoice>(`/api/shop/invoices/${invoice.id}/unpay`, { method: "POST" });
                setInvoice(next);
              }}
            >
              {t("markUnpaid")}
            </button>
          ) : null}
        </DocToolbar>
      )}
      <ThermalReceipt invoice={invoice} />
      <div className="no-print">
        <InvoiceSheet invoice={invoice} />
      </div>
    </div>
  );
}
