import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { IdentifyForm } from "../components/ui";
import { useI18n } from "../i18n";
import { money, unitLabel } from "../money";
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
  const { t, pick, locale } = useI18n();
  const [items, setItems] = useState<Item[]>([]);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState<number | "all">("all");
  const [error, setError] = useState("");
  const [identify, setIdentify] = useState(false);
  const [pendingItem, setPendingItem] = useState<Item | null>(null);

  useEffect(() => {
    api<Item[]>("/api/shop/catalog").then(setItems).catch((e) => setError(String(e.message)));
  }, []);

  const categories = useMemo(() => {
    const map = new Map<number, string>();
    for (const i of items) {
      if (i.category_id) {
        map.set(i.category_id, pick(i.category_name || "", i.category_name_id));
      }
    }
    return [...map.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [items, pick]);

  const shown = items.filter((i) => {
    if (cat !== "all" && i.category_id !== cat) return false;
    if (!q.trim()) return true;
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
      setError(e instanceof Error ? e.message : t("couldNotAdd"));
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
      <input className="search" placeholder={t("searchShop")} value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="chips" style={{ margin: "12px 0" }}>
        <button className={`chip ${cat === "all" ? "on" : ""}`} onClick={() => setCat("all")}>
          {t("all")}
        </button>
        {categories.map(([id, label]) => (
          <button key={id} className={`chip ${cat === id ? "on" : ""}`} onClick={() => setCat(id)}>
            {label}
          </button>
        ))}
      </div>
      {error && <div className="banner">{error}</div>}
      {identify && <IdentifyForm onDone={identifyAndAdd} />}
      <div className="cards">
        {shown.map((item) => (
          <article className="card" key={item.id}>
            <div className="sku">{item.sku}</div>
            <h3 style={{ margin: "4px 0 8px" }}>{pick(item.name, item.name_id)}</h3>
            <p className="muted" style={{ minHeight: 40 }}>
              {pick(item.description, item.description_id)}
            </p>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <div className="price">{money(item.unit_price_cents)}</div>
                <div className={`stock ${item.quantity === 0 ? "out" : item.low_stock ? "low" : ""}`}>
                  {item.quantity === 0
                    ? t("soldOut")
                    : t("inStock", { qty: item.quantity, unit: unitLabel(item.unit, locale) })}
                </div>
              </div>
              <button className="btn" disabled={item.quantity < 1} onClick={() => add(item)}>
                {t("add")}
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
  const { t, pick } = useI18n();
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
      if (e instanceof ApiError && e.shortages.length) {
        const s = e.shortages[0];
        setError(t("onlyLeft", { name: pick(s.name, s.name_id), available: s.available }));
      } else {
        setError(e instanceof Error ? e.message : t("updateFailed"));
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
          e.shortages
            .map((s) =>
              t("shortageLine", {
                name: pick(s.name, s.name_id),
                requested: s.requested,
                available: s.available,
              }),
            )
            .join(" · "),
        );
      } else {
        setError(e instanceof Error ? e.message : t("couldNotPlace"));
      }
    } finally {
      setBusy(false);
    }
  }

  if (!shopper) {
    return (
      <IdentifyForm
        onDone={(name, phone) =>
          api<Shopper>("/api/shop/session", { method: "POST", body: JSON.stringify({ name, phone }) }).then(onIdentified)
        }
      />
    );
  }

  if (!po || po.lines.length === 0) {
    return (
      <div className="card">
        <h2>{t("emptyPo")}</h2>
        <p className="muted">{t("emptyPoHint")}</p>
        <Link className="btn" to="/shop" style={{ display: "inline-block" }}>
          {t("browseShop")}
        </Link>
      </div>
    );
  }

  return (
    <div className="grid">
      <div>
        <div className="sku">{t("purchaseOrder")}</div>
        <h2 style={{ margin: "4px 0 12px" }}>{po.number}</h2>
      </div>
      {error && <div className="banner">{error}</div>}
      {po.lines.map((ln) => (
        <div className="card row" key={ln.id} style={{ justifyContent: "space-between" }}>
          <div>
            <b>{pick(ln.name, ln.name_id)}</b>
            <div className="sku">{ln.sku}</div>
            <div className="muted">
              {money(ln.unit_price_cents, po.currency_symbol)} {t("each")}
            </div>
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
        {t("noteForShop")}
        <input className="search" style={{ marginTop: 6 }} value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      <div className="card">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span>{t("subtotal")}</span>
          <span>{money(po.subtotal_cents, po.currency_symbol)}</span>
        </div>
        {po.tax_cents > 0 && (
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span>{t("tax")}</span>
            <span>{money(po.tax_cents, po.currency_symbol)}</span>
          </div>
        )}
        <div className="row" style={{ justifyContent: "space-between", marginTop: 8 }}>
          <b>{t("total")}</b>
          <b className="price">{money(po.total_cents, po.currency_symbol)}</b>
        </div>
        <p className="muted">{t("placeHint")}</p>
        <button className="btn terra block" disabled={busy} onClick={place}>
          {busy ? t("placing") : t("placeOrder")}
        </button>
      </div>
    </div>
  );
}
