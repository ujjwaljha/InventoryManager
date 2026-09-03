import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { FinderBar, InvoiceResultCard, PAGE_SIZE, Pager, ResultList, buildQuery, useDebounced, type PageResult } from "../components/Finder";
import { ItemPicker, PageHeader, ShareReceiptButton, StatusTag, ThermalReceipt } from "../components/ui";
import { useI18n } from "../i18n";
import { centsFromRupiah, formatQty, money, rupiahFromCents, todayInput, when } from "../money";
import type { CreditReport, DamageNote, Invoice, Item, SupplierReturn } from "../types";

type PickLine = { item: Item; quantity: number };

export function ReceiptsPage() {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<PageResult<Invoice> | null>(null);
  const [error, setError] = useState("");
  const needle = useDebounced(q);

  async function load(nextOffset = offset, nextQ = needle) {
    setError("");
    const qs = buildQuery({
      q: nextQ.trim(),
      status,
      date_from: dateFrom,
      date_to: dateTo,
      limit: PAGE_SIZE,
      offset: nextOffset,
    });
    setPage(await api<PageResult<Invoice>>(`/api/receipts${qs}`));
  }

  useEffect(() => {
    setOffset(0);
  }, [needle, status, dateFrom, dateTo]);

  useEffect(() => {
    load(offset, needle).catch((e) => setError(e instanceof Error ? e.message : t("couldNotAdd")));
  }, [needle, status, dateFrom, dateTo, offset, t]);

  return (
    <div className="grid">
      <PageHeader title={t("lookUpReceipt")} hint={t("lookUpHint")} />
      <FinderBar
        q={q}
        onQ={setQ}
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFrom={setDateFrom}
        onDateTo={setDateTo}
        statuses={["issued", "paid", "void"]}
        status={status}
        onStatus={setStatus}
        onSubmit={() => load(0, q)}
      />
      {error && <div className="banner">{error}</div>}
      {page && page.items.length === 0 && <p className="empty-state">{t("noRows")}</p>}
      {page && page.items.length > 0 ? (
        <ResultList>
          {page.items.map((inv) => (
            <InvoiceResultCard key={inv.id} invoice={inv} />
          ))}
        </ResultList>
      ) : null}
      {page ? <Pager total={page.total} limit={page.limit} offset={page.offset} onOffset={setOffset} /> : null}
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
      <div className="no-print">
        <PageHeader
          kicker={invoice.number}
          title={invoice.shopper_name || t("lookUpReceipt")}
          hint={invoice.shopper_phone}
          actions={
            <>
              <Link className="btn ghost" to="/receipts">
                {t("backInvoices")}
              </Link>
              <button className="btn" onClick={() => window.print()}>
                {t("printThermal")}
              </button>
              <ShareReceiptButton invoice={invoice} />
            </>
          }
        />
        <p className="muted">{t("thermalHint")}</p>
      </div>
      {invoice.status === "issued" && (
        <div className="row no-print">
          <button
            className="btn"
            onClick={async () => {
              const next = await api<Invoice>(`/api/invoices/${invoice.id}/mark-paid`, { method: "POST" });
              setInvoice(next);
            }}
          >
            {t("markPaid")}
          </button>
          <PaymentForm invoice={invoice} onPaid={setInvoice} />
          <button
            className="btn warn"
            onClick={async () => {
              if (!window.confirm(t("confirmCancel"))) return;
              await api(`/api/orders/${invoice.purchase_order_id}/cancel`, { method: "POST" });
              const next = await api<Invoice>(`/api/invoices/${invoice.id}`);
              setInvoice(next);
            }}
          >
            {t("cancelOrder")}
          </button>
        </div>
      )}
      {invoice.status !== "void" && (
        <div className="row no-print">
          <DueDateForm invoice={invoice} onSaved={setInvoice} />
        </div>
      )}
      {invoice.status === "paid" && (
        <div className="row no-print">
          <button
            className="btn ghost"
            onClick={async () => {
              if (!window.confirm(t("confirmUnpay"))) return;
              const next = await api<Invoice>(`/api/invoices/${invoice.id}/unpay`, { method: "POST" });
              setInvoice(next);
            }}
          >
            {t("markUnpaid")}
          </button>
        </div>
      )}
      <ThermalReceipt invoice={invoice} />
    </div>
  );
}

