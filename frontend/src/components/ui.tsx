import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { api } from "../api";
import { ScanButton, type ScanResult } from "./BarcodeScanner";
import { type MsgKey, useI18n } from "../i18n";
import { formatQty, money, qtyStep, unitLabel, when, whenFull } from "../money";
import { receiptPlainText, shareReceipt } from "../receiptShare";
import { matchScannedCode, shortScanCode } from "../sku";
import type { Invoice, Item, Settings, Shopper } from "../types";

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

export function ShareReceiptButton({ invoice }: { invoice: Invoice }) {
  const { t, pick, locale } = useI18n();
  const [note, setNote] = useState("");

  async function onShare() {
    setNote("");
    const text = receiptPlainText(invoice, t, pick, locale);
    const title = `${invoice.shop_name} · ${invoice.number}`;
    try {
      const outcome = await shareReceipt(title, text, `${invoice.number}.txt`);
      if (outcome === "copied") {
        setNote(t("receiptCopied"));
        window.setTimeout(() => setNote(""), 2500);
      }
    } catch {
      setNote(t("shareReceiptFailed"));
    }
  }

  return (
    <button className="btn ghost" type="button" onClick={onShare}>
      {note || t("shareReceipt")}
    </button>
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
  const searchRef = useRef<HTMLInputElement>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [q, setQ] = useState("");
  const [qty, setQty] = useState("1");
  const [extra, setExtra] = useState("");
  const [picked, setPicked] = useState<Item | null>(null);

  useEffect(() => {
    api<Item[]>("/api/items").then(setItems).catch(() => undefined);
  }, []);

  function resolveItem(needle: string): Item | null {
    const n = needle.trim().toLowerCase();
    if (!n) return picked;
    const exactSku = items.find((i) => i.sku.toLowerCase() === n);
    if (exactSku) return exactSku;
    const exactName = items.filter(
      (i) => i.name.toLowerCase() === n || (i.name_id || "").toLowerCase() === n,
    );
    if (exactName.length === 1) return exactName[0];
    const partial = items.filter(
      (i) =>
        i.sku.toLowerCase().includes(n) ||
        i.name.toLowerCase().includes(n) ||
        (i.name_id || "").toLowerCase().includes(n),
    );
    if (partial.length === 1) return partial[0];
    return picked;
  }

  function selectItem(item: Item) {
    setPicked(item);
    setQ("");
    if (costMode) setExtra(String(Math.round((item.fifo_cogs_cents ?? item.unit_cost_cents) / 100)));
    setQty(String(qtyStep(item.unit)));
  }

  function finishAdd() {
    setPicked(null);
    setQ("");
    setQty("1");
    setExtra("");
    window.setTimeout(() => searchRef.current?.focus(), 0);
  }

  function tryAdd(item: Item) {
    const want = Number(qty);
    if (!Number.isFinite(want) || want <= 0) return;
    const sellable = item.available ?? item.quantity;
    if (!costMode && want > sellable) return;
    onAdd(item, want, extra ? Number(extra) : undefined);
    finishAdd();
  }

  function commit(item: Item, quantity: number, cost?: number) {
    onAdd(item, quantity, cost);
    finishAdd();
  }

  async function handleScan(code: string): Promise<ScanResult> {
    if (!items.length) return { ok: false, message: t("loading") };
    const item = matchScannedCode(items, code);
    if (!item) return { ok: false, message: t("unknownSku", { sku: shortScanCode(code) }) };
    const step = qtyStep(item.unit);
    const sellable = item.available ?? item.quantity;
    if (!costMode && step > sellable) {
      return {
        ok: false,
        message: t("onlyLeft", { name: pick(item.name, item.name_id), available: formatQty(sellable) }),
      };
    }
    const cost = costMode ? Math.round((item.fifo_cogs_cents ?? item.unit_cost_cents) / 100) : undefined;
    commit(item, step, cost);
    return { ok: true, message: t("scanAdded", { name: pick(item.name, item.name_id) }) };
  }

  function onSearchKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key !== "Enter") return;
    e.preventDefault();
    e.stopPropagation();
    const item = picked || resolveItem(e.currentTarget.value);
    if (item) tryAdd(item);
  }

  function onQtyKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key !== "Enter") return;
    e.preventDefault();
    e.stopPropagation();
    if (picked) tryAdd(picked);
  }

  const want = Number(qty);
  const sellable = picked ? (picked.available ?? picked.quantity) : 0;
  const overStock = Boolean(!costMode && picked && Number.isFinite(want) && want > sellable);

  useEffect(() => {
    const n = q.trim().toLowerCase();
    if (!n || picked) return;
    const exact = items.find((i) => i.sku.toLowerCase() === n);
    if (exact) selectItem(exact);
  }, [q, items, picked]);

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
      <div className="scan-row">
        <label>
          {t("item")}
          <input
            ref={searchRef}
            className="search"
            placeholder={t("searchSku")}
            value={picked ? pick(picked.name, picked.name_id) : q}
            autoComplete="off"
            autoCapitalize="off"
            autoCorrect="off"
            spellCheck={false}
            onChange={(e) => {
              setPicked(null);
              setQ(e.target.value);
            }}
            onKeyDown={onSearchKeyDown}
          />
        </label>
        <ScanButton onCode={handleScan} disabled={!items.length} />
      </div>
      <p className="muted" style={{ margin: 0 }}>
        {t("scanSkuHint")}
      </p>
      <p className="muted" style={{ margin: 0 }}>
        {t("scanCameraHint")}
      </p>
      {!picked && q && (
        <div className="pick-list">
          {shown.map((i) => (
            <button
              type="button"
              className="chip"
              key={i.id}
              onClick={() => selectItem(i)}
            >
              {pick(i.name, i.name_id)} · {i.sku} · {formatQty(i.available ?? i.quantity)} {unitLabel(i.unit, locale)}
              {(i.reserved || 0) > 0 ? ` · ${t("heldInCart", { qty: formatQty(i.reserved || 0) })}` : ""}
            </button>
          ))}
        </div>
      )}
      <label>
        {t("quantity")}
        <input value={qty} onChange={(e) => setQty(e.target.value)} inputMode="decimal" onKeyDown={onQtyKeyDown} />
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
          tryAdd(picked);
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

