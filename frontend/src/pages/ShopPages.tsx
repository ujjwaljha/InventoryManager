import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { ScanButton } from "../components/BarcodeScanner";
import { IdentifyForm, SalesAgentSelect } from "../components/ui";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { formatQty, money, qtyStep, unitLabel } from "../money";
import { matchScannedCode, shortScanCode } from "../sku";
import type { Item, PoLine, PurchaseOrder, Shopper, Shortage } from "../types";

function flyAddToOrder(from: HTMLElement, label: string) {
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
  const origin = from.getBoundingClientRect();
  const dest =
    [...document.querySelectorAll<HTMLElement>("[data-cart-pane-target]")].find(
      (el) => el.getClientRects().length > 0,
    ) ||
    [...document.querySelectorAll<HTMLElement>("[data-order-target]")].find((el) => el.getClientRects().length > 0);
  const startX = origin.left + origin.width / 2;
  const startY = origin.top + origin.height / 2;
  let endX = window.innerWidth / 2;
  let endY = window.innerHeight - 28;
  if (dest) {
    const box = dest.getBoundingClientRect();
    endX = box.left + box.width / 2;
    endY = box.top + box.height / 2;
  }
  const chip = document.createElement("div");
  chip.className = "add-fly";
  chip.textContent = label;
  chip.style.left = `${startX}px`;
  chip.style.top = `${startY}px`;
  chip.style.setProperty("--dx", `${endX - startX}px`);
  chip.style.setProperty("--dy", `${endY - startY}px`);
  document.body.appendChild(chip);
  chip.addEventListener("animationend", () => chip.remove());
}

