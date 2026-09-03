import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { PageHeader, StatusTag } from "../components/ui";
import { useI18n } from "../i18n";
import { formatQty, marginPct, money, monthStart, todayInput, unitLabel, weekStartMonday } from "../money";
import type { Movement, ReportPerson, SalesReport, Settings, Shopper, StockReport } from "../types";

function downloadCsv(filename: string, headers: string[], rows: (string | number)[][]) {
  const esc = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`;
  const text = [headers, ...rows].map((row) => row.map(esc).join(",")).join("\n");
  const blob = new Blob([`\ufeff${text}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function DateRange({
  from,
  to,
  shopToday,
  onFrom,
  onTo,
  onPreset,
  onLoad,
}: {
  from: string;
  to: string;
  shopToday: string;
  onFrom: (v: string) => void;
  onTo: (v: string) => void;
  onPreset: (from: string, to: string) => void;
  onLoad: () => void;
}) {
  const { t } = useI18n();
  const weekFrom = weekStartMonday(shopToday);
  const monthFrom = monthStart(shopToday);
  const preset =
    from === shopToday && to === shopToday
      ? "today"
      : from === weekFrom && to === shopToday
        ? "week"
        : from === monthFrom && to === shopToday
          ? "month"
          : "";
  return (
    <div className="grid">
      <div className="chips">
        <button className={`chip ${preset === "today" ? "on" : ""}`} type="button" onClick={() => onPreset(shopToday, shopToday)}>
          {t("today")}
        </button>
        <button className={`chip ${preset === "week" ? "on" : ""}`} type="button" onClick={() => onPreset(weekFrom, shopToday)}>
          {t("thisWeek")}
        </button>
        <button className={`chip ${preset === "month" ? "on" : ""}`} type="button" onClick={() => onPreset(monthFrom, shopToday)}>
          {t("thisMonth")}
        </button>
      </div>
      <form
        className="row"
        onSubmit={(e) => {
          e.preventDefault();
          onLoad();
        }}
      >
        <label>
          {t("dateFrom")}
          <input type="date" value={from} onChange={(e) => onFrom(e.target.value)} />
        </label>
        <label>
          {t("dateTo")}
          <input type="date" value={to} onChange={(e) => onTo(e.target.value)} />
        </label>
        <button className="btn" type="submit">
          {t("continue")}
        </button>
      </form>
    </div>
  );
}

export function ReportsPage() {
  const { t, pick, locale } = useI18n();
  const [params, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState<"daily" | "items" | "cats" | "people" | "tax" | "stock" | "ledger">("daily");
  const [peopleSort, setPeopleSort] = useState<"sales" | "collected">("sales");
  const [purpose, setPurpose] = useState("");
  const [shopToday, setShopToday] = useState(todayInput);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [sales, setSales] = useState<SalesReport | null>(null);
  const [stock, setStock] = useState<StockReport | null>(null);
  const [ledger, setLedger] = useState<Movement[]>([]);
  const [error, setError] = useState("");
  const [shopperId, setShopperId] = useState<number | "">(() => {
    const v = params.get("shopper_id");
    const n = Number(v);
    return v && Number.isFinite(n) && n > 0 ? n : "";
  });
  const [shoppers, setShoppers] = useState<Shopper[]>([]);

  function chooseShopper(id: number | "") {
    setShopperId(id);
    const next = new URLSearchParams(params);
    if (id === "") next.delete("shopper_id");
    else next.set("shopper_id", String(id));
    setSearchParams(next, { replace: true });
  }

  useEffect(() => {
    api<Settings>("/api/settings")
      .then((s) => {
        const day = s.shop_today || todayInput();
        setShopToday(day);
        setFrom(day);
        setTo(day);
      })
      .catch(() => {
        const day = todayInput();
        setShopToday(day);
        setFrom(day);
        setTo(day);
      });
  }, []);

  useEffect(() => {
    api<Shopper[]>("/api/shoppers")
      .then(setShoppers)
      .catch(() => undefined);
  }, []);

  async function loadSales(dateFrom = from, dateTo = to) {
    setError("");
    const q = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
    if (shopperId !== "") q.set("shopper_id", String(shopperId));
    setSales(await api<SalesReport>(`/api/reports/pnl?${q}`));
    api<Shopper[]>("/api/shoppers").then(setShoppers).catch(() => undefined);
  }

  async function load() {
    if (!from && tab !== "stock") return;
    try {
      if (tab === "stock") setStock(await api<StockReport>("/api/reports/stock"));
      else if (tab === "ledger") {
        const q = new URLSearchParams({ limit: "200" });
        if (from) q.set("date_from", from);
        if (to) q.set("date_to", to);
        if (purpose) q.set("purpose", purpose);
        setLedger(await api<Movement[]>(`/api/reports/ledger?${q}`));
      } else await loadSales();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("couldNotAdd"));
    }
  }

  useEffect(() => {
    load();
  }, [tab, from, to, purpose, shopperId]);

  function exportCurrent() {
    if (!sales || tab === "stock" || tab === "ledger") return;
    const moneyCols = [t("revenue"), t("cogs"), t("profit"), t("margin")];
    const writeoffCols = [t("writeoffs"), t("adjustedProfit")];
    const cust = shopperId === "" ? "" : `-c${shopperId}`;
    if (tab === "cats") {
      downloadCsv(
        `report-categories-${from}-${to}${cust}.csv`,
        [t("category"), t("qtySold"), ...moneyCols, ...writeoffCols],
        sales.categories.map((r) => [
          pick(r.name, r.name_id),
          formatQty(r.quantity),
          r.revenue_cents,
          r.cogs_cents,
          r.profit_cents,
          marginPct(r.margin_bps),
          r.writeoff_cents ?? 0,
          r.adjusted_profit_cents ?? r.profit_cents,
        ]),
      );
      return;
    }
    if (tab === "tax") {
      downloadCsv(
        `report-tax-${from}-${to}${cust}.csv`,
        [t("receipts"), t("customer"), t("phone"), t("subtotal"), t("tax"), t("total")],
        sales.receipts.map((inv) => [inv.number, inv.shopper_name, inv.shopper_phone, inv.subtotal_cents, inv.tax_cents, inv.total_cents]),
      );
      return;
    }
    if (tab === "people") {
      downloadCsv(
        `report-salespeople-${from}-${to}${cust}.csv`,
        [t("salesperson"), t("receipts"), ...moneyCols, t("collected")],
        (sales.salespeople || []).map((r) => [r.name || t("unnamedStaff"), r.receipt_count, r.revenue_cents, r.cogs_cents, r.profit_cents, marginPct(r.margin_bps), r.collected_cents ?? 0]),
      );
      downloadCsv(
        `report-customers-${from}-${to}${cust}.csv`,
        [t("customer"), t("phone"), t("receipts"), ...moneyCols, t("collected")],
        (sales.customers || []).map((r) => [r.name || t("unnamedStaff"), r.phone || "", r.receipt_count, r.revenue_cents, r.cogs_cents, r.profit_cents, marginPct(r.margin_bps), r.collected_cents ?? 0]),
      );
      return;
    }
    downloadCsv(
      `report-items-${from}-${to}${cust}.csv`,
      [t("item"), t("category"), t("qtySold"), ...moneyCols, ...writeoffCols],
      sales.items.map((r) => [
        pick(r.name, r.name_id),
        pick(r.category_name, r.category_name_id),
        formatQty(r.quantity),
        r.revenue_cents,
        r.cogs_cents,
        r.profit_cents,
        marginPct(r.margin_bps),
        r.writeoff_cents ?? 0,
        r.adjusted_profit_cents ?? r.profit_cents,
      ]),
    );
  }

  const cash = sales?.cash_cents ?? 0;
  const credit = sales?.credit_cents ?? 0;

  return (
    <div className="grid">
      <PageHeader title={t("reports")} hint={t("reportsHint")} />
      <div className="chips">
        {(["daily", "items", "cats", "people", "tax", "stock", "ledger"] as const).map((key) => (
          <button key={key} className={`chip ${tab === key ? "on" : ""}`} type="button" onClick={() => setTab(key)}>
            {key === "daily"
              ? t("dailySales")
              : key === "items"
                ? t("itemPnl")
                : key === "cats"
                  ? t("categoryReport")
                  : key === "people"
                    ? t("peopleReport")
                    : key === "tax"
                      ? t("taxReport")
                      : key === "stock"
                        ? t("stockReport")
                        : t("ledger")}
          </button>
        ))}
      </div>
      {tab !== "stock" && (
        <>
          <DateRange
            from={from}
            to={to}
            shopToday={shopToday}
            onFrom={setFrom}
            onTo={setTo}
            onPreset={(nextFrom, nextTo) => {
              setFrom(nextFrom);
              setTo(nextTo);
            }}
            onLoad={load}
          />
          <label className="customer-filter">
            {t("customerReport")}
            <select
              value={shopperId === "" ? "" : String(shopperId)}
              onChange={(e) => chooseShopper(e.target.value ? Number(e.target.value) : "")}
            >
              <option value="">{t("allCustomers")}</option>
              {shoppers.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} · {s.phone}
                </option>
              ))}
            </select>
          </label>
          <p className="muted">{t("customerFilterHint")}</p>
          {sales?.shopper ? (
            <p>
              <b>{t("customerReport")}:</b> {sales.shopper.name} · {sales.shopper.phone}{" "}
              <button className="linkish" type="button" onClick={() => chooseShopper("")}>
                {t("allCustomers")}
              </button>
            </p>
          ) : null}
        </>
      )}
      {error && <div className="banner">{error}</div>}
      {tab !== "stock" && tab !== "ledger" && sales && (
        <>
          <div className="row">
            <div className="card kpi">
              {t("revenue")}
              <b>{money(sales.revenue_cents)}</b>
            </div>
            <div className="card kpi">
              {t("tax")}
              <b>{money(sales.tax_cents ?? 0)}</b>
              <span className="muted">
                {t("taxableSales")} {money(sales.subtotal_cents ?? 0)}
                {sales.tax_bps ? ` · ${(sales.tax_bps / 100).toFixed(2)}%` : ""}
              </span>
            </div>
            <div className="card kpi">
              {t("cash")}
              <b>{money(cash)}</b>
              <span className="muted">{sales.paid_count ?? 0}</span>
            </div>
            <div className="card kpi">
              {t("onAccount")}
              <b>{money(credit)}</b>
              <span className="muted">{sales.unpaid_count ?? 0}</span>
            </div>
            <div className="card kpi">
              {t("collected")}
              <b>{money(sales.collected_cents ?? 0)}</b>
              <span className="muted">{sales.collected_count ?? 0}</span>
            </div>
            <div className="card kpi">
              {t("cogs")}
              <b>{money(sales.cogs_cents)}</b>
            </div>
            <div className="card kpi">
              {t("profit")}
              <b>{money(sales.profit_cents)}</b>
            </div>
            <div className="card kpi">
              {t("margin")}
              <b>{marginPct(sales.margin_bps)}</b>
            </div>
            <div className="card kpi">
              {t("writeoffs")}
              <b>{money(sales.writeoff_cents ?? 0)}</b>
              <span className="muted">
                {t("damageCost")} {money(sales.damage_cents ?? 0)} · {t("supplierReturnCost")}{" "}
                {money(sales.supplier_return_cents ?? 0)}
              </span>
            </div>
            <div className="card kpi">
              {t("adjustedProfit")}
              <b>{money(sales.adjusted_profit_cents ?? sales.profit_cents)}</b>
              <span className="muted">{marginPct(sales.adjusted_margin_bps ?? sales.margin_bps)}</span>
            </div>
            <div className="card kpi">
              {t("voidedSales")}
              <b>{money(sales.voided_cents ?? 0)}</b>
              <span className="muted">{sales.voided_count ?? 0}</span>
            </div>
          </div>
          <p className="muted">{t("cashCreditHint")}</p>
          <p className="muted">{t("writeoffHint")}</p>
          <p className="muted">{t("taxHint")}</p>
          <button className="btn ghost" type="button" onClick={exportCurrent}>
            {t("exportReport")}
          </button>
          {tab === "tax" && (
            <>
              <h3>{t("taxReport")}</h3>
              {sales.receipts.length === 0 && <p className="muted">{t("noRows")}</p>}
              <div className="card" style={{ overflowX: "auto" }}>
                <table>
                  <thead>
                    <tr>
                      <th>{t("receipts")}</th>
                      <th>{t("customer")}</th>
                      <th>{t("subtotal")}</th>
                      <th>{t("tax")}</th>
                      <th>{t("total")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sales.receipts.map((inv) => (
                      <tr key={inv.id}>
                        <td>
                          <Link to={`/receipts/${inv.id}`}>{inv.number}</Link> <StatusTag status={inv.status} />
                        </td>
                        <td className="muted">
                          {inv.shopper_name} · {inv.shopper_phone}
                        </td>
                        <td>{money(inv.subtotal_cents)}</td>
                        <td>{money(inv.tax_cents)}</td>
                        <td>{money(inv.total_cents)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
          {tab === "daily" && (
            <>
              <h3>{t("receipts")}</h3>
              {sales.receipts.length === 0 && <p className="muted">{t("noRows")}</p>}
              {sales.receipts.map((inv) => (
                <Link className="card row" key={inv.id} to={`/receipts/${inv.id}`} style={{ justifyContent: "space-between" }}>
                  <div>
                    <b>{inv.number}</b> <StatusTag status={inv.status} />
                    <div className="muted">
                      {inv.shopper_name} · {inv.shopper_phone}
                    </div>
                  </div>
                  <div className="price">{money(inv.total_cents)}</div>
                </Link>
              ))}
              <h3>{t("itemsSold")}</h3>
            </>
          )}
          {(tab === "daily" || tab === "items") && (
            <div className="card" style={{ overflowX: "auto" }}>
              {sales.items.length === 0 && <p className="muted">{t("noRows")}</p>}
              <table>
                <thead>
                  <tr>
                    <th>{t("item")}</th>
                    <th>{t("category")}</th>
                    <th>{t("qtySold")}</th>
                    <th>{t("revenue")}</th>
                    <th>{t("cogs")}</th>
                    <th>{t("profit")}</th>
                    <th>{t("margin")}</th>
                    <th>{t("writeoffs")}</th>
                    <th>{t("adjustedProfit")}</th>
                  </tr>
                </thead>
                <tbody>
                  {sales.items.map((row) => (
                    <tr key={row.sku}>
                      <td>{pick(row.name, row.name_id)}</td>
                      <td className="muted">{pick(row.category_name, row.category_name_id)}</td>
                      <td>{formatQty(row.quantity)}</td>
                      <td>{money(row.revenue_cents)}</td>
                      <td>{money(row.cogs_cents)}</td>
                      <td>{money(row.profit_cents)}</td>
                      <td>{marginPct(row.margin_bps)}</td>
                      <td>{money(row.writeoff_cents ?? 0)}</td>
                      <td>{money(row.adjusted_profit_cents ?? row.profit_cents)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {tab === "cats" && (
            <div className="card" style={{ overflowX: "auto" }}>
              {sales.categories.length === 0 && <p className="muted">{t("noRows")}</p>}
              <table>
                <thead>
                  <tr>
                    <th>{t("category")}</th>
                    <th>{t("qtySold")}</th>
                    <th>{t("revenue")}</th>
                    <th>{t("cogs")}</th>
                    <th>{t("profit")}</th>
                    <th>{t("margin")}</th>
                    <th>{t("writeoffs")}</th>
                    <th>{t("adjustedProfit")}</th>
                  </tr>
                </thead>
                <tbody>
                  {sales.categories.map((row) => (
                    <tr key={String(row.category_id)}>
                      <td>{pick(row.name, row.name_id)}</td>
                      <td>{formatQty(row.quantity)}</td>
                      <td>{money(row.revenue_cents)}</td>
                      <td>{money(row.cogs_cents)}</td>
                      <td>{money(row.profit_cents)}</td>
                      <td>{marginPct(row.margin_bps)}</td>
                      <td>{money(row.writeoff_cents ?? 0)}</td>
                      <td>{money(row.adjusted_profit_cents ?? row.profit_cents)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {tab === "people" && (
            <>
              <p className="muted">{t("peopleHint")}</p>
              <div className="chips">
                <button className={`chip ${peopleSort === "sales" ? "on" : ""}`} type="button" onClick={() => setPeopleSort("sales")}>
                  {t("sortBySales")}
                </button>
                <button className={`chip ${peopleSort === "collected" ? "on" : ""}`} type="button" onClick={() => setPeopleSort("collected")}>
                  {t("sortByCollected")}
                </button>
              </div>
              <h3>{t("salespeople")}</h3>
              <PeopleTable rows={sales.salespeople || []} unnamed={t("unnamedStaff")} sortBy={peopleSort} />
              <h3>{t("topCustomers")}</h3>
              <PeopleTable
                rows={sales.customers || []}
                unnamed={t("unnamedStaff")}
                customers
                sortBy={peopleSort}
                onPick={(id) => {
                  chooseShopper(id);
                  setTab("daily");
                }}
              />
            </>
          )}
        </>
      )}
      {tab === "stock" && stock && (
        <div className="card" style={{ overflowX: "auto" }}>
          <div className="row">
            <div className="kpi">
              {t("stockValue")}
              <b>{money(stock.inventory_value_cents)}</b>
            </div>
            <button
              className="btn ghost"
              type="button"
              onClick={() =>
                downloadCsv(
                  "report-stock.csv",
                  [t("sku"), t("name"), t("category"), t("qty"), t("fifoCogs"), t("sellPrice"), t("stockValue")],
                  stock.items.map((i) => [
                    i.sku,
                    pick(i.name, i.name_id),
                    pick(i.category_name || "", i.category_name_id),
                    formatQty(i.quantity),
                    i.fifo_cogs_cents || i.unit_cost_cents,
                    i.unit_price_cents,
                    i.inventory_value_cents || 0,
                  ]),
                )
              }
            >
              {t("exportReport")}
            </button>
          </div>
          <table>
            <thead>
              <tr>
                <th>{t("sku")}</th>
                <th>{t("name")}</th>
                <th>{t("category")}</th>
                <th>{t("qty")}</th>
                <th>{t("fifoCogs")}</th>
                <th>{t("sellPrice")}</th>
                <th>{t("stockValue")}</th>
                <th>{t("potentialMargin")}</th>
              </tr>
            </thead>
            <tbody>
              {stock.items.map((i) => (
                <tr key={i.id}>
                  <td className="sku">{i.sku}</td>
                  <td>
                    <Link to={`/items/${i.id}`}>{pick(i.name, i.name_id)}</Link>
                  </td>
                  <td className="muted">{pick(i.category_name || "", i.category_name_id)}</td>
                  <td>
                    {formatQty(i.quantity)} {unitLabel(i.unit, locale)}
                  </td>
                  <td>{money(i.fifo_cogs_cents || i.unit_cost_cents)}</td>
                  <td>{money(i.unit_price_cents)}</td>
                  <td>{money(i.inventory_value_cents || 0)}</td>
                  <td>{marginPct(i.unit_price_cents ? Math.round(((i.unit_price_cents - (i.fifo_cogs_cents || 0)) * 10000) / i.unit_price_cents) : 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {tab === "ledger" && (
        <div className="card" style={{ overflowX: "auto" }}>
          <div className="chips" style={{ marginBottom: 12 }}>
            {["", "sale", "purchase", "damage", "supplier_return", "cancel"].map((key) => (
              <button key={key || "all"} className={`chip ${purpose === key ? "on" : ""}`} type="button" onClick={() => setPurpose(key)}>
                {key ? t(`purpose_${key}` as "purpose_sale") : t("all")}
              </button>
            ))}
            <button
              className="btn ghost"
              type="button"
              onClick={() =>
                downloadCsv(
                  `report-ledger-${from}-${to}.csv`,
                  [t("when"), t("item"), t("kind"), t("delta"), t("cogs"), t("reason")],
                  ledger.map((m) => [
                    m.created_at,
                    pick(m.item_name || "", m.item_name_id),
                    m.purpose || m.kind,
                    formatQty(m.quantity_delta),
                    m.cogs_cents || 0,
                    m.reason || "",
                  ]),
                )
              }
            >
              {t("exportReport")}
            </button>
          </div>
          <table>
            <thead>
              <tr>
                <th>{t("when")}</th>
                <th>{t("item")}</th>
                <th>{t("kind")}</th>
                <th>{t("delta")}</th>
                <th>{t("cogs")}</th>
                <th>{t("reason")}</th>
              </tr>
            </thead>
            <tbody>
              {ledger.map((m) => (
                <tr key={m.id}>
                  <td>{m.created_at.replace("T", " ").slice(0, 16)}</td>
                  <td>{pick(m.item_name || "", m.item_name_id)}</td>
                  <td>{m.purpose || m.kind}</td>
                  <td>{formatQty(m.quantity_delta)}</td>
                  <td>{money(m.cogs_cents || 0)}</td>
                  <td className="muted">{m.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function PeopleTable({
  rows,
  unnamed,
  customers = false,
  sortBy = "sales",
  onPick,
}: {
  rows: ReportPerson[];
  unnamed: string;
  customers?: boolean;
  sortBy?: "sales" | "collected";
  onPick?: (id: number) => void;
}) {
  const { t } = useI18n();
  const ranked = [...rows].sort((a, b) =>
    sortBy === "collected" ? (b.collected_cents ?? 0) - (a.collected_cents ?? 0) : b.revenue_cents - a.revenue_cents,
  );
  if (!ranked.length) return <p className="muted">{t("noRows")}</p>;
  return (
    <div className="card" style={{ overflowX: "auto" }}>
      <table>
        <thead>
          <tr>
            <th>{customers ? t("customer") : t("salesperson")}</th>
            {customers ? <th>{t("phone")}</th> : null}
            <th>{t("receipts")}</th>
            <th>{t("revenue")}</th>
            <th>{t("collected")}</th>
            <th>{t("cogs")}</th>
            <th>{t("profit")}</th>
            <th>{t("margin")}</th>
          </tr>
        </thead>
        <tbody>
          {ranked.map((row) => (
            <tr key={customers ? String(row.shopper_id) : row.name || unnamed}>
              <td>
                {customers && onPick && row.shopper_id ? (
                  <button className="linkish" type="button" onClick={() => onPick(row.shopper_id!)} title={t("viewCustomerReport")}>
                    {row.name || unnamed}
                  </button>
                ) : (
                  row.name || unnamed
                )}
              </td>
              {customers ? <td className="muted">{row.phone}</td> : null}
              <td>{row.receipt_count}</td>
              <td>{money(row.revenue_cents)}</td>
              <td>{money(row.collected_cents ?? 0)}</td>
              <td>{money(row.cogs_cents)}</td>
              <td>{money(row.profit_cents)}</td>
              <td>{marginPct(row.margin_bps)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
