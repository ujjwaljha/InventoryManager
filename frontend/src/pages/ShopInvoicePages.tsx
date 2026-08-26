import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { InvoiceSheet, StatusTag } from "../components/ui";
import { useI18n } from "../i18n";
import { money, when } from "../money";
import type { Invoice } from "../types";

export function ShopInvoices() {
  const { t, locale } = useI18n();
  const [rows, setRows] = useState<Invoice[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Invoice[]>("/api/shop/invoices")
      .then(setRows)
      .catch((e) => setError(e.message));
  }, []);
  if (error) return <div className="banner">{error}</div>;
  if (rows.length === 0) {
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
    <div className="grid">
      <div className="row no-print">
        <Link to="/shop/invoices">{t("backInvoices")}</Link>
        <button className="btn ghost" onClick={() => window.print()}>
          {t("printSave")}
        </button>
      </div>
      <InvoiceSheet invoice={invoice} />
    </div>
  );
}
