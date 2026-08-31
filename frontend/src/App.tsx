import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { LanguageSwitch, useI18n } from "./i18n";
import { api } from "./api";
import { OpNav, PinUnlock, ShopNav } from "./components/ui";
import { OpDashboard, OpInvoices, OpItems, OpOrders } from "./pages/OpPages";
import { OpInvoiceDetail, OpItemDetail, OpNewItem, OpSettings } from "./pages/OpDetailPages";
import { CreditPage, DamagePage, MorePage, ReceiptDetail, ReceiptsPage, ReturnsPage } from "./pages/OfficePages";
import { RestockDetail, RestockList, RestockNew } from "./pages/RestockPages";
import { ReportsPage } from "./pages/ReportPages";
import { TillPage } from "./pages/TillPage";
import { ShopInvoiceDetail, ShopInvoices } from "./pages/ShopInvoicePages";
import { ShopCart, ShopHome } from "./pages/ShopPages";
import type { PurchaseOrder, Settings, Shopper } from "./types";
import { useEffect, useRef, useState } from "react";

function Brand({ to, kicker, name }: { to: string; kicker: string; name: string }) {
  const letter = (name || "T").trim().charAt(0).toUpperCase();
  return (
    <Link to={to} className="brand">
      <span className="mark">{letter}</span>
      <span>
        {name}
        <div className="muted" style={{ fontFamily: "var(--sans)", fontSize: "0.78rem", fontWeight: 400 }}>
          {kicker}
        </div>
      </span>
    </Link>
  );
}

function useShopName() {
  const { t } = useI18n();
  const [name, setName] = useState(t("shopNameFallback"));
  useEffect(() => {
    api<Settings>("/api/settings")
      .then((s) => {
        setName(s.name);
        document.title = s.name;
      })
      .catch(() => undefined);
  }, [t]);
  return name;
}

function ShopShell() {
  const { t } = useI18n();
  const name = useShopName();
  const [shopper, setShopper] = useState<Shopper | null>(null);
  const [count, setCount] = useState(0);
  const [countBump, setCountBump] = useState(0);
  const [switching, setSwitching] = useState(false);
  const prevCount = useRef(0);

  async function logoutShop(keepCart: boolean) {
    await api(`/api/shop/logout${keepCart ? "?keep_cart=true" : ""}`, { method: "POST" });
    setShopper(null);
    prevCount.current = 0;
    setCount(0);
    setSwitching(false);
  }

  async function refreshCart() {
    try {
      const po = await api<PurchaseOrder>("/api/shop/po");
      const next = po.lines.reduce((n, l) => n + l.quantity, 0);
      if (next > prevCount.current) setCountBump((n) => n + 1);
      prevCount.current = next;
      setCount(next);
    } catch {
      setCount(0);
    }
  }

  useEffect(() => {
    api<{ shopper: Shopper | null }>("/api/shop/me").then((r) => {
      setShopper(r.shopper);
      if (r.shopper) refreshCart();
    });
  }, []);

  return (
    <div className="app-shell">
      <header className="topbar">
        <Brand to="/shop" kicker={t("shopFloor")} name={name} />
        <div className="row desktop-only">
          <NavLink to="/shop">{t("shop")}</NavLink>
          <NavLink to="/shop/order" data-order-target>
            {t("order")}
            {count ? (
              <span key={countBump} className={`nav-count${countBump ? " bump" : ""}`}>
                {" "}
                ({count})
              </span>
            ) : null}
          </NavLink>
          <NavLink to="/shop/invoices">{t("invoices")}</NavLink>
          <NavLink to="/">{t("backOffice")}</NavLink>
        </div>
        <div className="row" style={{ gap: 10 }}>
          <LanguageSwitch />
          {shopper ? (
            <button className="btn ghost" type="button" onClick={() => setSwitching(true)}>
              {shopper.name} · {t("changeCustomer")}
            </button>
          ) : (
            <div className="muted">{t("guest")}</div>
          )}
        </div>
      </header>
      {switching && shopper ? (
        <div className="card">
          <b>{t("changeCustomer")}</b>
          <p className="muted">{count > 0 ? t("changeCustomerHint") : t("whoShoppingHint")}</p>
          <div className="row">
            <button className="btn terra" type="button" onClick={() => logoutShop(true)}>
              {t("keepCart")}
            </button>
            {count > 0 ? (
              <button className="btn ghost" type="button" onClick={() => logoutShop(false)}>
                {t("dropCart")}
              </button>
            ) : null}
            <button className="btn ghost" type="button" onClick={() => setSwitching(false)}>
              {t("cancel")}
            </button>
          </div>
        </div>
      ) : null}
      <Routes>
        <Route
          path="/shop"
          element={<ShopHome shopper={shopper} onIdentified={setShopper} onCartChange={refreshCart} />}
        />
        <Route
          path="/shop/order"
          element={<ShopCart shopper={shopper} onIdentified={setShopper} onCartChange={refreshCart} />}
        />
        <Route path="/shop/invoices" element={<ShopInvoices />} />
        <Route path="/shop/invoices/:id" element={<ShopInvoiceDetail />} />
      </Routes>
      <ShopNav count={count} />
    </div>
  );
}

