import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { ItemPicker, StatusTag, ThermalReceipt } from "../components/ui";
import { useI18n } from "../i18n";
import { money, when } from "../money";
import type { DamageNote, Invoice, Item, SupplierReturn } from "../types";

type PickLine = { item: Item; quantity: number };

export function ReceiptsPage() {
  const { t, locale } = useI18n();
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<Invoice[]>([]);
  const [error, setError] = useState("");

  async function search(needle = q) {
    setError("");
    try {
      const path = needle.trim() ? `/api/receipts?q=${encodeURIComponent(needle.trim())}` : "/api/invoices";
      setRows(await api<Invoice[]>(path));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("couldNotAdd"));
    }
  }

  useEffect(() => {
    search("");
  }, []);

  return (
    <div className="grid">
      <h2 style={{ margin: 0 }}>{t("lookUpReceipt")}</h2>
      <p className="muted">{t("lookUpHint")}</p>
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault();
          search();
        }}
      >
        <input className="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("searchReceipt")} />
        <button className="btn" type="submit">
          {t("findReceipt")}
        </button>
      </form>
      {error && <div className="banner">{error}</div>}
      {rows.length === 0 && <p className="muted">{t("noRows")}</p>}
      {rows.map((inv) => (
        <Link className="card row" key={inv.id} to={`/receipts/${inv.id}`} style={{ justifyContent: "space-between" }}>
          <div>
            <b>{inv.number}</b> <StatusTag status={inv.status} />
            <div className="muted">
              {inv.shopper_name} · {inv.shopper_phone} · {when(inv.issued_at, locale)}
            </div>
            {inv.salesperson_name ? <div className="muted">{t("soldBy")}: {inv.salesperson_name}</div> : null}
          </div>
          <div className="price">{money(inv.total_cents, inv.currency_symbol)}</div>
        </Link>
      ))}
    </div>
  );
}

export function ReceiptDetail() {
  const { t } = useI18n();
  const { id } = useParams();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Invoice>(`/api/invoices/${id}`)
      .then(setInvoice)
      .catch((e) => setError(e.message));
  }, [id]);
  if (error) return <div className="banner">{error}</div>;
  if (!invoice) return <p className="muted">{t("loading")}</p>;
  return (
    <div className="grid print-thermal">
      <div className="row no-print">
        <Link to="/receipts">{t("backInvoices")}</Link>
        <button className="btn" onClick={() => window.print()}>
          {t("printThermal")}
        </button>
      </div>
      <p className="muted no-print">{t("thermalHint")}</p>
      <ThermalReceipt invoice={invoice} />
    </div>
  );
}

