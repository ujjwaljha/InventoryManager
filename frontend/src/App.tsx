import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { LanguageSwitch, useI18n } from "./i18n";
import { api } from "./api";
import { OpNav, ShopNav } from "./components/ui";
import { OpDashboard, OpInvoices, OpItems, OpOrders } from "./pages/OpPages";
import { OpInvoiceDetail, OpItemDetail, OpNewItem, OpSettings } from "./pages/OpDetailPages";
import { DamagePage, MorePage, ReceiptDetail, ReceiptsPage, ReturnsPage } from "./pages/OfficePages";
import { RestockDetail, RestockList, RestockNew } from "./pages/RestockPages";
import { ReportsPage } from "./pages/ReportPages";
import { TillPage } from "./pages/TillPage";
import { ShopInvoiceDetail, ShopInvoices } from "./pages/ShopInvoicePages";
import { ShopCart, ShopHome } from "./pages/ShopPages";
import type { PurchaseOrder, Settings, Shopper } from "./types";
import { useEffect, useState } from "react";

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
        <Brand to="/shop" kicker={t("shopFloor")} name={name} />
        <div className="row desktop-only">
          <NavLink to="/shop">{t("shop")}</NavLink>
          <NavLink to="/shop/order">
            {t("order")}
            {count ? ` (${count})` : ""}
          </NavLink>
          <NavLink to="/shop/invoices">{t("invoices")}</NavLink>
          <NavLink to="/">{t("backOffice")}</NavLink>
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
  const name = useShopName();
  const linkClass = ({ isActive }: { isActive: boolean }) => (isActive ? "active" : "");
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
