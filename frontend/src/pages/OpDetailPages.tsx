import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { InvoiceSheet, PinSettings, SharePanel, ShareReceiptButton, ThermalReceipt } from "../components/ui";
import { DueDateForm, PaymentForm } from "./OfficePages";
import { type MsgKey, useI18n } from "../i18n";
import { centsFromRupiah, formatQty, money, rupiahFromCents, unitLabel, when } from "../money";
import type { Category, CsvImportResult, Invoice, Item, ItemDeleteResult, Location, Movement, Settings, StockLot } from "../types";

export function OpItemDetail() {
  const { t, pick, locale } = useI18n();
  const { id } = useParams();
  const [item, setItem] = useState<Item | null>(null);
  const [moves, setMoves] = useState<Movement[]>([]);
  const [lots, setLots] = useState<StockLot[]>([]);
  const [cats, setCats] = useState<Category[]>([]);
  const [locs, setLocs] = useState<Location[]>([]);
  const [qty, setQty] = useState("1");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [deleting, setDeleting] = useState(false);
  const nav = useNavigate();

  async function load() {
    const it = await api<Item>(`/api/items/${id}`);
    setItem(it);
    setMoves(await api<Movement[]>(`/api/items/${id}/movements`));
    setLots(await api<StockLot[]>(`/api/items/${id}/lots`));
    setCats(await api<Category[]>("/api/categories"));
    setLocs(await api<Location[]>("/api/locations"));
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
    setError("");
    setNotice("");
    try {
      await api(`/api/items/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: fd.get("name"),
          name_id: fd.get("name_id"),
          sku: fd.get("sku"),
          description: fd.get("description"),
          description_id: fd.get("description_id"),
          unit: fd.get("unit") || item.unit,
          unit_price_cents: centsFromRupiah(String(fd.get("price") || "0")),
          unit_cost_cents: centsFromRupiah(String(fd.get("cost") || "0")),
          reorder_point: Number(fd.get("reorder")),
          category_id: fd.get("category_id") ? Number(fd.get("category_id")) : null,
          location_id: fd.get("location_id") ? Number(fd.get("location_id")) : null,
          notes: fd.get("notes"),
        }),
      });
      setNotice(t("saved"));
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("updateFailed"));
    }
  }

  async function remove() {
    if (!item) return;
    if (!window.confirm(t("deleteItemConfirm", { name: pick(item.name, item.name_id) }))) return;
    setError("");
    setNotice("");
    setDeleting(true);
    try {
      const result = await api<ItemDeleteResult>(`/api/items/${id}`, { method: "DELETE" });
      nav("/items", { state: { notice: result.archived ? t("itemArchived") : t("itemDeleted") } });
    } catch (err) {
      setError(err instanceof Error ? err.message : t("updateFailed"));
      setDeleting(false);
    }
  }

  if (!item) return <p className="muted">{t("loading")}</p>;

  return (
    <div className="grid">
      <Link to="/items">{t("backItems")}</Link>
      {error && <div className="banner">{error}</div>}
      {notice && <div className="banner ok">{notice}</div>}
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div className="sku">{item.sku}</div>
            <h2 style={{ margin: "4px 0" }}>{pick(item.name, item.name_id)}</h2>
            {item.archived ? <div className="stock low">{t("itemHidden")}</div> : null}
            <p className="price" style={{ margin: 0 }}>
              {t("onHand", { qty: formatQty(item.quantity), unit: unitLabel(item.unit, locale) })}
            </p>
            {(item.reserved || 0) > 0 ? (
              <p className="muted">
                {t("sellable")} {formatQty(item.available ?? item.quantity)} · {t("heldInCart", { qty: formatQty(item.reserved || 0) })}
              </p>
            ) : null}
            <p className="muted">
              {t("fifoCogs")}: {money(item.fifo_cogs_cents || item.unit_cost_cents)} · {t("stockValue")}{" "}
              {money(item.inventory_value_cents || 0)}
            </p>
            {item.low_stock && <div className="stock low">{t("belowReorder", { point: item.reorder_point })}</div>}
          </div>
          <figure className="sku-qr-wrap">
            <img className="sku-qr" src={`/api/items/${item.id}/sku-qr`} alt={t("skuQrAlt", { sku: item.sku })} />
            <figcaption className="muted">{t("skuQrHint")}</figcaption>
          </figure>
        </div>
      </div>
      <form key={item.updated_at} className="card form-grid" onSubmit={save}>
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
          {t("lastCost")}
          <input name="cost" type="number" step="1" defaultValue={rupiahFromCents(item.unit_cost_cents)} />
        </label>
        <label>
          {t("unit")}
          <input name="unit" defaultValue={item.unit} />
        </label>
        <label>
          {t("pickCategory")}
          <select name="category_id" defaultValue={item.category_id || ""}>
            <option value="">{t("none")}</option>
            {cats.map((c) => (
              <option key={c.id} value={c.id}>
                {pick(c.name, c.name_id)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("pickLocation")}
          <select name="location_id" defaultValue={item.location_id || ""}>
            <option value="">{t("none")}</option>
            {locs.map((loc) => (
              <option key={loc.id} value={loc.id}>
                {pick(loc.name, loc.name_id)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("reorderPoint")}
          <input name="reorder" type="number" step="any" defaultValue={item.reorder_point} />
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
        <p className="muted">{t("fifoLayers")}</p>
        <label>
          {t("quantity")}
          <input value={qty} onChange={(e) => setQty(e.target.value)} inputMode="decimal" />
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
      <div className="card" style={{ overflowX: "auto" }}>
        <h3>{t("lots")}</h3>
        <p className="muted">{t("fifoLayers")}</p>
        <table>
          <thead>
            <tr>
              <th>{t("when")}</th>
              <th>{t("qty")}</th>
              <th>{t("fifoCogs")}</th>
            </tr>
          </thead>
          <tbody>
            {lots.map((lot) => (
              <tr key={lot.id}>
                <td>{when(lot.received_at, locale)}</td>
                <td>
                  {formatQty(lot.qty_remaining)} / {formatQty(lot.qty_original)}
                </td>
                <td>{money(lot.unit_cost_cents)}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
                <td>{formatQty(m.quantity_delta)}</td>
                <td>{formatQty(m.quantity_after)}</td>
                <td className="muted">{m.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button className="btn warn" type="button" disabled={deleting} onClick={remove}>
        {t("deleteNamed")}
      </button>
    </div>
  );
}

export function OpNewItem() {
  const { t, pick } = useI18n();
  const nav = useNavigate();
  const [error, setError] = useState("");
  const [cats, setCats] = useState<Category[]>([]);
  const [locs, setLocs] = useState<Location[]>([]);
  useEffect(() => {
    api<Category[]>("/api/categories").then(setCats);
    api<Location[]>("/api/locations").then(setLocs);
  }, []);
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
          category_id: fd.get("category_id") ? Number(fd.get("category_id")) : null,
          location_id: fd.get("location_id") ? Number(fd.get("location_id")) : null,
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
        {t("pickCategory")}
        <select name="category_id">
          <option value="">{t("none")}</option>
          {cats.map((c) => (
            <option key={c.id} value={c.id}>
              {pick(c.name, c.name_id)}
            </option>
          ))}
        </select>
      </label>
      <label>
        {t("pickLocation")}
        <select name="location_id">
          <option value="">{t("none")}</option>
          {locs.map((loc) => (
            <option key={loc.id} value={loc.id}>
              {pick(loc.name, loc.name_id)}
            </option>
          ))}
        </select>
      </label>
      <label>
        {t("openingQty")}
        <input name="quantity" type="number" step="any" defaultValue={0} />
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
    <div className="grid print-thermal">
      <div className="row no-print">
        <Link to="/invoices">{t("backInvoices")}</Link>
        <button className="btn ghost" onClick={() => window.print()}>
          {t("printThermal")}
        </button>
        <ShareReceiptButton invoice={invoice} />
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
        {invoice.status === "issued" ? <PaymentForm invoice={invoice} onPaid={setInvoice} /> : null}
        <DueDateForm invoice={invoice} onSaved={setInvoice} />
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
        {invoice.status === "paid" && (
          <button
            className="btn ghost"
            onClick={async () => {
              if (!window.confirm(t("confirmUnpay"))) return;
              await api(`/api/invoices/${id}/unpay`, { method: "POST" });
              await load();
            }}
          >
            {t("markUnpaid")}
          </button>
        )}
      </div>
      <p className="muted no-print">{t("invoiceAlsoReceipt")}</p>
      <ThermalReceipt invoice={invoice} />
      <div className="no-print">
        <InvoiceSheet invoice={invoice} />
      </div>
    </div>
  );
}

export function OpSettings() {
  const { t } = useI18n();
  const [s, setS] = useState<Settings | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    api<Settings>("/api/settings").then(setS);
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
        allow_lan: fd.get("allow_lan") === "on",
        credit_days: Number(fd.get("credit_days") || 30),
        ...(String(fd.get("invoice_prefix") || "").trim()
          ? { invoice_prefix: String(fd.get("invoice_prefix") || "").trim() }
          : {}),
        ...(String(fd.get("po_prefix") || "").trim() ? { po_prefix: String(fd.get("po_prefix") || "").trim() } : {}),
      }),
    });
    setS(next);
    setSaved(true);
  }
  return (
    <div className="grid">
      <h2 style={{ margin: 0 }}>{t("shopSettings")}</h2>
      <SharePanel showRestore />
      <PinSettings pinSet={Boolean(s.pin_set)} onChange={() => api<Settings>("/api/settings").then(setS)} />
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
        <label>
          {t("creditDays")}
          <input name="credit_days" type="number" min={0} max={365} defaultValue={s.credit_days ?? 30} />
        </label>
        <label>
          {t("invoicePrefix")}
          <input name="invoice_prefix" defaultValue={s.invoice_prefix} />
        </label>
        <label>
          {t("poPrefix")}
          <input name="po_prefix" defaultValue={s.po_prefix} />
        </label>
        <label className="row">
          <input name="allow_lan" type="checkbox" defaultChecked={Boolean(s.allow_lan)} />
          {t("allowLan")}
        </label>
        <p className="muted">{t("allowLanHint")}</p>
        <button className="btn" type="submit">
          {t("save")}
        </button>
        {saved && <span className="muted">{t("saved")}</span>}
      </form>
      <CatalogAdmin />
      <div className="card form-grid">
        <h3 style={{ margin: 0 }}>{t("importCsv")}</h3>
        <p className="muted">{t("importHint")}</p>
        <CsvImport />
        <a className="btn ghost" href="/api/export/items.csv">
          {t("exportCsv")}
        </a>
      </div>
    </div>
  );
}

function CatalogAdmin() {
  const { t } = useI18n();
  const [cats, setCats] = useState<Category[]>([]);
  const [locs, setLocs] = useState<Location[]>([]);
  const [error, setError] = useState("");

  async function load() {
    setCats(await api<Category[]>("/api/categories"));
    setLocs(await api<Location[]>("/api/locations"));
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);

  return (
    <div className="card form-grid">
      <h3 style={{ margin: 0 }}>{t("catalogAdmin")}</h3>
      {error && <div className="banner">{error}</div>}
      <form
        className="row"
        onSubmit={async (e) => {
          e.preventDefault();
          const form = e.currentTarget;
          const fd = new FormData(form);
          const name = String(fd.get("cat") || "").trim();
          if (!name) return;
          setError("");
          try {
            await api("/api/categories", { method: "POST", body: JSON.stringify({ name, name_id: name }) });
            form.reset();
            await load();
          } catch (err) {
            setError(err instanceof Error ? err.message : t("couldNotCreate"));
          }
        }}
      >
        <label>
          {t("addCategory")}
          <input name="cat" />
        </label>
        <button className="btn" type="submit">
          {t("addCategory")}
        </button>
      </form>
      <NamedList
        rows={cats}
        onRename={async (id, name) => {
          await api(`/api/categories/${id}`, { method: "PATCH", body: JSON.stringify({ name, name_id: name }) });
          await load();
        }}
        onDelete={async (id, intoId) => {
          const q = intoId ? `?into_id=${intoId}` : "";
          await api(`/api/categories/${id}${q}`, { method: "DELETE" });
          await load();
        }}
      />
      <form
        className="row"
        onSubmit={async (e) => {
          e.preventDefault();
          const form = e.currentTarget;
          const fd = new FormData(form);
          const name = String(fd.get("loc") || "").trim();
          if (!name) return;
          setError("");
          try {
            await api("/api/locations", { method: "POST", body: JSON.stringify({ name, name_id: name }) });
            form.reset();
            await load();
          } catch (err) {
            setError(err instanceof Error ? err.message : t("couldNotCreate"));
          }
        }}
      >
        <label>
          {t("addLocation")}
          <input name="loc" />
        </label>
        <button className="btn" type="submit">
          {t("addLocation")}
        </button>
      </form>
      <NamedList
        rows={locs}
        onRename={async (id, name) => {
          await api(`/api/locations/${id}`, { method: "PATCH", body: JSON.stringify({ name, name_id: name }) });
          await load();
        }}
        onDelete={async (id, intoId) => {
          const q = intoId ? `?into_id=${intoId}` : "";
          await api(`/api/locations/${id}${q}`, { method: "DELETE" });
          await load();
        }}
      />
    </div>
  );
}

function NamedList({
  rows,
  onRename,
  onDelete,
}: {
  rows: { id: number; name: string; name_id?: string }[];
  onRename: (id: number, name: string) => Promise<void>;
  onDelete: (id: number, intoId?: number) => Promise<void>;
}) {
  const { t, pick } = useI18n();
  const [error, setError] = useState("");
  const [into, setInto] = useState<Record<number, string>>({});
  if (!rows.length) return <p className="muted">{t("none")}</p>;
  return (
    <div className="grid">
      {error && <div className="banner">{error}</div>}
      {rows.map((row) => (
        <form
          key={row.id}
          className="row"
          onSubmit={async (e) => {
            e.preventDefault();
            const name = String(new FormData(e.currentTarget).get("name") || "").trim();
            if (!name) return;
            setError("");
            try {
              await onRename(row.id, name);
            } catch (err) {
              setError(err instanceof Error ? err.message : t("couldNotCreate"));
            }
          }}
        >
          <input name="name" defaultValue={pick(row.name, row.name_id)} />
          <button className="btn ghost" type="submit">
            {t("rename")}
          </button>
          {rows.length > 1 ? (
            <select value={into[row.id] || ""} onChange={(e) => setInto((cur) => ({ ...cur, [row.id]: e.target.value }))}>
              <option value="">{t("mergeInto")}</option>
              {rows
                .filter((other) => other.id !== row.id)
                .map((other) => (
                  <option key={other.id} value={other.id}>
                    {pick(other.name, other.name_id)}
                  </option>
                ))}
            </select>
          ) : null}
          <button
            className="btn warn"
            type="button"
            onClick={async () => {
              const dest = Number(into[row.id] || 0);
              const fromName = pick(row.name, row.name_id);
              const destRow = rows.find((other) => other.id === dest);
              const ok = destRow
                ? window.confirm(t("confirmMerge", { from: fromName, into: pick(destRow.name, destRow.name_id) }))
                : window.confirm(t("confirmDeleteNamed", { name: fromName }));
              if (!ok) return;
              setError("");
              try {
                await onDelete(row.id, dest || undefined);
              } catch (err) {
                setError(err instanceof Error ? err.message : t("couldNotCreate"));
              }
            }}
          >
            {t("deleteNamed")}
          </button>
        </form>
      ))}
    </div>
  );
}

function CsvImport() {
  const { t } = useI18n();
  const [result, setResult] = useState<CsvImportResult | null>(null);
  const [error, setError] = useState("");

  return (
    <>
      <input
        type="file"
        accept=".csv,text/csv"
        onChange={async (e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (!file) return;
          setError("");
          setResult(null);
          const body = new FormData();
          body.append("file", file);
          try {
            setResult(await api<CsvImportResult>("/api/import/items.csv", { method: "POST", body }));
          } catch (err) {
            setError(err instanceof Error ? err.message : t("couldNotCreate"));
          }
        }}
      />
      {error && <div className="banner">{error}</div>}
      {result && (
        <p className="muted">
          {t("importOk", { created: result.created, updated: result.updated })}
          {result.error_count ? ` ${result.error_count}` : ""}
        </p>
      )}
    </>
  );
}
