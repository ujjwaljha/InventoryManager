import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { api } from "../api";
import { SharePanel, StatusTag } from "../components/ui";
import { type MsgKey, useI18n } from "../i18n";
import { formatQty, money, unitLabel, when } from "../money";
import type { Dashboard, Invoice, Item, ItemDeleteResult, Movement, PurchaseOrder } from "../types";

export function OpDashboard() {
  const { t, pick, locale } = useI18n();
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Dashboard>("/api/dashboard")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);
  if (error) return <div className="banner">{error}</div>;
  if (!data) return <p className="muted">{t("loading")}</p>;
  return (
    <div className="grid">
      <div>
        <div className="sku">{t("operator")}</div>
        <h2 style={{ margin: "4px 0 0" }}>{data.shop_name}</h2>
      </div>
      <SharePanel />
      <div className="row">
        <Link className="btn" to="/till">
          {t("till")}
        </Link>
        <Link className="btn ghost" to="/restock">
          {t("restock")}
        </Link>
        <Link className="btn ghost" to="/receipts">
          {t("receipts")}
        </Link>
        <Link className="btn ghost" to="/credit">
          {t("credit")}
        </Link>
        <Link className="btn ghost" to="/customers">
          {t("customerFile")}
        </Link>
        <Link className="btn ghost" to="/reports">
          {t("reports")}
        </Link>
      </div>
      <div className="row">
        <div className="card kpi">
          {t("skus")}
          <b>{data.sku_count}</b>
        </div>
        <div className="card kpi">
          {t("unitsOnHand")}
          <b>{data.units_on_hand}</b>
        </div>
        {(data.units_reserved || 0) > 0 ? (
          <Link className="card kpi" to="/orders">
            {t("unitsReserved")}
            <b>{data.units_reserved}</b>
          </Link>
        ) : null}
        <div className="card kpi">
          {t("lowStock")}
          <b>{data.low_stock_count}</b>
        </div>
        <div className="card kpi">
          {t("todaysSales")}
          <b>{money(data.today_sales_cents, data.currency_symbol)}</b>
        </div>
        <div className="card kpi">
          {t("ordersToday")}
          <b>{data.today_order_count}</b>
        </div>
        <Link className="card kpi" to="/orders">
          {t("openDrafts")}
          <b>{data.draft_po_count}</b>
        </Link>
        <Link className="card kpi" to="/credit">
          {t("unpaid")}
          <b>{data.unpaid_count ?? 0}</b>
          <span className="muted">{money(data.unpaid_cents || 0, data.currency_symbol)}</span>
        </Link>
        {(data.promises_due_count || 0) > 0 ? (
          <Link className="card kpi" to="/credit">
            {t("promiseDue")}
            <b>{data.promises_due_count}</b>
          </Link>
        ) : null}
      </div>
      <div className="cards">
        <section className="card">
          <h3>{t("lowStock")}</h3>
          {data.low_stock_items.length === 0 && <p className="muted">{t("nothingLow")}</p>}
          {data.low_stock_items.map((i) => (
            <div key={i.id} className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
              <Link to={`/items/${i.id}`}>{pick(i.name, i.name_id)}</Link>
              <span className="stock low">
                {formatQty(i.available ?? i.quantity)} / {formatQty(i.reorder_point)}
                {(i.reserved || 0) > 0 ? (
                  <div className="muted">{t("heldInCart", { qty: formatQty(i.reserved || 0) })}</div>
                ) : null}
              </span>
            </div>
          ))}
        </section>
        <section className="card">
          <h3>{t("recentMoves")}</h3>
          {data.recent_movements.map((m: Movement) => (
            <div key={m.id} className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
              <span>
                {pick(m.item_name || "", m.item_name_id)}{" "}
                <span className="sku">{t(`kind_${m.kind}` as MsgKey)}</span>
              </span>
              <span>
                {m.quantity_delta > 0 ? "+" : ""}
                {formatQty(m.quantity_delta)}
              </span>
            </div>
          ))}
        </section>
      </div>
    </div>
  );
}