export function SalesAgentSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const { t } = useI18n();
  const [agents, setAgents] = useState<{ id: number; display_name: string; username: string }[]>([]);
  useEffect(() => {
    api<{ id: number; display_name: string; username: string }[]>("/api/sales-agents")
      .then(setAgents)
      .catch(() => setAgents([]));
  }, []);
  const extra = value && !agents.some((a) => a.display_name === value);
  return (
    <label>
      {t("salesAgent")}
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{t("noSalesAgent")}</option>
        {extra ? <option value={value}>{value}</option> : null}
        {agents.map((a) => (
          <option key={a.id} value={a.display_name}>
            {a.display_name}
          </option>
        ))}
      </select>
      <span className="muted">{t("salesAgentOptional")}</span>
    </label>
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
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  return (
    <form
      className="card form-grid"
      onSubmit={(e) => {
        e.preventDefault();
        onDone(name, phone);
      }}
    >
      <h3 style={{ margin: 0 }}>{t("whoShopping")}</h3>
      <p className="muted" style={{ margin: 0 }}>
        {t("whoShoppingHint")}
      </p>
      <CustomerPicker
        name={name}
        phone={phone}
        onName={setName}
        onPhone={setPhone}
        endpoint="/api/shop/customers"
        onPick={(c) => onDone(c.name, c.phone)}
      />
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

export function CustomerPicker({
  name,
  phone,
  onName,
  onPhone,
  onPick,
  endpoint = "/api/shoppers",
  required = true,
}: {
  name: string;
  phone: string;
  onName: (v: string) => void;
  onPhone: (v: string) => void;
  onPick?: (c: Shopper) => void;
  endpoint?: string;
  required?: boolean;
}) {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [matches, setMatches] = useState<Shopper[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const tmr = window.setTimeout(() => {
      const qs = q.trim() ? `?q=${encodeURIComponent(q.trim())}` : "";
      api<Shopper[]>(`${endpoint}${qs}`)
        .then((rows) => {
          setMatches(rows);
          setLoaded(true);
        })
        .catch(() => {
          setMatches([]);
          setLoaded(true);
        });
    }, 150);
    return () => window.clearTimeout(tmr);
  }, [q, endpoint]);

  useEffect(() => {
    const digits = phone.replace(/\D/g, "");
    if (digits.length < 8 || name.trim()) return;
    const hit = matches.find((s) => s.phone.replace(/\D/g, "") === digits);
    if (hit) onName(hit.name);
  }, [phone, matches, name, onName]);

  function pick(c: Shopper) {
    onName(c.name);
    onPhone(c.phone);
    setQ("");
    onPick?.(c);
  }

  const shown = matches.slice(0, 8);

  return (
    <>
      <label>
        {t("returningCustomers")}
        <input
          className="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t("pickReturningCustomer")}
          autoComplete="off"
        />
      </label>
      {shown.length > 0 ? (
        <div className="customer-matches" role="listbox" aria-label={t("savedCustomers")}>
          {shown.map((c) => (
            <button
              key={c.id}
              type="button"
              className={`chip${c.phone === phone.replace(/\D/g, "") || c.phone === phone ? " on" : ""}`}
              onClick={() => pick(c)}
            >
              {c.name} · {c.phone}
            </button>
          ))}
        </div>
      ) : loaded ? (
        <p className="muted" style={{ margin: 0 }}>
          {t("noCustomersYet")}
        </p>
      ) : null}
      <label>
        {t("name")}
        <input
          required={required}
          value={name}
          onChange={(e) => onName(e.target.value)}
          placeholder={t("yourName")}
          autoComplete="name"
        />
      </label>
      <label>
        {t("phone")}
        <input
          required={required}
          value={phone}
          onChange={(e) => onPhone(e.target.value)}
          placeholder={t("mobileNumber")}
          inputMode="tel"
          autoComplete="tel"
        />
      </label>
    </>
  );
}

export function PageHeader({
  kicker,
  title,
  hint,
  actions,
}: {
  kicker?: string;
  title: string;
  hint?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-header">
      <div>
        {kicker ? <div className="sku">{kicker}</div> : null}
        <h2>{title}</h2>
        {hint ? <p className="muted page-hint">{hint}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </div>
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
