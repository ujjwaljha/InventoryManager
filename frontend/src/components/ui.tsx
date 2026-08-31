import { useEffect, useRef, useState, type FormEvent } from "react";
import { NavLink } from "react-router-dom";
import { api } from "../api";
import { type MsgKey, useI18n } from "../i18n";
import { formatQty, money, qtyStep, unitLabel, when, whenFull } from "../money";
import type { Invoice, Item, Settings } from "../types";

export function InvoiceSheet({ invoice }: { invoice: Invoice }) {
  const { t, pick, locale } = useI18n();
  return (
    <article className="invoice-sheet">
      <header className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1>{invoice.shop_name}</h1>
          <div className="muted">
            {invoice.shop_address}
            {invoice.shop_phone ? ` · ${invoice.shop_phone}` : ""}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="sku">{t("invoice")}</div>
          <b>{invoice.number}</b>
          <div className="muted">{when(invoice.issued_at, locale)}</div>
          {invoice.due_date ? (
            <div className="muted">
              {t("dueDate")} {invoice.due_date}
            </div>
          ) : null}
          <StatusTag status={invoice.status} />
        </div>
      </header>
      <p>
        <b>{t("billTo")}</b>
        <br />
        {invoice.shopper_name}
        <br />
        <span className="muted">{invoice.shopper_phone}</span>
        <br />
        {invoice.salesperson_name ? (
          <>
            <span className="muted">
              {t("soldBy")}: {invoice.salesperson_name}
            </span>
            <br />
          </>
        ) : null}
        <span className="muted">{invoice.purchase_order_number}</span>
      </p>
      <table>
        <thead>
          <tr>
            <th>{t("item")}</th>
            <th>{t("qty")}</th>
            <th>{t("price")}</th>
            <th>{t("amount")}</th>
          </tr>
        </thead>
        <tbody>
          {invoice.lines.map((ln) => (
            <tr key={ln.id}>
              <td>
                <div>{pick(ln.name, ln.name_id)}</div>
                <div className="sku">{ln.sku}</div>
              </td>
              <td>{formatQty(ln.quantity)} {unitLabel(ln.unit || "ea", locale)}</td>
              <td>{money(ln.unit_price_cents, invoice.currency_symbol)}</td>
              <td>{money(ln.line_total_cents, invoice.currency_symbol)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 16, textAlign: "right" }}>
        <div className="muted">
          {t("subtotal")} {money(invoice.subtotal_cents, invoice.currency_symbol)}
        </div>
        {invoice.tax_cents > 0 && (
          <div className="muted">
            {t("tax")} ({(invoice.tax_bps / 100).toFixed(2)}%) {money(invoice.tax_cents, invoice.currency_symbol)}
          </div>
        )}
        <h2 style={{ margin: "8px 0 0" }}>
          {t("total")} {money(invoice.total_cents, invoice.currency_symbol)}
        </h2>
      </div>
    </article>
  );
}

export function ThermalReceipt({ invoice }: { invoice: Invoice }) {
  const { t, pick, locale } = useI18n();
  return (
    <article className="thermal-receipt" aria-label={t("receipt")}>
      <header className="thermal-head">
        <h1>{invoice.shop_name}</h1>
        <div>{invoice.shop_address}</div>
        {invoice.shop_phone ? <div>{invoice.shop_phone}</div> : null}
      </header>
      <hr className="thermal-dash" />
      <div className="thermal-meta">
        <div>
          <b>{t("receipt")}</b> {invoice.number}
        </div>
        <div>
          {t("dateTime")}: {whenFull(invoice.issued_at, locale)}
        </div>
        {invoice.due_date ? (
          <div>
            {t("dueDate")}: {invoice.due_date}
          </div>
        ) : null}
        {invoice.salesperson_name ? (
          <div>
            {t("soldBy")}: {invoice.salesperson_name}
          </div>
        ) : null}
        <div>
          {t("customer")}: {invoice.shopper_name}
        </div>
        <div>
          {t("phone")}: {invoice.shopper_phone}
        </div>
        <div>
          {t(`status_${invoice.status}` as MsgKey)}
        </div>
      </div>
      <hr className="thermal-dash" />
      {invoice.lines.map((ln) => (
        <div key={ln.id} className="thermal-item">
          <div>{pick(ln.name, ln.name_id)}</div>
          <div className="thermal-line">
            <span>
              {formatQty(ln.quantity)} {unitLabel(ln.unit || "ea", locale)} × {money(ln.unit_price_cents, invoice.currency_symbol)}
            </span>
            <span>{money(ln.line_total_cents, invoice.currency_symbol)}</span>
          </div>
        </div>
      ))}
      <hr className="thermal-dash" />
      <div className="thermal-line muted">
        <span>{t("subtotal")}</span>
        <span>{money(invoice.subtotal_cents, invoice.currency_symbol)}</span>
      </div>
      {invoice.tax_cents > 0 && (
        <div className="thermal-line muted">
          <span>
            {t("tax")} {(invoice.tax_bps / 100).toFixed(2)}%
          </span>
          <span>{money(invoice.tax_cents, invoice.currency_symbol)}</span>
        </div>
      )}
      <div className="thermal-line thermal-total">
        <span>{t("total")}</span>
        <span>{money(invoice.total_cents, invoice.currency_symbol)}</span>
      </div>
      <hr className="thermal-dash" />
      <p className="thermal-head">{t("thankYou")}</p>
    </article>
  );
}

export function ItemPicker({
  onAdd,
  costMode = false,
}: {
  onAdd: (item: Item, qty: number, extra?: number) => void;
  costMode?: boolean;
}) {
  const { t, pick, locale } = useI18n();
  const [items, setItems] = useState<Item[]>([]);
  const [q, setQ] = useState("");
  const [qty, setQty] = useState("1");
  const [extra, setExtra] = useState("");
  const [picked, setPicked] = useState<Item | null>(null);

  useEffect(() => {
    api<Item[]>("/api/items").then(setItems).catch(() => undefined);
  }, []);

  const want = Number(qty);
  const sellable = picked ? (picked.available ?? picked.quantity) : 0;
  const overStock = Boolean(!costMode && picked && Number.isFinite(want) && want > sellable);

  const shown = items
    .filter((i) => {
      if (!q.trim()) return picked ? i.id === picked.id : true;
      const n = q.toLowerCase();
      return (
        i.sku.toLowerCase().includes(n) ||
        i.name.toLowerCase().includes(n) ||
        (i.name_id || "").toLowerCase().includes(n)
      );
    })
    .slice(0, 8);

  return (
    <div className="form-grid">
      <label>
        {t("item")}
        <input
          className="search"
          placeholder={t("searchSku")}
          value={picked ? pick(picked.name, picked.name_id) : q}
          onChange={(e) => {
            setPicked(null);
            setQ(e.target.value);
          }}
        />
      </label>
      {!picked && q && (
        <div className="pick-list">
          {shown.map((i) => (
            <button
              type="button"
              className="chip"
              key={i.id}
              onClick={() => {
                setPicked(i);
                setQ("");
                if (costMode) setExtra(String(Math.round((i.fifo_cogs_cents ?? i.unit_cost_cents) / 100)));
                setQty(String(qtyStep(i.unit)));
              }}
            >
              {pick(i.name, i.name_id)} · {i.sku} · {formatQty(i.available ?? i.quantity)} {unitLabel(i.unit, locale)}
              {(i.reserved || 0) > 0 ? ` · ${t("heldInCart", { qty: formatQty(i.reserved || 0) })}` : ""}
            </button>
          ))}
        </div>
      )}
      <label>
        {t("quantity")}
        <input value={qty} onChange={(e) => setQty(e.target.value)} inputMode="decimal" />
      </label>
      {costMode && (
        <label>
          {t("unitCost")}
          <input value={extra} onChange={(e) => setExtra(e.target.value)} inputMode="numeric" />
        </label>
      )}
      {overStock && picked ? (
        <p className="muted">
          {t("onlyLeft", { name: pick(picked.name, picked.name_id), available: formatQty(picked.available ?? picked.quantity) })}
        </p>
      ) : null}
      <button
        className="btn ghost"
        type="button"
        disabled={!picked || want <= 0 || overStock}
        onClick={() => {
          if (!picked || overStock) return;
          onAdd(picked, want, extra ? Number(extra) : undefined);
          setPicked(null);
          setQ("");
          setQty("1");
        }}
      >
        {t("addLine")}
      </button>
    </div>
  );
}


export function StatusTag({ status }: { status: string }) {
  const { t } = useI18n();
  const key = `status_${status}` as MsgKey;
  return <span className={`tag ${status}`}>{t(key)}</span>;
}

export function PinUnlock({ onUnlocked }: { onUnlocked: () => void }) {
  const { t } = useI18n();
  const [pin, setPin] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/api/operator/unlock", { method: "POST", body: JSON.stringify({ pin }) });
      onUnlocked();
    } catch {
      setError(t("pinWrong"));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="card form-grid" onSubmit={submit} style={{ maxWidth: 360, margin: "48px auto" }}>
      <h2 style={{ margin: 0 }}>{t("pinRequired")}</h2>
      <p className="muted">{t("pinHint")}</p>
      {error && <div className="banner">{error}</div>}
      <label>
        {t("enterPin")}
        <input
          value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, "").slice(0, 8))}
          inputMode="numeric"
          autoComplete="off"
          autoFocus
        />
      </label>
      <button className="btn" type="submit" disabled={busy || pin.length < 4}>
        {t("unlock")}
      </button>
    </form>
  );
}

