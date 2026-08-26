import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { InvoiceSheet } from "../components/ui";
import { type MsgKey, useI18n } from "../i18n";
import { centsFromRupiah, rupiahFromCents, unitLabel, when } from "../money";
import type { Invoice, Item, Movement, Settings } from "../types";

export function OpItemDetail() {
  const { t, pick, locale } = useI18n();
  const { id } = useParams();
  const [item, setItem] = useState<Item | null>(null);
  const [moves, setMoves] = useState<Movement[]>([]);
  const [qty, setQty] = useState("1");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const nav = useNavigate();

  async function load() {
    const it = await api<Item>(`/api/items/${id}`);
    setItem(it);
    setMoves(await api<Movement[]>(`/api/items/${id}/movements`));
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [id]);

  async function move(kind: string) {
    setError("");
    try {
      await api(`/api/items/${id}/movements`, {
        method: "POST",
        body: JSON.stringify({ kind, quantity: Number(qty), reason }),
      });
      setReason("");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("movementFailed"));
    }
  }

  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!item) return;
    const fd = new FormData(e.currentTarget);
    await api(`/api/items/${id}`, {
      method: "PATCH",
      body: JSON.stringify({
        name: fd.get("name"),
        name_id: fd.get("name_id"),
        sku: fd.get("sku"),
        description: fd.get("description"),
        description_id: fd.get("description_id"),
        unit_price_cents: centsFromRupiah(String(fd.get("price") || "0")),
        unit_cost_cents: centsFromRupiah(String(fd.get("cost") || "0")),
        reorder_point: Number(fd.get("reorder")),
        notes: fd.get("notes"),
      }),
    });
    await load();
  }

  if (!item) return <p className="muted">{t("loading")}</p>;

  return (
    <div className="grid">
      <Link to="/items">{t("backItems")}</Link>
      {error && <div className="banner">{error}</div>}
      <div className="card">
        <div className="sku">{item.sku}</div>
        <h2 style={{ margin: "4px 0" }}>{pick(item.name, item.name_id)}</h2>
        <p className="price" style={{ margin: 0 }}>
          {t("onHand", { qty: item.quantity, unit: unitLabel(item.unit, locale) })}
        </p>
        {item.low_stock && <div className="stock low">{t("belowReorder", { point: item.reorder_point })}</div>}
      </div>
      <form className="card form-grid" onSubmit={save}>
        <h3 style={{ margin: 0 }}>{t("details")}</h3>
        <label>
          {t("nameEn")}
          <input name="name" defaultValue={item.name} />
        </label>
        <label>
          {t("nameId")}
          <input name="name_id" defaultValue={item.name_id || item.name} />
        </label>
        <label>
          {t("sku")}
          <input name="sku" defaultValue={item.sku} />
        </label>
        <label>
          {t("descriptionEn")}
          <textarea name="description" defaultValue={item.description} />
        </label>
        <label>
          {t("descriptionId")}
          <textarea name="description_id" defaultValue={item.description_id || item.description} />
        </label>
        <label>
          {t("sellPrice")}
          <input name="price" type="number" step="1" defaultValue={rupiahFromCents(item.unit_price_cents)} />
        </label>
        <label>
          {t("cost")}
          <input name="cost" type="number" step="1" defaultValue={rupiahFromCents(item.unit_cost_cents)} />
        </label>
        <label>
          {t("reorderPoint")}
          <input name="reorder" type="number" defaultValue={item.reorder_point} />
        </label>
        <label>
          {t("notes")}
          <input name="notes" defaultValue={item.notes} />
        </label>
        <button className="btn" type="submit">
          {t("save")}
        </button>
      </form>
      <div className="card form-grid">
        <h3 style={{ margin: 0 }}>{t("stock")}</h3>
        <p className="muted">{t("stockHint")}</p>
        <label>
          {t("quantity")}
          <input value={qty} onChange={(e) => setQty(e.target.value)} inputMode="numeric" />
        </label>
        <label>
          {t("reason")}
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t("reasonPlaceholder")} />
        </label>
        <div className="row">
          <button className="btn" type="button" onClick={() => move("in")}>
            {t("receiveIn")}
          </button>
          <button className="btn ghost" type="button" onClick={() => move("adjust")}>
            {t("setCount")}
          </button>
          <button className="btn warn" type="button" onClick={() => move("out")}>
            {t("shrinkage")}
          </button>
        </div>
      </div>
      <div className="card">
        <h3>{t("history")}</h3>
        <table>
          <thead>
            <tr>
              <th>{t("when")}</th>
              <th>{t("kind")}</th>
              <th>{t("delta")}</th>
              <th>{t("after")}</th>
              <th>{t("reason")}</th>
            </tr>
          </thead>
          <tbody>
            {moves.map((m) => (
              <tr key={m.id}>
                <td>{when(m.created_at, locale)}</td>
                <td>{t(`kind_${m.kind}` as MsgKey)}</td>
                <td>{m.quantity_delta}</td>
                <td>{m.quantity_after}</td>
                <td className="muted">{m.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button
        className="btn ghost"
        onClick={async () => {
          await api(`/api/items/${id}/archive`, { method: "POST" });
          nav("/items");
        }}
      >
        {t("archiveItem")}
      </button>
    </div>
  );
}

export function OpNewItem() {
  const { t } = useI18n();
  const nav = useNavigate();
  const [error, setError] = useState("");
  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    try {
      const created = await api<Item>("/api/items", {
        method: "POST",
        body: JSON.stringify({
          sku: fd.get("sku"),
          name: fd.get("name"),
          name_id: fd.get("name_id") || fd.get("name"),
          description: fd.get("description") || "",
          description_id: fd.get("description_id") || fd.get("description") || "",
          quantity: Number(fd.get("quantity") || 0),
          unit: fd.get("unit") || "ea",
          reorder_point: Number(fd.get("reorder") || 0),
          unit_price_cents: centsFromRupiah(String(fd.get("price") || "0")),
          unit_cost_cents: centsFromRupiah(String(fd.get("cost") || "0")),
        }),
      });
      nav(`/items/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("couldNotCreate"));
    }
  }
  return (
    <form className="card form-grid" onSubmit={onSubmit}>
      <h2 style={{ margin: 0 }}>{t("newItem")}</h2>
      {error && <div className="banner">{error}</div>}
      <label>
        {t("sku")}
        <input name="sku" required />
      </label>
      <label>
        {t("nameEn")}
        <input name="name" required />
      </label>
      <label>
        {t("nameId")}
        <input name="name_id" />
      </label>
      <label>
        {t("descriptionEn")}
        <textarea name="description" />
      </label>
      <label>
        {t("descriptionId")}
        <textarea name="description_id" />
      </label>
      <label>
        {t("openingQty")}
        <input name="quantity" type="number" defaultValue={0} />
      </label>
      <label>
        {t("unit")}
        <input name="unit" defaultValue="pcs" />
      </label>
      <label>
        {t("sellPrice")}
        <input name="price" type="number" step="1" defaultValue={0} />
      </label>
      <label>
        {t("cost")}
        <input name="cost" type="number" step="1" defaultValue={0} />
      </label>
      <label>
        {t("reorderPoint")}
        <input name="reorder" type="number" defaultValue={0} />
      </label>
      <button className="btn" type="submit">
        {t("create")}
      </button>
    </form>
  );
}

export function OpInvoiceDetail() {
  const { t } = useI18n();
  const { id } = useParams();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [error, setError] = useState("");
  async function load() {
    setInvoice(await api<Invoice>(`/api/invoices/${id}`));
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [id]);
  if (!invoice) return <p className="muted">{error || t("loading")}</p>;
  return (
    <div className="grid">
      <div className="row no-print">
        <Link to="/invoices">{t("backInvoices")}</Link>
        <button className="btn ghost" onClick={() => window.print()}>
          {t("print")}
        </button>
        {invoice.status === "issued" && (
          <button
            className="btn"
            onClick={async () => {
              await api(`/api/invoices/${id}/mark-paid`, { method: "POST" });
              await load();
            }}
          >
            {t("markPaid")}
          </button>
        )}
        {invoice.status === "issued" && (
          <button
            className="btn warn"
            onClick={async () => {
              await api(`/api/orders/${invoice.purchase_order_id}/cancel`, { method: "POST" });
              await load();
            }}
          >
            {t("cancelOrder")}
          </button>
        )}
      </div>
      <InvoiceSheet invoice={invoice} />
    </div>
  );
}

export function OpSettings() {
  const { t } = useI18n();
  const [s, setS] = useState<Settings | null>(null);
  const [lan, setLan] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    api<Settings>("/api/settings").then(setS);
    api<{ lan_host: string }>("/api/lan").then((r) => setLan(`http://${r.lan_host}:8000/shop`));
  }, []);
  if (!s) return <p className="muted">{t("loading")}</p>;
  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const next = await api<Settings>("/api/settings", {
      method: "PATCH",
      body: JSON.stringify({
        name: fd.get("name"),
        address: fd.get("address"),
        phone: fd.get("phone"),
        currency_symbol: "Rp",
        currency_code: "IDR",
        tax_rate_bps: Math.round(Number(fd.get("tax") || 0) * 100),
      }),
    });
    setS(next);
    setSaved(true);
  }
  return (
    <div className="grid">
      <h2 style={{ margin: 0 }}>{t("shopSettings")}</h2>
      <div className="card">
        <h3>{t("phoneAccess")}</h3>
        <p className="muted">{t("phoneAccessHint")}</p>
        <b>{lan || "http://localhost:8000/shop"}</b>
      </div>
      <form className="card form-grid" onSubmit={onSubmit}>
        <label>
          {t("shopName")}
          <input name="name" defaultValue={s.name} />
        </label>
        <label>
          {t("address")}
          <input name="address" defaultValue={s.address} />
        </label>
        <label>
          {t("phone")}
          <input name="phone" defaultValue={s.phone} />
        </label>
        <label>
          {t("currency")}
          <input readOnly value={t("currencyValue")} />
        </label>
        <label>
          {t("taxPct")}
          <input name="tax" type="number" step="0.01" defaultValue={(s.tax_rate_bps / 100).toFixed(2)} />
        </label>
        <button className="btn" type="submit">
          {t("save")}
        </button>
        {saved && <span className="muted">{t("saved")}</span>}
      </form>
      <div className="row">
        <a className="btn ghost" href="/api/export/items.csv">
          {t("exportCsv")}
        </a>
        <a className="btn ghost" href="/api/backup">
          {t("downloadBackup")}
        </a>
      </div>
    </div>
  );
}