export function OpItems() {
  const { t, pick, locale } = useI18n();
  const loc = useLocation();
  const [items, setItems] = useState<Item[]>([]);
  const [q, setQ] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState<number | null>(null);
  useEffect(() => {
    api<Item[]>("/api/items").then(setItems);
  }, []);
  useEffect(() => {
    const fromDetail = (loc.state as { notice?: string } | null)?.notice;
    if (fromDetail) setNotice(fromDetail);
  }, [loc.state]);
  const shown = items.filter((i) => {
    if (!q) return true;
    const n = q.toLowerCase();
    return (
      i.name.toLowerCase().includes(n) ||
      (i.name_id || "").toLowerCase().includes(n) ||
      (i.description || "").toLowerCase().includes(n) ||
      (i.description_id || "").toLowerCase().includes(n) ||
      i.sku.toLowerCase().includes(n)
    );
  });
  shown.sort((a, b) => pick(a.name, a.name_id).localeCompare(pick(b.name, b.name_id), locale === "id" ? "id" : "en"));

  async function remove(item: Item) {
    const label = pick(item.name, item.name_id);
    if (!window.confirm(t("deleteItemConfirm", { name: label }))) return;
    setError("");
    setNotice("");
    setDeletingId(item.id);
    try {
      const result = await api<ItemDeleteResult>(`/api/items/${item.id}`, { method: "DELETE" });
      setItems((rows) => rows.filter((row) => row.id !== item.id));
      setNotice(result.archived ? t("itemArchived") : t("itemDeleted"));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("updateFailed"));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="grid">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>{t("items")}</h2>
        <Link className="btn" to="/items/new">
          {t("newItem")}
        </Link>
      </div>
      {error && <div className="banner">{error}</div>}
      {notice && <div className="banner ok">{notice}</div>}
      <input className="search" placeholder={t("searchSku")} value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="card" style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>{t("sku")}</th>
              <th>{t("name")}</th>
              <th>{t("category")}</th>
              <th>{t("qty")}</th>
              <th>{t("fifoCogs")}</th>
              <th>{t("price")}</th>
              <th>{t("location")}</th>
              <th>{t("actions")}</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((i) => (
              <tr key={i.id}>
                <td className="sku">{i.sku}</td>
                <td>
                  <Link to={`/items/${i.id}`}>{pick(i.name, i.name_id)}</Link>
                  {i.low_stock && <div className="stock low">{t("lowStock")}</div>}
                </td>
                <td className="muted">{pick(i.category_name || "", i.category_name_id)}</td>
                <td>
                  {formatQty(i.available ?? i.quantity)} {unitLabel(i.unit, locale)}
                  {(i.reserved || 0) > 0 ? (
                    <div className="muted">{t("heldInCart", { qty: formatQty(i.reserved || 0) })}</div>
                  ) : (
                    <div className="muted">{money(i.fifo_cogs_cents || i.unit_cost_cents)}</div>
                  )}
                </td>
                <td>{money(i.fifo_cogs_cents || i.unit_cost_cents)}</td>
                <td>{money(i.unit_price_cents)}</td>
                <td className="muted">{pick(i.location_name || "", i.location_name_id)}</td>
                <td>
                  <div className="table-actions">
                    <Link className="btn ghost small" to={`/items/${i.id}`}>
                      {t("edit")}
                    </Link>
                    <button
                      className="btn danger-ghost small"
                      type="button"
                      disabled={deletingId === i.id}
                      onClick={() => remove(i)}
                    >
                      {t("deleteNamed")}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function OpOrders() {
  const { t, locale } = useI18n();
  const [rows, setRows] = useState<PurchaseOrder[]>([]);
  useEffect(() => {
    api<PurchaseOrder[]>("/api/orders").then(setRows);
  }, []);
  return (
    <div className="grid">
      <h2 style={{ margin: 0 }}>{t("purchaseOrders")}</h2>
      {rows.map((po) => (
        <div className="card row" key={po.id} style={{ justifyContent: "space-between" }}>
          <div>
            <b>{po.number}</b> <StatusTag status={po.status} />
            <div className="muted">
              {po.shopper_name} · {po.shopper_phone}
            </div>
            <div className="muted">{when(po.placed_at || po.created_at, locale)}</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div className="price">{money(po.total_cents, po.currency_symbol)}</div>
            {po.invoice && <Link to={`/invoices/${po.invoice.id}`}>{po.invoice.number}</Link>}
          </div>
        </div>
      ))}
    </div>
  );
}

export function OpInvoices() {
  const { t, locale } = useI18n();
  const [rows, setRows] = useState<Invoice[]>([]);
  useEffect(() => {
    api<Invoice[]>("/api/invoices").then(setRows);
  }, []);
  return (
    <div className="grid">
      <h2 style={{ margin: 0 }}>{t("invoices")}</h2>
      {rows.map((inv) => (
        <Link className="card row" key={inv.id} to={`/invoices/${inv.id}`} style={{ justifyContent: "space-between" }}>
          <div>
            <b>{inv.number}</b> <StatusTag status={inv.status} />
            <div className="muted">
              {inv.shopper_name} · {when(inv.issued_at, locale)}
            </div>
          </div>
          <div className="price">{money(inv.total_cents, inv.currency_symbol)}</div>
        </Link>
      ))}
    </div>
  );
}