export function PinSettings({ pinSet, onChange }: { pinSet: boolean; onChange?: () => void }) {
  const { t } = useI18n();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  async function save(e: FormEvent) {
    e.preventDefault();
    setError("");
    setNote("");
    try {
      await api("/api/operator/pin", {
        method: "POST",
        body: JSON.stringify({ pin: next, current_pin: current }),
      });
      setNote(t("pinSet"));
      setCurrent("");
      setNext("");
      onChange?.();
    } catch {
      setError(t("pinWrong"));
    }
  }
  async function remove() {
    setError("");
    setNote("");
    try {
      await api("/api/operator/pin/clear", { method: "POST", body: JSON.stringify({ pin: current }) });
      setNote(t("pinRemoved"));
      setCurrent("");
      onChange?.();
    } catch {
      setError(t("pinWrong"));
    }
  }
  async function lock() {
    await api("/api/operator/lock", { method: "POST" });
    window.location.reload();
  }
  return (
    <form className="card form-grid" onSubmit={save}>
      <h3 style={{ margin: 0 }}>{t("operatorPin")}</h3>
      <p className="muted">{t("pinHint")}</p>
      {error && <div className="banner">{error}</div>}
      {pinSet ? (
        <label>
          {t("currentPin")}
          <input value={current} onChange={(e) => setCurrent(e.target.value.replace(/\D/g, "").slice(0, 8))} inputMode="numeric" autoComplete="off" />
        </label>
      ) : null}
      <label>
        {t("newPin")}
        <input value={next} onChange={(e) => setNext(e.target.value.replace(/\D/g, "").slice(0, 8))} inputMode="numeric" autoComplete="off" />
      </label>
      <div className="row">
        <button className="btn" type="submit" disabled={next.length < 4}>
          {pinSet ? t("changePin") : t("setPin")}
        </button>
        {pinSet ? (
          <>
            <button className="btn ghost" type="button" onClick={remove} disabled={current.length < 4}>
              {t("removePin")}
            </button>
            <button className="btn ghost" type="button" onClick={lock}>
              {t("lockOffice")}
            </button>
          </>
        ) : null}
      </div>
      {note && <p className="muted">{note}</p>}
    </form>
  );
}

