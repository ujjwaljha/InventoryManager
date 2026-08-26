import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { LanguageSwitch, useI18n } from "./i18n";
import { api } from "./api";
import { OpNav, ShopNav } from "./components/ui";
import { OpDashboard, OpInvoices, OpItems, OpOrders } from "./pages/OpPages";
import { OpInvoiceDetail, OpItemDetail, OpNewItem, OpSettings } from "./pages/OpDetailPages";
import { ShopInvoiceDetail, ShopInvoices } from "./pages/ShopInvoicePages";
import { ShopCart, ShopHome } from "./pages/ShopPages";
import type { PurchaseOrder, Shopper } from "./types";
import { useEffect, useState } from "react";

function Brand({ to, kicker }: { to: string; kicker: string }) {
  return (
    <Link to={to} className="brand">
      <span className="mark">W</span>
      <span>
        Warung Pojok
        <div className="muted" style={{ fontFamily: "var(--sans)", fontSize: "0.78rem", fontWeight: 400 }}>
          {kicker}
        </div>
      </span>
    </Link>
  );
}

function ShopShell() {
  const { t } = useI18n();
  const [shopper, setShopper] = useState<Shopper | null>(null);
  const [count, setCount] = useState(0);

  async function refreshCart() {
    try {
      const po = await api<PurchaseOrder>("/api/shop/po");
      setCount(po.lines.reduce((n, l) => n + l.quantity, 0));
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
        <Brand to="/shop" kicker={t("shopFloor")} />
        <div className="row desktop-only">
          <NavLink to="/shop">{t("shop")}</NavLink>
          <NavLink to="/shop/order">
            {t("order")}
            {count ? ` (${count})` : ""}
          </NavLink>
          <NavLink to="/shop/invoices">{t("invoices")}</NavLink>
          <NavLink to="/">{t("operatorTill")}</NavLink>
        </div>
        <div className="row" style={{ gap: 10 }}>
          <LanguageSwitch />
          <div className="muted">{shopper ? shopper.name : t("guest")}</div>
        </div>
      </header>
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
  const linkClass = ({ isActive }: { isActive: boolean }) => (isActive ? "active" : "");
  return (
    <div className="app-shell side">
      <aside className="sidebar desktop-only">
        <Brand to="/" kicker={t("operatorTill")} />
        <NavLink to="/" end className={linkClass}>
          {t("home")}
        </NavLink>
        <NavLink to="/items" className={linkClass}>
          {t("items")}
        </NavLink>
        <NavLink to="/orders" className={linkClass}>
          {t("orders")}
        </NavLink>
        <NavLink to="/invoices" className={linkClass}>
          {t("invoices")}
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
          <Brand to="/" kicker={t("operatorTill")} />
          <div className="row">
            <LanguageSwitch />
            <NavLink to="/shop" className="btn ghost">
              {t("openShop")}
            </NavLink>
          </div>
        </header>
        <Routes>
          <Route path="/" element={<OpDashboard />} />
          <Route path="/items" element={<OpItems />} />
          <Route path="/items/new" element={<OpNewItem />} />
          <Route path="/items/:id" element={<OpItemDetail />} />
          <Route path="/orders" element={<OpOrders />} />
          <Route path="/invoices" element={<OpInvoices />} />
          <Route path="/invoices/:id" element={<OpInvoiceDetail />} />
          <Route path="/settings" element={<OpSettings />} />
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