export function CreditPage() {
  const { t, locale } = useI18n();
  const [data, setData] = useState<CreditReport | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<"all" | "overdue" | "promised">("all");
  const [printFor, setPrintFor] = useState<number | null>(null);

  async function load() {
    setData(await api<CreditReport>("/api/credit"));
  }
  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : t("couldNotAdd")));
  }, []);

  if (error) return <div className="banner">{error}</div>;
  if (!data) return <p className="muted">{t("loading")}</p>;

  const today = todayInput();
  const customers = data.customers.filter((c) => {
    if (filter === "all") return true;
    if (filter === "overdue") {
      return data.invoices.some((inv) => inv.shopper_id === c.shopper_id && (inv.overdue_days || 0) > 0);
    }
    return (c.notes || []).some((note) => note.promised_date && note.promised_date <= today);
  });
  const printCustomer = printFor == null ? null : data.customers.find((c) => c.shopper_id === printFor);
  const printInvoices = printCustomer
    ? data.invoices.filter((inv) => inv.shopper_id === printCustomer.shopper_id && (inv.overdue_days || 0) > 0)
    : [];

  function startPrint(shopperId: number) {
    setPrintFor(shopperId);
    window.setTimeout(() => {
      window.print();
      setPrintFor(null);
    }, 50);
  }

  return (
    <div className="grid">
      {printCustomer ? (
        <article className="thermal-receipt">
          <header className="thermal-head">
            <h1>{printInvoices[0]?.shop_name || t("credit")}</h1>
            <div>{t("reminderTitle")}</div>
          </header>
          <hr className="thermal-dash" />
          <div className="thermal-meta">
            <div>
              <b>{printCustomer.shopper_name}</b>
            </div>
            <div>{printCustomer.shopper_phone}</div>
          </div>
          <hr className="thermal-dash" />
          {(printInvoices.length ? printInvoices : data.invoices.filter((inv) => inv.shopper_id === printCustomer.shopper_id)).map(
            (inv) => (
              <div key={inv.id} className="thermal-item">
                <div>
                  {inv.number}
                  {inv.due_date ? ` · ${t("dueDate")} ${inv.due_date}` : ""}
                </div>
                <div className="thermal-line">
                  <span>{money(inv.balance_cents ?? inv.total_cents, inv.currency_symbol)}</span>
                </div>
              </div>
            ),
          )}
          <hr className="thermal-dash" />
          <div className="thermal-total">
            {t("unpaidTotal")} {money(printCustomer.unpaid_cents, data.currency_symbol)}
          </div>
        </article>
      ) : null}
      <div className={printFor ? "no-print" : ""}>
      <PageHeader title={t("credit")} hint={t("creditHint")} />
      <div className="card filter-card">
        <div className="chips">
          <button className={`chip ${filter === "all" ? "on" : ""}`} type="button" onClick={() => setFilter("all")}>
            {t("allUnpaid")}
          </button>
          <button className={`chip ${filter === "overdue" ? "on" : ""}`} type="button" onClick={() => setFilter("overdue")}>
            {t("overdueOnly")}
          </button>
          <button className={`chip ${filter === "promised" ? "on" : ""}`} type="button" onClick={() => setFilter("promised")}>
            {t("promiseDue")}
          </button>
        </div>
      </div>
      <div className="row">
        <div className="card kpi">
          {t("unpaid")}
          <b>{data.invoice_count}</b>
        </div>
        <div className="card kpi">
          {t("unpaidTotal")}
          <b>{money(data.unpaid_cents, data.currency_symbol)}</b>
        </div>
        <button className="card kpi" type="button" onClick={() => setFilter("promised")}>
          {t("promiseDue")}
          <b>{data.promises_due_count ?? 0}</b>
        </button>
        <div className="card kpi">
          {t("agingCurrent")}
          <b>{money(data.aging_cents?.d0_30 || 0, data.currency_symbol)}</b>
        </div>
        <div className="card kpi">
          {t("aging30")}
          <b>{money(data.aging_cents?.d31_60 || 0, data.currency_symbol)}</b>
        </div>
        <div className="card kpi">
          {t("aging60")}
          <b>{money(data.aging_cents?.d61_90 || 0, data.currency_symbol)}</b>
        </div>
        <div className="card kpi">
          {t("aging90")}
          <b>{money(data.aging_cents?.d90_plus || 0, data.currency_symbol)}</b>
        </div>
      </div>
      {customers.length === 0 && <p className="empty-state">{t("noCredit")}</p>}
      {customers.map((c) => (
        <section className="card" key={c.shopper_id}>
          <div className="row split" style={{ justifyContent: "space-between" }}>
            <div>
              <b>{c.shopper_name}</b>
              <div className="muted">{c.shopper_phone}</div>
              <div className="muted">
                {c.invoice_count} · {t("oldest")} {when(c.oldest_issued_at, locale)}
              </div>
              <button className="btn ghost" type="button" onClick={() => startPrint(c.shopper_id)}>
                {t("printReminder")}
              </button>
            </div>
            <div className="price split-amount">{money(c.unpaid_cents, data.currency_symbol)}</div>
          </div>
          {data.invoices
            .filter((inv) => inv.shopper_id === c.shopper_id)
            .filter((inv) => filter === "all" || (inv.overdue_days || 0) > 0)
            .map((inv) => (
              <Link key={inv.id} className="row split" to={`/receipts/${inv.id}`} style={{ marginTop: 8 }}>
                <span>
                  {inv.number} <StatusTag status={inv.status} />
                  {inv.due_date ? (
                    <span className="muted">
                      {" "}
                      · {t("dueDate")} {inv.due_date}
                    </span>
                  ) : null}
                  {(inv.overdue_days || 0) > 0 ? (
                    <span className="muted">
                      {" "}
                      · {t("overdue")} {t("daysOld", { days: inv.overdue_days || 0 })}
                    </span>
                  ) : null}
                </span>
                <span className="split-amount">{money(inv.balance_cents ?? inv.total_cents, inv.currency_symbol)}</span>
              </Link>
            ))}
          {(c.notes || []).length > 0 && (
            <div className="muted" style={{ marginTop: 8 }}>
              <b>{t("followUp")}</b>
              {(c.notes || []).slice(0, 4).map((note) => (
                <div key={note.id}>
                  {when(note.created_at, locale)} · {note.body}
                  {note.promised_date ? ` · ${t("promisedDate")} ${note.promised_date}` : ""}
                </div>
              ))}
            </div>
          )}
          <form
            className="row"
            style={{ marginTop: 8 }}
            onSubmit={async (e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const fd = new FormData(form);
              const body = String(fd.get("note") || "").trim();
              if (!body) return;
              const promised = String(fd.get("promised") || "").trim();
              await api("/api/credit/notes", {
                method: "POST",
                body: JSON.stringify({ shopper_id: c.shopper_id, body, promised_date: promised || null }),
              });
              form.reset();
              await load();
            }}
          >
            <input name="note" placeholder={t("followUp")} />
            <input name="promised" type="date" aria-label={t("promisedDate")} />
            <button className="btn ghost" type="submit">
              {t("addNote")}
            </button>
          </form>
        </section>
      ))}
      </div>
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
      <PageHeader title={t("recordDamage")} />
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
              {pick(ln.item.name, ln.item.name_id)} × {formatQty(ln.quantity)}
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
              {pick(ln.name, ln.name_id)} × {formatQty(ln.quantity)}
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
      <PageHeader title={t("returnToSupplier")} />
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
              {pick(ln.item.name, ln.item.name_id)} × {formatQty(ln.quantity)}
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
              {pick(ln.name, ln.name_id)} × {formatQty(ln.quantity)}
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
    ["/credit", t("credit")],
    ["/customers", t("customerFile")],
    ["/invoices", t("invoices")],
    ["/settings", t("settings")],
    ["/shop", t("openShop")],
  ] as const;
  return (
    <div className="grid">
      <PageHeader title={t("moreOffice")} />
      <div className="more-grid">
        {links.map(([to, label]) => (
          <Link className="card more-link" key={to} to={to}>
            {label}
          </Link>
        ))}
      </div>
    </div>
  );
}