export function DamagePage() {
  const { t, pick, locale } = useI18n();
  const [reason, setReason] = useState("");
  const [lines, setLines] = useState<PickLine[]>([]);
  const [rows, setRows] = useState<DamageNote[]>([]);
  const [error, setError] = useState("");

  async function load() {
    setRows(await api<DamageNote[]>("/api/damage"));
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);

  async function submit() {
    setError("");
    try {
      await api("/api/damage", {
        method: "POST",
        body: JSON.stringify({
          reason,
          lines: lines.map((ln) => ({ item_id: ln.item.id, quantity: ln.quantity })),
        }),
      });
      setReason("");
      setLines([]);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("movementFailed"));
    }
  }

  return (
    <div className="grid">
      <h2 style={{ margin: 0 }}>{t("recordDamage")}</h2>
      {error && <div className="banner">{error}</div>}
      <div className="card form-grid">
        <label>
          {t("reason")}
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("damageReason")} />
        </label>
        <ItemPicker onAdd={(item, qty) => setLines((c) => [...c, { item, quantity: qty }])} />
        {lines.map((ln, idx) => (
          <div className="row" key={`${ln.item.id}-${idx}`} style={{ justifyContent: "space-between" }}>
            <span>
              {pick(ln.item.name, ln.item.name_id)} × {ln.quantity}
            </span>
            <button type="button" className="btn ghost" onClick={() => setLines((c) => c.filter((_, i) => i !== idx))}>
              ×
            </button>
          </div>
        ))}
        <button className="btn warn" type="button" disabled={!reason || !lines.length} onClick={submit}>
          {t("saveDamage")}
        </button>
      </div>
      {rows.map((row) => (
        <section className="card" key={row.id}>
          <b>{row.number}</b>
          <div className="muted">
            {row.reason} · {when(row.created_at, locale)}
          </div>
          <div>
            {t("cogs")} {money(row.cogs_cents)}
          </div>
          {row.lines.map((ln) => (
            <div key={ln.id} className="muted">
              {pick(ln.name, ln.name_id)} × {ln.quantity}
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}

export function ReturnsPage() {
  const { t, pick, locale } = useI18n();
  const [reason, setReason] = useState("");
  const [supplier, setSupplier] = useState("");
  const [phone, setPhone] = useState("");
  const [lines, setLines] = useState<PickLine[]>([]);
  const [rows, setRows] = useState<SupplierReturn[]>([]);
  const [error, setError] = useState("");

  async function load() {
    setRows(await api<SupplierReturn[]>("/api/supplier-returns"));
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);

  async function submit() {
    setError("");
    try {
      await api("/api/supplier-returns", {
        method: "POST",
        body: JSON.stringify({
          reason,
          supplier_name: supplier,
          supplier_phone: phone,
          lines: lines.map((ln) => ({ item_id: ln.item.id, quantity: ln.quantity })),
        }),
      });
      setReason("");
      setSupplier("");
      setPhone("");
      setLines([]);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("movementFailed"));
    }
  }

  return (
    <div className="grid">
      <h2 style={{ margin: 0 }}>{t("returnToSupplier")}</h2>
      {error && <div className="banner">{error}</div>}
      <div className="card form-grid">
        <label>
          {t("supplierName")}
          <input value={supplier} onChange={(e) => setSupplier(e.target.value)} />
        </label>
        <label>
          {t("phone")}
          <input value={phone} onChange={(e) => setPhone(e.target.value)} />
        </label>
        <label>
          {t("reason")}
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("returnReason")} />
        </label>
        <ItemPicker onAdd={(item, qty) => setLines((c) => [...c, { item, quantity: qty }])} />
        {lines.map((ln, idx) => (
          <div className="row" key={`${ln.item.id}-${idx}`} style={{ justifyContent: "space-between" }}>
            <span>
              {pick(ln.item.name, ln.item.name_id)} × {ln.quantity}
            </span>
            <button type="button" className="btn ghost" onClick={() => setLines((c) => c.filter((_, i) => i !== idx))}>
              ×
            </button>
          </div>
        ))}
        <button className="btn" type="button" disabled={!reason || !lines.length} onClick={submit}>
          {t("submitReturn")}
        </button>
      </div>
      {rows.map((row) => (
        <section className="card" key={row.id}>
          <b>{row.number}</b>
          <div className="muted">
            {row.supplier_name} · {row.reason} · {when(row.created_at, locale)}
          </div>
          <div>
            {t("cogs")} {money(row.cogs_cents)}
          </div>
          {row.lines.map((ln) => (
            <div key={ln.id} className="muted">
              {pick(ln.name, ln.name_id)} × {ln.quantity}
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}

export function MorePage() {
  const { t } = useI18n();
  const links = [
    ["/", t("home")],
    ["/restock", t("restock")],
    ["/damage", t("damage")],
    ["/returns", t("returns")],
    ["/orders", t("orders")],
    ["/invoices", t("invoices")],
    ["/settings", t("settings")],
    ["/shop", t("openShop")],
  ] as const;
  return (
    <div className="grid">
      <h2 style={{ margin: 0 }}>{t("moreOffice")}</h2>
      {links.map(([to, label]) => (
        <Link className="card" key={to} to={to}>
          {label}
        </Link>
      ))}
    </div>
  );
}
