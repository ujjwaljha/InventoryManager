import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useI18n } from "../i18n";
import { marginPct, money, todayInput, unitLabel } from "../money";
import type { Movement, SalesReport, StockReport } from "../types";

function DateRange({
  from,
  to,
  onFrom,
  onTo,
  onLoad,
}: {
  from: string;
  to: string;
  onFrom: (v: string) => void;
  onTo: (v: string) => void;
  onLoad: () => void;
}) {
  const { t } = useI18n();
  return (
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
  );
}

export function ReportsPage() {
  const { t, pick, locale } = useI18n();
  const today = todayInput();
  const [tab, setTab] = useState<"daily" | "items" | "cats" | "stock" | "ledger">("daily");
  const [from, setFrom] = useState(today);
  const [to, setTo] = useState(today);
  const [sales, setSales] = useState<SalesReport | null>(null);
  const [stock, setStock] = useState<StockReport | null>(null);
  const [ledger, setLedger] = useState<Movement[]>([]);
  const [error, setError] = useState("");

  async function loadSales() {
    setError("");
    const q = `date_from=${from}&date_to=${to}`;
    const path = tab === "daily" ? `/api/reports/daily?date=${from}` : `/api/reports/pnl?${q}`;
    setSales(await api<SalesReport>(path));
  }

  async function load() {
    try {
      if (tab === "stock") setStock(await api<StockReport>("/api/reports/stock"));
      else if (tab === "ledger") setLedger(await api<Movement[]>("/api/reports/ledger?limit=80"));
      else await loadSales();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("couldNotAdd"));
    }
  }

  useEffect(() => {
    load();
  }, [tab]);

  return (
    <div className="grid">
      <div>
        <h2 style={{ margin: 0 }}>{t("reports")}</h2>
        <p className="muted">{t("reportsHint")}</p>
      </div>
      <div className="chips">
        {(["daily", "items", "cats", "stock", "ledger"] as const).map((key) => (
          <button key={key} className={`chip ${tab === key ? "on" : ""}`} type="button" onClick={() => setTab(key)}>
            {key === "daily"
              ? t("dailySales")
              : key === "items"
                ? t("itemPnl")
                : key === "cats"
                  ? t("categoryReport")
                  : key === "stock"
                    ? t("stockReport")
                    : t("ledger")}
          </button>
        ))}
      </div>
      {tab !== "stock" && tab !== "ledger" && (
        <DateRange from={from} to={to} onFrom={setFrom} onTo={setTo} onLoad={load} />
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
          </div>
          {tab === "daily" && (
            <>
              <h3>{t("receipts")}</h3>
              {sales.receipts.map((inv) => (
                <Link className="card row" key={inv.id} to={`/receipts/${inv.id}`} style={{ justifyContent: "space-between" }}>
                  <div>
                    <b>{inv.number}</b>
                    <div className="muted">
                      {inv.shopper_name} · {inv.shopper_phone}
                    </div>
                  </div>
                  <div className="price">{money(inv.total_cents)}</div>
                </Link>
              ))}
              <h3>{t("itemsSoldToday")}</h3>
            </>
          )}
          {(tab === "daily" || tab === "items") && (
            <div className="card" style={{ overflowX: "auto" }}>
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
                  </tr>
                </thead>
                <tbody>
                  {sales.items.map((row) => (
                    <tr key={row.sku}>
                      <td>{pick(row.name, row.name_id)}</td>
                      <td className="muted">{pick(row.category_name, row.category_name_id)}</td>
                      <td>{row.quantity}</td>
                      <td>{money(row.revenue_cents)}</td>
                      <td>{money(row.cogs_cents)}</td>
                      <td>{money(row.profit_cents)}</td>
                      <td>{marginPct(row.margin_bps)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {tab === "cats" && (
            <div className="card" style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>{t("category")}</th>
                    <th>{t("qtySold")}</th>
                    <th>{t("revenue")}</th>
                    <th>{t("cogs")}</th>
                    <th>{t("profit")}</th>
                    <th>{t("margin")}</th>
                  </tr>
                </thead>
                <tbody>
                  {sales.categories.map((row) => (
                    <tr key={String(row.category_id)}>
                      <td>{pick(row.name, row.name_id)}</td>
                      <td>{row.quantity}</td>
                      <td>{money(row.revenue_cents)}</td>
                      <td>{money(row.cogs_cents)}</td>
                      <td>{money(row.profit_cents)}</td>
                      <td>{marginPct(row.margin_bps)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
                    {i.quantity} {unitLabel(i.unit, locale)}
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
                  <td>{m.quantity_delta}</td>
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