export function ShopHome({
  shopper,
  onIdentified,
  onCartChange,
  cartLines,
}: {
  shopper: Shopper | null;
  onIdentified: (s: Shopper) => void;
  onCartChange: () => void;
  cartLines?: PoLine[];
}) {
  const { t, pick, locale } = useI18n();
  const [items, setItems] = useState<Item[]>([]);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState<number | "all">("all");
  const [error, setError] = useState("");
  const [identify, setIdentify] = useState(false);
  const [pendingItem, setPendingItem] = useState<Item | null>(null);
  const [inCart, setInCart] = useState<Record<number, number>>({});
  const [justAdded, setJustAdded] = useState<Record<number, number>>({});
  const [adding, setAdding] = useState<Record<number, boolean>>({});
  const addedTimers = useRef<Record<number, number>>({});
  const skipNextCartLoad = useRef(false);

  useEffect(() => {
    api<Item[]>("/api/shop/catalog").then(setItems).catch((e) => setError(String(e.message)));
  }, []);

  useEffect(() => {
    if (!shopper) {
      setInCart({});
      return;
    }
    if (skipNextCartLoad.current) {
      skipNextCartLoad.current = false;
      return;
    }
    const next: Record<number, number> = {};
    for (const ln of cartLines || []) next[ln.item_id] = ln.quantity;
    setInCart(next);
  }, [shopper, cartLines]);

  useEffect(() => {
    return () => {
      for (const id of Object.keys(addedTimers.current)) {
        window.clearTimeout(addedTimers.current[Number(id)]);
      }
    };
  }, []);

  function markAdded(item: Item, from?: HTMLElement | null) {
    const step = qtyStep(item.unit);
    setInCart((cur) => ({ ...cur, [item.id]: (cur[item.id] || 0) + step }));
    setJustAdded((cur) => {
      const next = { ...cur };
      delete next[item.id];
      return next;
    });
    requestAnimationFrame(() => {
      setJustAdded((cur) => ({ ...cur, [item.id]: Date.now() }));
    });
    window.clearTimeout(addedTimers.current[item.id]);
    addedTimers.current[item.id] = window.setTimeout(() => {
      setJustAdded((cur) => {
        const next = { ...cur };
        delete next[item.id];
        return next;
      });
    }, 700);
    if (from) flyAddToOrder(from, `+${formatQty(step)}`);
  }

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

  async function add(item: Item, from?: HTMLElement | null): Promise<"ok" | "identify" | "error"> {
    setError("");
    if (!shopper) {
      setPendingItem(item);
      setIdentify(true);
      return "identify";
    }
    setAdding((cur) => ({ ...cur, [item.id]: true }));
    try {
      await api("/api/shop/po/lines", {
        method: "POST",
        body: JSON.stringify({ item_id: item.id, quantity: qtyStep(item.unit), increment: true }),
      });
      markAdded(item, from);
      onCartChange();
      return "ok";
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setPendingItem(item);
        setIdentify(true);
        return "identify";
      }
      setError(e instanceof Error ? e.message : t("couldNotAdd"));
      return "error";
    } finally {
      setAdding((cur) => ({ ...cur, [item.id]: false }));
    }
  }

  async function identifyAndAdd(name: string, phone: string) {
    const s = await api<Shopper>("/api/shop/session", {
      method: "POST",
      body: JSON.stringify({ name, phone }),
    });
    skipNextCartLoad.current = true;
    onIdentified(s);
    setIdentify(false);
    if (pendingItem) {
      await api("/api/shop/po/lines", {
        method: "POST",
        body: JSON.stringify({ item_id: pendingItem.id, quantity: qtyStep(pendingItem.unit), increment: true }),
      });
      const from = document.querySelector<HTMLElement>(`[data-add-id="${pendingItem.id}"]`);
      markAdded(pendingItem, from);
      setPendingItem(null);
      onCartChange();
    }
  }

  async function handleScan(code: string) {
    const item = matchScannedCode(items, code);
    if (!item) return { ok: false, message: t("unknownSku", { sku: shortScanCode(code) }) };
    if ((item.available ?? item.quantity) < qtyStep(item.unit)) {
      return { ok: false, message: t("soldOut") };
    }
    if (!shopper) {
      setPendingItem(item);
      setIdentify(true);
      return { ok: true, message: t("whoShopping"), close: true };
    }
    const from = document.querySelector<HTMLElement>(`[data-add-id="${item.id}"]`);
    const result = await add(item, from);
    if (result === "identify") return { ok: true, message: t("whoShopping"), close: true };
    if (result === "error") return { ok: false, message: t("couldNotAdd") };
    return { ok: true, message: t("scanAdded", { name: pick(item.name, item.name_id) }) };
  }

  return (
    <div>
      <div className="scan-row">
        <input className="search" placeholder={t("searchShop")} value={q} onChange={(e) => setQ(e.target.value)} />
        <ScanButton onCode={handleScan} disabled={!items.length} />
      </div>
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
      {identify && (
        <IdentifyForm
          onDone={identifyAndAdd}
          onCancel={() => {
            setIdentify(false);
            setPendingItem(null);
          }}
        />
      )}
      <div className="cards">
        {shown.map((item) => (
          <article className="card product-card" key={item.id}>
            <div className="sku">{item.sku}</div>
            <h3 style={{ margin: "4px 0 8px" }}>{pick(item.name, item.name_id)}</h3>
            <p className="muted" style={{ minHeight: 40 }}>
              {pick(item.description, item.description_id)}
            </p>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <div className="price">{money(item.unit_price_cents)}</div>
                <div className={`stock ${(item.available ?? item.quantity) === 0 ? "out" : item.low_stock ? "low" : ""}`}>
                  {(item.available ?? item.quantity) === 0
                    ? t("soldOut")
                    : t("inStock", { qty: formatQty(item.available ?? item.quantity), unit: unitLabel(item.unit, locale) })}
                </div>
              </div>
              <div className="add-wrap">
                <button
                  className={`btn add-btn${adding[item.id] ? " adding" : ""}${justAdded[item.id] ? " just-added" : ""}`}
                  data-add-id={item.id}
                  disabled={(item.available ?? item.quantity) < qtyStep(item.unit)}
                  onClick={(e) => add(item, e.currentTarget)}
                >
                  {justAdded[item.id] ? t("added") : t("add")}
                </button>
                {inCart[item.id] ? (
                  <div className={`in-order${justAdded[item.id] ? " pop" : ""}`}>
                    {t("inOrder", { qty: formatQty(inCart[item.id]), unit: unitLabel(item.unit, locale) })}
                  </div>
                ) : null}
              </div>
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
  cartRev = 0,
}: {
  shopper: Shopper | null;
  onIdentified: (s: Shopper) => void;
  onCartChange: () => void;
  cartRev?: number;
}) {
  const { t, pick, locale } = useI18n();
  const { user } = useAuth();
  const [po, setPo] = useState<PurchaseOrder | null>(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [shortages, setShortages] = useState<Shortage[]>([]);
  const [paidNow, setPaidNow] = useState(true);
  const [salesperson, setSalesperson] = useState<string | null>(() => {
    try {
      return localStorage.getItem("im_salesperson");
    } catch {
      return "";
    }
  });
  const navigate = useNavigate();

  useEffect(() => {
    if (salesperson !== null) return;
    if (user?.is_sales_agent) {
      setSalesperson(user.display_name);
      return;
    }
    if (user) setSalesperson("");
  }, [user, salesperson]);

  useEffect(() => {
    if (salesperson === null) return;
    try {
      localStorage.setItem("im_salesperson", salesperson);
    } catch {
      /* ignore */
    }
  }, [salesperson]);

  async function load() {
    if (!shopper) return;
    const draft = await api<PurchaseOrder>("/api/shop/po");
    setPo(draft);
    setNote(draft.note || "");
    onCartChange();
  }

  useEffect(() => {
    if (shopper) load().catch((e) => setError(e.message));
  }, [shopper, cartRev]);

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
        setError(t("onlyLeft", { name: pick(s.name, s.name_id), available: formatQty(s.available) }));
      } else {
        setError(e instanceof Error ? e.message : t("updateFailed"));
      }
    }
  }

  async function trimToStock() {
    setBusy(true);
    setError("");
    try {
      for (const s of shortages) {
        await setQty(s.item_id, s.available);
      }
      setShortages([]);
    } finally {
      setBusy(false);
    }
  }

  async function place() {
    setBusy(true);
    setError("");
    setShortages([]);
    try {
      const placed = await api<PurchaseOrder>("/api/shop/po/place", {
        method: "POST",
        body: JSON.stringify({ note, paid: paidNow, salesperson_name: salesperson || "" }),
      });
      onCartChange();
      if (placed.invoice) navigate(`/shop/invoices/${placed.invoice.id}`);
    } catch (e) {
      if (e instanceof ApiError && e.shortages.length) {
        setShortages(e.shortages);
        setError(
          e.shortages
            .map((s) =>
              t("shortageLine", {
                name: pick(s.name, s.name_id),
                requested: formatQty(s.requested),
                available: formatQty(s.available),
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
        {shopper ? (
          <p className="muted">
            {t("customer")}: {shopper.name} · {shopper.phone}
          </p>
        ) : null}
        <button
          className="btn ghost"
          type="button"
          disabled={busy}
          onClick={async () => {
            if (!window.confirm(t("confirmEmptyCart"))) return;
            setBusy(true);
            setError("");
            try {
              const next = await api<PurchaseOrder>("/api/shop/po/abandon", { method: "POST" });
              setPo(next);
              setShortages([]);
              onCartChange();
            } catch (e) {
              setError(e instanceof Error ? e.message : t("updateFailed"));
            } finally {
              setBusy(false);
            }
          }}
        >
          {t("emptyCart")}
        </button>
      </div>
      {error && <div className="banner">{error}</div>}
      {po.lines.map((ln) => (
        <div className="card row" key={ln.id} style={{ justifyContent: "space-between" }}>
          <div>
            <b>{pick(ln.name, ln.name_id)}</b>
            <div className="sku">{ln.sku}</div>
            <div className="muted">
              {money(ln.unit_price_cents, po.currency_symbol)} / {unitLabel(ln.unit || "ea", locale)}
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div className="stepper">
              <button className="icon-btn" onClick={() => setQty(ln.item_id, Math.round((ln.quantity - qtyStep(ln.unit || "ea")) * 1000) / 1000)}>
                −
              </button>
              <b>{formatQty(ln.quantity)}</b>
              <button className="icon-btn" onClick={() => setQty(ln.item_id, Math.round((ln.quantity + qtyStep(ln.unit || "ea")) * 1000) / 1000)}>
                +
              </button>
            </div>
            <div className="price">{money(ln.line_total_cents, po.currency_symbol)}</div>
          </div>
        </div>
      ))}
      <SalesAgentSelect value={salesperson || ""} onChange={setSalesperson} />
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
        <label className="row" style={{ gap: 8, margin: "8px 0" }}>
          <input type="checkbox" checked={paidNow} onChange={(e) => setPaidNow(e.target.checked)} />
          {paidNow ? t("paidNow") : t("creditSale")}
        </label>
        <p className="muted">{t("placeHint")}</p>
        {shortages.length > 0 && (
          <button className="btn ghost block" type="button" disabled={busy} onClick={trimToStock}>
            {t("trimToStock")}
          </button>
        )}
        <button className="btn terra block" disabled={busy} onClick={place}>
          {busy ? t("placing") : t("placeOrder")}
        </button>
      </div>
    </div>
  );
}
