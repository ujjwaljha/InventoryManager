import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { InvoiceSheet } from "../components/ui";
import { money, when } from "../money";
import type { Invoice, Item, Movement, Settings } from "../types";

export function OpItemDetail() {
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
      setError(e instanceof Error ? e.message : "Movement failed");
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
        sku: fd.get("sku"),
        description: fd.get("description"),
        unit_price_cents: Math.round(Number(fd.get("price")) * 100),
        unit_cost_cents: Math.round(Number(fd.get("cost")) * 100),
        reorder_point: Number(fd.get("reorder")),
        notes: fd.get("notes"),
      }),
    });
    await load();
  }

  if (!item) return <p className="muted">Loading…</p>;

  return (
    <div className="grid">
      <Link to="/items">← Items</Link>
      {error && <div className="banner">{error}</div>}
      <div className="card">
        <div className="sku">{item.sku}</div>
        <h2 style={{ margin: "4px 0" }}>{item.name}</h2>
        <p className="price" style={{ margin: 0 }}>
          On hand: {item.quantity} {item.unit}
        </p>
        {item.low_stock && <div className="stock low">Below reorder point ({item.reorder_point})</div>}
      </div>
      <form className="card form-grid" onSubmit={save}>
        <h3 style={{ margin: 0 }}>Details</h3>
        <label>
          Name
          <input name="name" defaultValue={item.name} />
        </label>
        <label>
          SKU
          <input name="sku" defaultValue={item.sku} />
        </label>
        <label>
          Description
          <textarea name="description" defaultValue={item.description} />
        </label>
        <label>
          Sell price
          <input name="price" type="number" step="0.01" defaultValue={(item.unit_price_cents / 100).toFixed(2)} />
        </label>
        <label>
          Cost
          <input name="cost" type="number" step="0.01" defaultValue={(item.unit_cost_cents / 100).toFixed(2)} />
        </label>
        <label>
          Reorder point
          <input name="reorder" type="number" defaultValue={item.reorder_point} />
        </label>
        <label>
          Notes
          <input name="notes" defaultValue={item.notes} />
        </label>
        <button className="btn" type="submit">
          Save
        </button>
      </form>
      <div className="card form-grid">
        <h3 style={{ margin: 0 }}>Stock</h3>
        <p className="muted">Sales go through Place order. Use these for deliveries, counts, and shrinkage.</p>
        <label>
          Quantity
          <input value={qty} onChange={(e) => setQty(e.target.value)} inputMode="numeric" />
        </label>
        <label>
          Reason
          <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Supplier delivery, count, breakage…" />
        </label>
        <div className="row">
          <button className="btn" type="button" onClick={() => move("in")}>
            Receive in
          </button>
          <button className="btn ghost" type="button" onClick={() => move("adjust")}>
            Set count
          </button>
          <button className="btn warn" type="button" onClick={() => move("out")}>
            Shrinkage
          </button>
        </div>
      </div>
      <div className="card">
        <h3>History</h3>
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Kind</th>
              <th>Delta</th>
              <th>After</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {moves.map((m) => (
              <tr key={m.id}>
                <td>{when(m.created_at)}</td>
                <td>{m.kind}</td>
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
        Archive item
      </button>
    </div>
  );
}

export function OpNewItem() {
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
          description: fd.get("description") || "",
          quantity: Number(fd.get("quantity") || 0),
          unit: fd.get("unit") || "ea",
          reorder_point: Number(fd.get("reorder") || 0),
          unit_price_cents: Math.round(Number(fd.get("price") || 0) * 100),
          unit_cost_cents: Math.round(Number(fd.get("cost") || 0) * 100),
        }),
      });
      nav(`/items/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create");
    }
  }
  return (
    <form className="card form-grid" onSubmit={onSubmit}>
      <h2 style={{ margin: 0 }}>New item</h2>
      {error && <div className="banner">{error}</div>}
      <label>
        SKU
        <input name="sku" required />
      </label>
      <label>
        Name
        <input name="name" required />
      </label>
      <label>
        Description
        <textarea name="description" />
      </label>
      <label>
        Opening quantity
        <input name="quantity" type="number" defaultValue={0} />
      </label>
      <label>
        Unit
        <input name="unit" defaultValue="ea" />
      </label>
      <label>
        Sell price
        <input name="price" type="number" step="0.01" defaultValue={0} />
      </label>
      <label>
        Cost
        <input name="cost" type="number" step="0.01" defaultValue={0} />
      </label>
      <label>
        Reorder point
        <input name="reorder" type="number" defaultValue={0} />
      </label>
      <button className="btn" type="submit">
        Create
      </button>
    </form>
  );
}

export function OpInvoiceDetail() {
  const { id } = useParams();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [error, setError] = useState("");
  async function load() {
    setInvoice(await api<Invoice>(`/api/invoices/${id}`));
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [id]);
  if (!invoice) return <p className="muted">{error || "Loading…"}</p>;
  return (
    <div className="grid">
      <div className="row no-print">
        <Link to="/invoices">← Invoices</Link>
        <button className="btn ghost" onClick={() => window.print()}>
          Print
        </button>
        {invoice.status === "issued" && (
          <button
            className="btn"
            onClick={async () => {
              await api(`/api/invoices/${id}/mark-paid`, { method: "POST" });
              await load();
            }}
          >
            Mark paid
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
            Cancel order
          </button>
        )}
      </div>
      <InvoiceSheet invoice={invoice} />
    </div>
  );
}

export function OpSettings() {
  const [s, setS] = useState<Settings | null>(null);
  const [lan, setLan] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    api<Settings>("/api/settings").then(setS);
    api<{ lan_host: string }>("/api/lan").then((r) => setLan(`http://${r.lan_host}:8000/shop`));
  }, []);
  if (!s) return <p className="muted">Loading…</p>;
  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const next = await api<Settings>("/api/settings", {
      method: "PATCH",
      body: JSON.stringify({
        name: fd.get("name"),
        address: fd.get("address"),
        phone: fd.get("phone"),
        currency_symbol: fd.get("currency_symbol"),
        tax_rate_bps: Math.round(Number(fd.get("tax") || 0) * 100),
      }),
    });
    setS(next);
    setSaved(true);
  }
  return (
    <div className="grid">
      <h2 style={{ margin: 0 }}>Shop settings</h2>
      <div className="card">
        <h3>Phone access</h3>
        <p className="muted">On the same Wi‑Fi, open this address in the phone browser:</p>
        <b>{lan || "http://localhost:8000/shop"}</b>
      </div>
      <form className="card form-grid" onSubmit={onSubmit}>
        <label>
          Shop name
          <input name="name" defaultValue={s.name} />
        </label>
        <label>
          Address
          <input name="address" defaultValue={s.address} />
        </label>
        <label>
          Phone
          <input name="phone" defaultValue={s.phone} />
        </label>
        <label>
          Currency symbol
          <input name="currency_symbol" defaultValue={s.currency_symbol} />
        </label>
        <label>
          Tax %
          <input name="tax" type="number" step="0.01" defaultValue={(s.tax_rate_bps / 100).toFixed(2)} />
        </label>
        <button className="btn" type="submit">
          Save
        </button>
        {saved && <span className="muted">Saved.</span>}
      </form>
      <div className="row">
        <a className="btn ghost" href="/api/export/items.csv">
          Export items CSV
        </a>
        <a className="btn ghost" href="/api/backup">
          Download SQLite backup
        </a>
      </div>
    </div>
  );
}