export function DueDateForm({ invoice, onSaved }: { invoice: Invoice; onSaved: (inv: Invoice) => void }) {
  const { t } = useI18n();
  const [due, setDue] = useState(invoice.due_date || "");
  const [error, setError] = useState("");
  useEffect(() => {
    setDue(invoice.due_date || "");
  }, [invoice.id, invoice.due_date]);
  if (invoice.status === "void") return null;
  return (
    <form
      className="row"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!due) return;
        setError("");
        try {
          onSaved(await api<Invoice>(`/api/invoices/${invoice.id}/due`, { method: "PATCH", body: JSON.stringify({ due_date: due }) }));
        } catch (err) {
          setError(err instanceof Error ? err.message : t("couldNotAdd"));
        }
      }}
    >
      <label>
        {t("dueDate")}
        <input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
      </label>
      <button className="btn ghost" type="submit">
        {t("save")}
      </button>
      {error ? <span className="banner">{error}</span> : null}
    </form>
  );
}

export function PaymentForm({ invoice, onPaid }: { invoice: Invoice; onPaid: (inv: Invoice) => void }) {
  const { t } = useI18n();
  const remaining = invoice.balance_cents ?? invoice.total_cents;
  const [amount, setAmount] = useState(String(rupiahFromCents(remaining)));
  const [error, setError] = useState("");
  if (invoice.status !== "issued" || remaining <= 0) return null;
  return (
    <form
      className="row"
      onSubmit={async (e) => {
        e.preventDefault();
        setError("");
        try {
          onPaid(
            await api<Invoice>(`/api/invoices/${invoice.id}/pay`, {
              method: "POST",
              body: JSON.stringify({ amount_cents: centsFromRupiah(amount) }),
            }),
          );
        } catch (err) {
          setError(err instanceof Error ? err.message : t("couldNotAdd"));
        }
      }}
    >
      <label>
        {t("payAmount")}
        <input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="numeric" />
      </label>
      <button className="btn ghost" type="submit">
        {t("recordPayment")}
      </button>
      <span className="muted">
        {t("remaining")} {money(remaining)}
        {(invoice.amount_paid_cents || 0) > 0 ? ` · ${t("alreadyPaid")} ${money(invoice.amount_paid_cents || 0)}` : ""}
      </span>
      {error ? <span className="banner">{error}</span> : null}
    </form>
  );
}
