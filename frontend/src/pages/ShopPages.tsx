import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { IdentifyForm } from "../components/ui";
import { money } from "../money";
import type { Item, PurchaseOrder, Shopper } from "../types";

export function ShopHome({
  shopper,
  onIdentified,
  onCartChange,
}: {
  shopper: Shopper | null;
  onIdentified: (s: Shopper) => void;
  onCartChange: () => void;
}) {
  const [items, setItems] = useState<Item[]>([]);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState<string>("all");
  const [error, setError] = useState("");
  const [identify, setIdentify] = useState(false);
  const [pendingItem, setPendingItem] = useState<Item | null>(null);

  useEffect(() => {
    api<Item[]>("/api/shop/catalog").then(setItems).catch((e) => setError(String(e.message)));
  }, []);

  const categories = useMemo(() => {
    const names = Array.from(new Set(items.map((i) => i.category_name).filter(Boolean))) as string[];
    names.sort();
    return names;
  }, [items]);

  const shown = items.filter((i) => {
    if (cat !== "all" && i.category_name !== cat) return false;
    if (!q.trim()) return true;
    const n = q.toLowerCase();
    return i.name.toLowerCase().includes(n) || i.sku.toLowerCase().includes(n);
  });

  async function add(item: Item) {
    setError("");
    if (!shopper) {
      setPendingItem(item);
      setIdentify(true);
      return;
    }
    try {
      await api("/api/shop/po/lines", {
        method: "POST",
        body: JSON.stringify({ item_id: item.id, quantity: 1 }),
      });
      onCartChange();
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setPendingItem(item);
        setIdentify(true);
        return;
      }
      setError(e instanceof Error ? e.message : "Could not add");
    }
  }

  async function identifyAndAdd(name: string, phone: string) {
    const s = await api<Shopper>("/api/shop/session", {
      method: "POST",
      body: JSON.stringify({ name, phone }),
    });
    onIdentified(s);
    setIdentify(false);
    if (pendingItem) {
      await api("/api/shop/po/lines", {
        method: "POST",
        body: JSON.stringify({ item_id: pendingItem.id, quantity: 1 }),
      });
      setPendingItem(null);
      onCartChange();
    }
  }

  return (
    <div>
      <input className="search" placeholder="Search atta, oil, soap…" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="chips" style={{ margin: "12px 0" }}>
        <button className={`chip ${cat === "all" ? "on" : ""}`} onClick={() => setCat("all")}>
          All
        </button>
        {categories.map((c) => (
          <button key={c} className={`chip ${cat === c ? "on" : ""}`} onClick={() => setCat(c)}>
            {c}
          </button>
        ))}
      </div>
      {error && <div className="banner">{error}</div>}
      {identify && <IdentifyForm onDone={identifyAndAdd} />}
      <div className="cards">
        {shown.map((item) => (
          <article className="card" key={item.id}>
            <div className="sku">{item.sku}</div>
            <h3 style={{ margin: "4px 0 8px" }}>{item.name}</h3>
            <p className="muted" style={{ minHeight: 40 }}>
              {item.description}
            </p>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <div className="price">{money(item.unit_price_cents)}</div>
                <div className={`stock ${item.quantity === 0 ? "out" : item.low_stock ? "low" : ""}`}>
                  {item.quantity === 0 ? "Sold out" : `${item.quantity} ${item.unit} in stock`}
                </div>
              </div>
              <button className="btn" disabled={item.quantity < 1} onClick={() => add(item)}>
                Add
              </button>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

export function ShopCart({
  shopper,
  onIdentified,
  onCartChange,
}: {
  shopper: Shopper | null;
  onIdentified: (s: Shopper) => void;
  onCartChange: () => void;
}) {
  const [po, setPo] = useState<PurchaseOrder | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  async function load() {
    if (!shopper) return;
    const draft = await api<PurchaseOrder>("/api/shop/po");
    setPo(draft);
    setNote(draft.note || "");
    onCartChange();
  }

  useEffect(() => {
    if (shopper) load().catch((e) => setError(e.message));
  }, [shopper]);

  async function setQty(itemId: number, quantity: number) {
    setError("");
    try {
      if (quantity <= 0) {
        const next = await api<PurchaseOrder>(`/api/shop/po/lines/${itemId}`, { method: "DELETE" });
        setPo(next);
      } else {
        const next = await api<PurchaseOrder>("/api/shop/po/lines", {
          method: "POST",
          body: JSON.stringify({ item_id: itemId, quantity }),
        });
        setPo(next);
      }
      onCartChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
      if (e instanceof ApiError && e.shortages.length) {
        setError(`${e.shortages[0].name}: only ${e.shortages[0].available} left`);
      }
    }
  }

  async function place() {
    setBusy(true);
    setError("");
    try {
      const placed = await api<PurchaseOrder>("/api/shop/po/place", {
        method: "POST",
        body: JSON.stringify({ note }),
      });
      onCartChange();
      if (placed.invoice) navigate(`/shop/invoices/${placed.invoice.id}`);
    } catch (e) {
      if (e instanceof ApiError && e.shortages.length) {
        setError(
          e.shortages.map((s) => `${s.name}: need ${s.requested}, have ${s.available}`).join(" · "),
        );
      } else {
        setError(e instanceof Error ? e.message : "Could not place order");
      }
    } finally {
      setBusy(false);
    }
  }

  if (!shopper) {
    return <IdentifyForm onDone={(name, phone) => api<Shopper>("/api/shop/session", { method: "POST", body: JSON.stringify({ name, phone }) }).then(onIdentified)} />;
  }

  if (!po || po.lines.length === 0) {
    return (
      <div className="card">
        <h2>Your purchase order is empty</h2>
        <p className="muted">Add items from the shop. Stock is held only when you place the order.</p>
        <Link className="btn" to="/shop" style={{ display: "inline-block" }}>
          Browse shop
        </Link>
      </div>
    );
  }

  return (
    <div className="grid">
      <div>
        <div className="sku">Purchase order</div>
        <h2 style={{ margin: "4px 0 12px" }}>{po.number}</h2>
      </div>
      {error && <div className="banner">{error}</div>}
      {po.lines.map((ln) => (
        <div className="card row" key={ln.id} style={{ justifyContent: "space-between" }}>
          <div>
            <b>{ln.name}</b>
            <div className="sku">{ln.sku}</div>
            <div className="muted">{money(ln.unit_price_cents, po.currency_symbol)} each</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div className="stepper">
              <button className="icon-btn" onClick={() => setQty(ln.item_id, ln.quantity - 1)}>
                −
              </button>
              <b>{ln.quantity}</b>
              <button className="icon-btn" onClick={() => setQty(ln.item_id, ln.quantity + 1)}>
                +
              </button>
            </div>
            <div className="price">{money(ln.line_total_cents, po.currency_symbol)}</div>
          </div>
        </div>
      ))}
      <label className="muted">
        Note for the shop
        <input className="search" style={{ marginTop: 6 }} value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span>Subtotal</span>
          <span>{money(po.subtotal_cents, po.currency_symbol)}</span>
        </div>
        {po.tax_cents > 0 && (
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span>Tax</span>
            <span>{money(po.tax_cents, po.currency_symbol)}</span>
          </div>
        )}
        <div className="row" style={{ justifyContent: "space-between", marginTop: 8 }}>
          <b>Total</b>
          <b className="price">{money(po.total_cents, po.currency_symbol)}</b>
        </div>
        <p className="muted">Placing this order will take items off the shelf and raise an invoice.</p>
        <button className="btn terra block" disabled={busy} onClick={place}>
          {busy ? "Placing…" : "Place order & raise invoice"}
        </button>
      </div>
    </div>
  );
}
