import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { InvoiceSheet, ShareReceiptButton, StatusTag, ThermalReceipt } from "../components/ui";
import { useI18n } from "../i18n";
import { money, when } from "../money";
import type { Invoice, PurchaseOrder } from "../types";

export function ShopInvoices() {
  const { t, locale } = useI18n();
  const [rows, setRows] = useState<Invoice[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api<Invoice[]>("/api/shop/invoices"), api<PurchaseOrder[]>("/api/shop/orders")])
      .then(([invs, pos]) => {
        setRows(invs);
        setOrders(pos);
      })
      .catch((e) => setError(e.message));
  }, []);
  if (error) return <div className="banner">{error}</div>;
  if (rows.length === 0 && orders.length === 0) {
    return (
      <div className="card">
        <h2>{t("noInvoices")}</h2>
        <p className="muted">{t("noInvoicesHint")}</p>
      </div>
    );
  }
  return (
    <div className="grid">
      <h2 style={{ margin: 0 }}>{t("yourInvoices")}</h2>
      {rows.length === 0 && <p className="muted">{t("noInvoices")}</p>}
      {rows.map((inv) => (
        <Link className="card row" style={{ justifyContent: "space-between" }} key={inv.id} to={`/shop/invoices/${inv.id}`}>
          <div>
            <b>{inv.number}</b>
            <div className="muted">{when(inv.issued_at, locale)}</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <StatusTag status={inv.status} />
            <div className="price">{money(inv.total_cents, inv.currency_symbol)}</div>
          </div>
        </Link>
      ))}
      <h3 style={{ margin: 0 }}>{t("yourOrders")}</h3>
      {orders.length === 0 && <p className="muted">{t("noOrders")}</p>}
      {orders.map((po) => {
        const href = po.invoice ? `/shop/invoices/${po.invoice.id}` : "/shop/invoices";
        return (
          <Link className="card row" style={{ justifyContent: "space-between" }} key={po.id} to={href}>
            <div>
              <b>{po.number}</b> <StatusTag status={po.status} />
              <div className="muted">{when(po.placed_at || po.created_at, locale)}</div>
            </div>
            <div className="price">{money(po.total_cents, po.currency_symbol)}</div>
          </Link>
        );
      })}
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
      <div className="row no-print">
        <Link to="/shop/invoices">{t("backInvoices")}</Link>
        <button className="btn ghost" onClick={() => window.print()}>
          {t("printThermal")}
        </button>
        <ShareReceiptButton invoice={invoice} />
        {invoice.status === "issued" && (
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
        )}
        {invoice.status === "paid" && (
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
        )}
      </div>
      <ThermalReceipt invoice={invoice} />
      <div className="no-print">
        <InvoiceSheet invoice={invoice} />
      </div>
    </div>
  );
}