function OpShell() {
  const { t } = useI18n();
  const loc = useLocation();
  const name = useShopName();
  const [gate, setGate] = useState<{ required: boolean; unlocked: boolean } | null>(null);
  const linkClass = ({ isActive }: { isActive: boolean }) => (isActive ? "active" : "");

  useEffect(() => {
    api<{ required: boolean; unlocked: boolean }>("/api/operator/status")
      .then(setGate)
      .catch(() => setGate({ required: false, unlocked: true }));
  }, [loc.pathname]);

  if (gate?.required && !gate.unlocked) {
    return (
      <div className="app-shell">
        <PinUnlock onUnlocked={() => setGate({ required: true, unlocked: true })} />
      </div>
    );
  }

  return (
    <div className="app-shell side">
      <aside className="sidebar desktop-only">
        <Brand to="/" kicker={t("backOffice")} name={name} />
        <NavLink to="/" end className={linkClass}>
          {t("home")}
        </NavLink>
        <NavLink to="/till" className={linkClass}>
          {t("till")}
        </NavLink>
        <NavLink to="/items" className={linkClass}>
          {t("items")}
        </NavLink>
        <NavLink to="/restock" className={linkClass}>
          {t("restock")}
        </NavLink>
        <NavLink to="/receipts" className={linkClass}>
          {t("receipts")}
        </NavLink>
        <NavLink to="/credit" className={linkClass}>
          {t("credit")}
        </NavLink>
        <NavLink to="/reports" className={linkClass}>
          {t("reports")}
        </NavLink>
        <NavLink to="/damage" className={linkClass}>
          {t("damage")}
        </NavLink>
        <NavLink to="/returns" className={linkClass}>
          {t("returns")}
        </NavLink>
        <NavLink to="/orders" className={linkClass}>
          {t("orders")}
        </NavLink>
        <NavLink to="/settings" className={linkClass}>
          {t("settings")}
        </NavLink>
        <NavLink to="/shop" className="btn ghost" style={{ marginTop: 12, textAlign: "center" }}>
          {t("openShop")}
        </NavLink>
        <div style={{ marginTop: 12 }}>
          <LanguageSwitch />
        </div>
      </aside>
      <div>
        <header className="topbar">
          <Brand to="/" kicker={t("backOffice")} name={name} />
          <div className="row">
            <LanguageSwitch />
            <NavLink to="/shop" className="btn ghost">
              {t("openShop")}
            </NavLink>
          </div>
        </header>
        <Routes>
          <Route path="/" element={<OpDashboard />} />
          <Route path="/till" element={<TillPage />} />
          <Route path="/items" element={<OpItems />} />
          <Route path="/items/new" element={<OpNewItem />} />
          <Route path="/items/:id" element={<OpItemDetail />} />
          <Route path="/restock" element={<RestockList />} />
          <Route path="/restock/new" element={<RestockNew />} />
          <Route path="/restock/:id" element={<RestockDetail />} />
          <Route path="/receipts" element={<ReceiptsPage />} />
          <Route path="/receipts/:id" element={<ReceiptDetail />} />
          <Route path="/credit" element={<CreditPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/damage" element={<DamagePage />} />
          <Route path="/returns" element={<ReturnsPage />} />
          <Route path="/orders" element={<OpOrders />} />
          <Route path="/invoices" element={<OpInvoices />} />
          <Route path="/invoices/:id" element={<OpInvoiceDetail />} />
          <Route path="/settings" element={<OpSettings />} />
          <Route path="/more" element={<MorePage />} />
        </Routes>
      </div>
      <OpNav />
      <span hidden>{loc.pathname}</span>
    </div>
  );
}

export default function App() {
  const loc = useLocation();
  if (loc.pathname.startsWith("/shop")) return <ShopShell />;
  return <OpShell />;
}