export function IdentifyForm({
  onDone,
  pending,
  onCancel,
}: {
  onDone: (name: string, phone: string) => void;
  pending?: boolean;
  onCancel?: () => void;
}) {
  const { t } = useI18n();
  return (
    <form
      className="card form-grid"
      onSubmit={(e) => {
        e.preventDefault();
        const fd = new FormData(e.currentTarget);
        onDone(String(fd.get("name") || ""), String(fd.get("phone") || ""));
      }}
    >
      <h3 style={{ margin: 0 }}>{t("whoShopping")}</h3>
      <p className="muted" style={{ margin: 0 }}>
        {t("whoShoppingHint")}
      </p>
      <label>
        {t("name")}
        <input name="name" required placeholder={t("yourName")} autoComplete="name" />
      </label>
      <label>
        {t("phone")}
        <input name="phone" required placeholder={t("mobileNumber")} inputMode="tel" autoComplete="tel" />
      </label>
      <div className="row">
        <button className="btn" type="submit" disabled={pending}>
          {t("continue")}
        </button>
        {onCancel ? (
          <button className="btn ghost" type="button" onClick={onCancel}>
            {t("cancel")}
          </button>
        ) : null}
      </div>
    </form>
  );
}

export function ShopNav({ count }: { count: number }) {
  const { t } = useI18n();
  const bump = useCountBump(count);
  return (
    <nav className="bottom-nav">
      <NavLink to="/shop" end>
        {t("shop")}
      </NavLink>
      <NavLink to="/shop/order" data-order-target>
        {t("order")}
        {count > 0 ? (
          <span key={bump} className={`badge${bump ? " bump" : ""}`}>
            {count}
          </span>
        ) : null}
      </NavLink>
      <NavLink to="/shop/invoices">{t("invoices")}</NavLink>
    </nav>
  );
}

