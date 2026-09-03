import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { StatusTag } from "../components/ui";
import { useI18n } from "../i18n";
import { money, when } from "../money";
import type { Invoice, Shopper } from "../types";

type CustomerDetail = Shopper & { invoices?: Invoice[] };

export function CustomersPage() {
  const { t, locale } = useI18n();
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<Shopper[]>([]);
  const [error, setError] = useState("");

  async function load(needle = q) {
    setError("");
    const params = new URLSearchParams({ limit: "200" });
    if (needle.trim()) params.set("q", needle.trim());
    setRows(await api<Shopper[]>(`/api/shoppers?${params}`));
  }

  useEffect(() => {
    load("").catch((e) => setError(e instanceof Error ? e.message : t("couldNotAdd")));
  }, []);

  return (
    <div className="grid">
      <div>
        <h2 style={{ margin: 0 }}>{t("customerFile")}</h2>
        <p className="muted">{t("customerFileHint")}</p>
      </div>
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault();
          load().catch((e) => setError(e instanceof Error ? e.message : t("couldNotAdd")));
        }}
      >
        <input className="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("searchCustomers")} />
        <button className="btn" type="submit">
          {t("findReceipt")}
        </button>
      </form>
      {error && <div className="banner">{error}</div>}
      {rows.length === 0 && <p className="muted">{t("noCustomersYet")}</p>}
      {rows.map((c) => (
        <Link className="card row" key={c.id} to={`/customers/${c.id}`} style={{ justifyContent: "space-between" }}>
          <div>
            <b>{c.name}</b>
            <div className="muted">{c.phone}</div>
            {c.last_issued_at ? (
              <div className="muted">
                {t("lastPurchase")}: {when(c.last_issued_at, locale)}
              </div>
            ) : null}
          </div>
          <div style={{ textAlign: "right" }}>
            <div className="price">{money(c.revenue_cents || 0)}</div>
            <div className="muted">
              {c.receipt_count || 0} {t("receipts")}
              {(c.unpaid_cents || 0) > 0 ? ` · ${t("unpaid")} ${money(c.unpaid_cents || 0)}` : ""}
            </div>
          </div>
        </Link>
      ))}
    </div>
  );
}

export function CustomerDetailPage() {
  const { t, locale } = useI18n();
  const { id } = useParams();
  const [customer, setCustomer] = useState<CustomerDetail | null>(null);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const row = await api<CustomerDetail>(`/api/shoppers/${id}`);
    setCustomer(row);
    setName(row.name);
    setPhone(row.phone);
    setEmail(row.email || "");
  }

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : t("couldNotAdd")));
  }, [id]);

  async function save() {
    setError("");
    setNote("");
    setBusy(true);
    try {
      const row = await api<CustomerDetail>(`/api/shoppers/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ name, phone, email }),
      });
      setCustomer({ ...row, invoices: customer?.invoices });
      setName(row.name);
      setPhone(row.phone);
      setEmail(row.email || "");
      setNote(t("customerSaved"));
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setError(t("phoneInUse"));
      else setError(e instanceof Error ? e.message : t("updateFailed"));
    } finally {
      setBusy(false);
    }
  }

  if (error && !customer) return <div className="banner">{error}</div>;
  if (!customer) return <p className="muted">{t("loading")}</p>;

  return (
    <div className="grid">
      <div className="row">
        <Link to="/customers">{t("customerFile")}</Link>
      </div>
      <div>
        <h2 style={{ margin: 0 }}>{customer.name}</h2>
        <p className="muted">{customer.phone}</p>
      </div>
      {error && <div className="banner">{error}</div>}
      {note && <p className="muted">{note}</p>}
      <form
        className="card form-grid"
        onSubmit={(e) => {
          e.preventDefault();
          save();
        }}
      >
        <label>
          {t("name")}
          <input required value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          {t("phone")}
          <input required value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" />
        </label>
        <label>
          {t("email")}
          <input value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <div className="row">
          <button className="btn" type="submit" disabled={busy}>
            {t("save")}
          </button>
          <Link className="btn ghost" to={`/till?name=${encodeURIComponent(customer.name)}&phone=${encodeURIComponent(customer.phone)}`}>
            {t("sellToCustomer")}
          </Link>
          <Link className="btn ghost" to={`/reports?shopper_id=${customer.id}`}>
            {t("customerReport")}
          </Link>
        </div>
      </form>
      <div className="row">
        <div className="card kpi">
          {t("revenue")}
          <b>{money(customer.revenue_cents || 0)}</b>
        </div>
        <div className="card kpi">
          {t("receipts")}
          <b>{customer.receipt_count || 0}</b>
        </div>
        <div className="card kpi">
          {t("unpaid")}
          <b>{money(customer.unpaid_cents || 0)}</b>
        </div>
      </div>
      <h3>{t("receipts")}</h3>
      {(customer.invoices || []).length === 0 && <p className="muted">{t("noRows")}</p>}
      {(customer.invoices || []).map((inv) => (
        <Link className="card row" key={inv.id} to={`/receipts/${inv.id}`} style={{ justifyContent: "space-between" }}>
          <div>
            <b>{inv.number}</b> <StatusTag status={inv.status} />
            <div className="muted">{when(inv.issued_at, locale)}</div>
          </div>
          <div className="price">{money(inv.total_cents)}</div>
        </Link>
      ))}
    </div>
  );
}
