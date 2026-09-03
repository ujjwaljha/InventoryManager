import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { CartPane, readCartPaneOpen, writeCartPaneOpen } from "../components/CartPane";
import { CustomerPicker, ItemPicker, PageHeader, SalesAgentSelect } from "../components/ui";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import { formatQty, money, nudgeQty, qtyMoney } from "../money";
import type { Item, Shortage } from "../types";

type Line = { item: Item; quantity: number };

export function TillPage() {
  const { t, pick } = useI18n();
  const { user } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [salesperson, setSalesperson] = useState<string | null>(() => {
    try {
      return localStorage.getItem("im_salesperson");
    } catch {
      return "";
    }
  });
  const [customer, setCustomer] = useState(() => params.get("name") || "");
  const [phone, setPhone] = useState(() => params.get("phone") || "");
  const [lines, setLines] = useState<Line[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [paidNow, setPaidNow] = useState(true);
  const [shortages, setShortages] = useState<Shortage[]>([]);
  const [cartOpen, setCartOpen] = useState(readCartPaneOpen);

  function setPaneOpen(open: boolean) {
    setCartOpen(open);
    writeCartPaneOpen(open);
  }

  function resetSale() {
    setLines([]);
    setCustomer("");
    setPhone("");
    setPaidNow(true);
    setError("");
    setShortages([]);
  }

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

  useEffect(() => {
    function clearIfDone() {
      try {
        if (sessionStorage.getItem("im_till_done")) {
          sessionStorage.removeItem("im_till_done");
          resetSale();
        }
      } catch {
        /* ignore */
      }
    }
    clearIfDone();
    const onShow = (e: PageTransitionEvent) => {
      if (e.persisted) clearIfDone();
    };
    window.addEventListener("pageshow", onShow);
    return () => window.removeEventListener("pageshow", onShow);
  }, []);

  const total = useMemo(
    () => lines.reduce((n, ln) => n + qtyMoney(ln.quantity, ln.item.unit_price_cents), 0),
    [lines],
  );

  function add(item: Item, quantity: number) {
    setError("");
    setPaneOpen(true);
    setLines((cur) => {
      const found = cur.find((ln) => ln.item.id === item.id);
      if (!found) return [...cur, { item, quantity }];
      return cur.map((ln) => (ln.item.id === item.id ? { ...ln, quantity: ln.quantity + quantity } : ln));
    });
  }

  function setLineQty(itemId: number, quantity: number) {
    setLines((cur) => {
      if (quantity <= 0) return cur.filter((ln) => ln.item.id !== itemId);
      return cur.map((ln) => (ln.item.id === itemId ? { ...ln, quantity } : ln));
    });
  }

  function trimToStock() {
    setLines((cur) =>
      cur
        .map((ln) => {
          const hit = shortages.find((s) => s.item_id === ln.item.id);
          if (!hit) return ln;
          return { ...ln, quantity: hit.available };
        })
        .filter((ln) => ln.quantity > 0),
    );
    setShortages([]);
    setError("");
  }

  async function submit() {
    setError("");
    setShortages([]);
    setBusy(true);
    try {
      const inv = await api<{ id: number }>("/api/sales", {
        method: "POST",
        body: JSON.stringify({
          salesperson_name: salesperson || "",
          customer_name: customer,
          customer_phone: phone,
          lines: lines.map((ln) => ({ item_id: ln.item.id, quantity: ln.quantity })),
          paid: paidNow,
        }),
      });
      try {
        sessionStorage.setItem("im_till_done", String(inv.id));
      } catch {
        /* ignore */
      }
      resetSale();
      nav(`/receipts/${inv.id}`, { replace: true });
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
        const msg = e instanceof ApiError ? e.message : e instanceof Error ? e.message : t("couldNotPlace");
        setError(msg);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`till-with-cart${cartOpen ? "" : " collapsed"}`}>
      <div className="grid">
      <PageHeader kicker={t("till")} title={t("completeSale")} hint={t("tillHint")} />
      {error && <div className="banner">{error}</div>}
      {shortages.length > 0 && (
        <button className="btn ghost" type="button" onClick={trimToStock}>
          {t("trimToStock")}
        </button>
      )}
      <div className="till-desk">
        <section className="card form-grid">
          <h3>{t("addItems")}</h3>
          <p className="muted" style={{ margin: 0 }}>
            {t("scanSkuHint")}
          </p>
          <ItemPicker compact onAdd={(item, qty) => add(item, qty)} />
        </section>
        <form
          className="card form-grid till-checkout"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <h3>{t("checkout")}</h3>
          <SalesAgentSelect value={salesperson || ""} onChange={setSalesperson} />
          <CustomerPicker name={customer} phone={phone} onName={setCustomer} onPhone={setPhone} />
          <p className="muted" style={{ margin: 0 }}>
            {t("tillKeepsCart")}
          </p>
          <div className="till-total">
            <span>{t("total")}</span>
            <div className="price">{money(total)}</div>
          </div>
          <label className="pay-toggle">
            <input type="checkbox" checked={paidNow} onChange={(e) => setPaidNow(e.currentTarget.checked)} />
            {paidNow ? t("paidNow") : t("creditSale")}
          </label>
          <button className="btn block" type="submit" disabled={busy || !lines.length}>
            {t("completeSale")}
          </button>
        </form>
      </div>
      </div>
      <CartPane
        lines={lines.map((ln) => ({
          key: ln.item.id,
          name: pick(ln.item.name, ln.item.name_id),
          sku: ln.item.sku,
          quantity: ln.quantity,
          unit: ln.item.unit,
          lineTotalCents: qtyMoney(ln.quantity, ln.item.unit_price_cents),
          onInc: () => setLineQty(ln.item.id, nudgeQty(ln.quantity, ln.item.unit, 1)),
          onDec: () => setLineQty(ln.item.id, nudgeQty(ln.quantity, ln.item.unit, -1)),
          onRemove: () => setLineQty(ln.item.id, 0),
        }))}
        totalCents={total}
        count={lines.length}
        collapsed={!cartOpen}
        onToggle={() => setPaneOpen(!cartOpen)}
      />
    </div>
  );
}