function useCountBump(count: number) {
  const [bump, setBump] = useState(0);
  const prev = useRef(count);
  useEffect(() => {
    if (count > prev.current) setBump((n) => n + 1);
    prev.current = count;
  }, [count]);
  return bump;
}

export function OpNav() {
  const { t } = useI18n();
  return (
    <nav className="bottom-nav office-nav">
      <NavLink to="/till">{t("till")}</NavLink>
      <NavLink to="/items">{t("items")}</NavLink>
      <NavLink to="/receipts">{t("receipts")}</NavLink>
      <NavLink to="/reports">{t("reports")}</NavLink>
      <NavLink to="/more">{t("more")}</NavLink>
    </nav>
  );
}

export function SharePanel({ showRestore = false }: { showRestore?: boolean }) {
  const { t } = useI18n();
  const [lan, setLan] = useState("http://localhost:8000/shop");
  const [copied, setCopied] = useState(false);
  const [note, setNote] = useState("");
  const [lanOn, setLanOn] = useState(false);
  useEffect(() => {
    api<Settings>("/api/settings")
      .then((s) => setLanOn(Boolean(s.allow_lan)))
      .catch(() => undefined);
    api<{ shop_url?: string; lan_host: string }>("/api/lan")
      .then((r) => setLan(r.shop_url || `http://${r.lan_host}:8000/shop`))
      .catch(() => undefined);
  }, []);

  async function copy() {
    try {
      await navigator.clipboard.writeText(lan);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }

  async function restore(file: File | undefined) {
    if (!file) return;
    if (!window.confirm(t("restoreConfirm"))) return;
    setNote("");
    try {
      const fd = new FormData();
      fd.append("file", file, file.name || "inventory.db");
      await api("/api/backup/restore", { method: "POST", body: fd });
      setNote(t("restored"));
      window.location.reload();
    } catch {
      setNote(t("restoreFailed"));
    }
  }

  return (
    <section className="card">
      <h3>{t("shareTitle")}</h3>
      {lanOn ? (
        <>
          <p className="muted">{t("wifiLive")}</p>
          <div className="share-row">
            <img className="qr" src="/api/lan/qr" alt={t("qrAlt")} />
            <div>
              <b className="share-url">{lan}</b>
              <div className="row" style={{ marginTop: 10 }}>
                <button className="btn" type="button" onClick={copy}>
                  {copied ? t("copied") : t("copyAddress")}
                </button>
              </div>
            </div>
          </div>
        </>
      ) : (
        <p className="muted">{t("lanOff")}</p>
      )}
      <p className="muted">{t("fileShare")}</p>
      {showRestore && (
        <div className="row">
          <a className="btn ghost" href="/api/backup">
            {t("downloadBackup")}
          </a>
          <label className="btn ghost" style={{ cursor: "pointer" }}>
            {t("restoreBackup")}
            <input
              type="file"
              accept=".db,.sqlite,application/octet-stream"
              hidden
              onChange={(e) => {
                const f = e.currentTarget.files?.[0];
                e.currentTarget.value = "";
                restore(f);
              }}
            />
          </label>
        </div>
      )}
      {note && <p className="muted">{note}</p>}
    </section>
  );
}
