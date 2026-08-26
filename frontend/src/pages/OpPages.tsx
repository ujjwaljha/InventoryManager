import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { StatusTag } from "../components/ui";
import { money, when } from "../money";
import type { Dashboard, Invoice, Item, Movement, PurchaseOrder } from "../types";

export function OpDashboard() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Dashboard>("/api/dashboard")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);
  if (error) return <div className="banner">{error}</div>;
  if (!data) return <p className="muted">Loading…</p>;
  return (
    <div className="grid">
      <div>
        <div className="sku">Operator</div>
        <h2 style={{ margin: "4px 0 0" }}>{data.shop_name}</h2>
      </div>
      <div className="row">
        <div className="card kpi">
          SKUs
          <b>{data.sku_count}</b>
        </div>
        <div className="card kpi">
          Units on hand
          <b>{data.units_on_hand}</b>
        </div>
        <div className="card kpi">
          Low stock
          <b>{data.low_stock_count}</b>
        </div>
        <div className="card kpi">
          Today&apos;s sales
          <b>{money(data.today_sales_cents, data.currency_symbol)}</b>
        </div>
        <div className="card kpi">
          Orders today
          <b>{data.today_order_count}</b>
        </div>
      </div>
      <div className="cards">
        <section className="card">
          <h3>Low stock</h3>
          {data.low_stock_items.length === 0 && <p className="muted">Nothing below reorder point.</p>}
          {data.low_stock_items.map((i) => (
            <div key={i.id} className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
              <Link to={`/items/${i.id}`}>{i.name}</Link>
              <span className="stock low">
                {i.quantity} / {i.reorder_point}
              </span>
            </div>
          ))}
        </section>
        <section className="card">
          <h3>Recent stock moves</h3>
          {data.recent_movements.map((m: Movement) => (
            <div key={m.id} className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
              <span>
                {m.item_name} <span className="sku">{m.kind}</span>
              </span>
              <span>
                {m.quantity_delta > 0 ? "+" : ""}
                {m.quantity_delta}
              </span>
            </div>
          ))}
        </section>
      </div>
    </div>
  );
}

export function OpItems() {
  const [items, setItems] = useState<Item[]>([]);
  const [q, setQ] = useState("");
  useEffect(() => {
    api<Item[]>("/api/items").then(setItems);
  }, []);
  const shown = items.filter(
    (i) => !q || i.name.toLowerCase().includes(q.toLowerCase()) || i.sku.toLowerCase().includes(q.toLowerCase()),
  );
  return (
    <div className="grid">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ margin: 0 }}>Items</h2>
        <Link className="btn" to="/items/new">
          New item
        </Link>
      </div>
      <input className="search" placeholder="Search SKU or name" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="card" style={{ overflowX: "auto" }}>
        <table>
          <thead>
            <tr>
              <th>SKU</th>
              <th>Name</th>
              <th>Qty</th>
              <th>Price</th>
              <th>Location</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((i) => (
              <tr key={i.id}>
                <td className="sku">{i.sku}</td>
                <td>
                  <Link to={`/items/${i.id}`}>{i.name}</Link>
                  {i.low_stock && <div className="stock low">Low stock</div>}
                </td>
                <td>
                  {i.quantity} {i.unit}
                </td>
                <td>{money(i.unit_price_cents)}</td>
                <td className="muted">{i.location_name}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function OpOrders() {
  const [rows, setRows] = useState<PurchaseOrder[]>([]);
  useEffect(() => {
    api<PurchaseOrder[]>("/api/orders").then(setRows);
  }, []);
  return (
    <div className="grid">
      <h2 style={{ margin: 0 }}>Purchase orders</h2>
      {rows.map((po) => (
        <div className="card row" key={po.id} style={{ justifyContent: "space-between" }}>
          <div>
            <b>{po.number}</b> <StatusTag status={po.status} />
            <div className="muted">
              {po.shopper_name} · {po.shopper_phone}
            </div>
            <div className="muted">{when(po.placed_at || po.created_at)}</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div className="price">{money(po.total_cents, po.currency_symbol)}</div>
            {po.invoice && (
              <Link to={`/invoices/${po.invoice.id}`}>{po.invoice.number}</Link>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export function OpInvoices() {
  const [rows, setRows] = useState<Invoice[]>([]);
  useEffect(() => {
    api<Invoice[]>("/api/invoices").then(setRows);
  }, []);
  return (
    <div className="grid">
      <h2 style={{ margin: 0 }}>Invoices</h2>
      {rows.map((inv) => (
        <Link className="card row" key={inv.id} to={`/invoices/${inv.id}`} style={{ justifyContent: "space-between" }}>
          <div>
            <b>{inv.number}</b> <StatusTag status={inv.status} />
            <div className="muted">
              {inv.shopper_name} · {when(inv.issued_at)}
            </div>
          </div>
          <div className="price">{money(inv.total_cents, inv.currency_symbol)}</div>
        </Link>
      ))}
    </div>
  );
}
