import { Link, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { AuthGate, useAuth } from "./auth";
import { LanguageSwitch, useI18n } from "./i18n";
import { api, ApiError } from "./api";
import { OpNav, ShopNav } from "./components/ui";
import { CartPane, readCartPaneOpen, writeCartPaneOpen } from "./components/CartPane";
import { OpDashboard, OpInvoices, OpItems, OpOrders } from "./pages/OpPages";
import { OpInvoiceDetail, OpItemDetail, OpNewItem, OpSettings } from "./pages/OpDetailPages";
import { CreditPage, DamagePage, MorePage, ReceiptDetail, ReceiptsPage, ReturnsPage } from "./pages/OfficePages";
import { CustomerDetailPage, CustomersPage } from "./pages/CustomersPage";
import { RestockDetail, RestockList, RestockNew } from "./pages/RestockPages";
import { ReportsPage } from "./pages/ReportPages";
import { TillPage } from "./pages/TillPage";
import { ShopInvoiceDetail, ShopInvoices } from "./pages/ShopInvoicePages";
import { ShopCart, ShopHome } from "./pages/ShopPages";
import type { PurchaseOrder, Settings, Shopper } from "./types";
import { formatQty, nudgeQty } from "./money";
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
  const { t, pick } = useI18n();
  const { user, logout } = useAuth();
  const name = useShopName();
  const [shopper, setShopper] = useState<Shopper | null>(null);
  const [po, setPo] = useState<PurchaseOrder | null>(null);
  const [count, setCount] = useState(0);
  const [countBump, setCountBump] = useState(0);
  const [switching, setSwitching] = useState(false);
  const [cartOpen, setCartOpen] = useState(readCartPaneOpen);
  const [cartError, setCartError] = useState("");
  const [cartRev, setCartRev] = useState(0);
  const prevCount = useRef(0);

  function setPaneOpen(open: boolean) {
    setCartOpen(open);
    writeCartPaneOpen(open);
  }

  async function logoutShop(keepCart: boolean) {
    await api(`/api/shop/logout${keepCart ? "?keep_cart=true" : ""}`, { method: "POST" });
    setShopper(null);
    setPo(null);
    prevCount.current = 0;
    setCount(0);
    setSwitching(false);
  }

  async function refreshCart() {
    try {
      const draft = await api<PurchaseOrder>("/api/shop/po");
      setPo(draft);
      const next = draft.lines.reduce((n, l) => n + l.quantity, 0);
      if (next > prevCount.current) {
        setCountBump((n) => n + 1);
        setPaneOpen(true);
      }
      prevCount.current = next;
      setCount(next);
    } catch {
      setPo(null);
      setCount(0);
    }
  }

  async function changeLine(itemId: number, quantity: number) {
    setCartError("");
    try {
      if (quantity <= 0) {
        const next = await api<PurchaseOrder>(`/api/shop/po/lines/${itemId}`, { method: "DELETE" });
        setPo(next);
        const nextCount = next.lines.reduce((n, l) => n + l.quantity, 0);
        prevCount.current = nextCount;
        setCount(nextCount);
      } else {
        const next = await api<PurchaseOrder>("/api/shop/po/lines", {
          method: "POST",
          body: JSON.stringify({ item_id: itemId, quantity }),
        });
        setPo(next);
        const nextCount = next.lines.reduce((n, l) => n + l.quantity, 0);
        prevCount.current = nextCount;
        setCount(nextCount);
      }
      setCartRev((n) => n + 1);
    } catch (e) {
      if (e instanceof ApiError && e.shortages.length) {
        const s = e.shortages[0];
        setCartError(t("onlyLeft", { name: pick(s.name, s.name_id), available: formatQty(s.available) }));
      } else {
        setCartError(e instanceof Error ? e.message : t("updateFailed"));
      }
    }
  }

  useEffect(() => {
    api<{ shopper: Shopper | null }>("/api/shop/me").then((r) => {
      setShopper(r.shopper);
      if (r.shopper) refreshCart();
    });
  }, []);

  return (
    <div className={`app-shell shop-with-cart${cartOpen ? "" : " collapsed"}`}>
      <header className="topbar">
        <Brand to="/shop" kicker={t("shopFloor")} name={name} />
        <div className="row top-nav desktop-only">
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
          {user ? <span className="muted desktop-only">{user.display_name}</span> : null}
          <button className="btn ghost" type="button" onClick={() => logout()}>
            {t("logout")}
          </button>
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
          element={
            <ShopHome
              shopper={shopper}
              onIdentified={setShopper}
              onCartChange={refreshCart}
              cartLines={po?.lines}
            />
          }
        />
        <Route
          path="/shop/order"
          element={<ShopCart shopper={shopper} onIdentified={setShopper} onCartChange={refreshCart} cartRev={cartRev} />}
        />
        <Route path="/shop/invoices" element={<ShopInvoices />} />
        <Route path="/shop/invoices/:id" element={<ShopInvoiceDetail />} />
      </Routes>
      <CartPane
          lines={(po?.lines || []).map((ln) => ({
            key: ln.id,
            name: pick(ln.name, ln.name_id),
            sku: ln.sku,
            quantity: ln.quantity,
            unit: ln.unit,
            lineTotalCents: ln.line_total_cents,
            onInc: shopper
              ? () => changeLine(ln.item_id, nudgeQty(ln.quantity, ln.unit || "ea", 1))
              : undefined,
            onDec: shopper
              ? () => changeLine(ln.item_id, nudgeQty(ln.quantity, ln.unit || "ea", -1))
              : undefined,
            onRemove: shopper ? () => changeLine(ln.item_id, 0) : undefined,
          }))}
          totalCents={po?.total_cents || 0}
          count={po?.lines.length || 0}
          collapsed={!cartOpen}
          onToggle={() => setPaneOpen(!cartOpen)}
          error={cartError}
          footer={
            (po?.lines.length || 0) > 0 ? (
              <Link className="btn terra block" to="/shop/order" style={{ marginTop: 10, display: "block", textAlign: "center" }}>
                {t("order")}
              </Link>
            ) : null
          }
        />
      <ShopNav count={count} />
    </div>
  );
}

function OpShell() {
  const { t } = useI18n();
  const loc = useLocation();
  const name = useShopName();
  const { user, logout } = useAuth();
  const linkClass = ({ isActive }: { isActive: boolean }) => (isActive ? "active" : "");

  return (
    <div className="app-shell side">
      <aside className="sidebar desktop-only">
        <Brand to="/" kicker={t("backOffice")} name={name} />
        <nav className="sidebar-nav">
          <div className="nav-group-label">{t("navSales")}</div>
          <NavLink to="/" end className={linkClass}>
            {t("home")}
          </NavLink>
          <NavLink to="/till" className={linkClass}>
            {t("till")}
          </NavLink>
          <NavLink to="/receipts" className={linkClass}>
            {t("receipts")}
          </NavLink>
          <NavLink to="/credit" className={linkClass}>
            {t("credit")}
          </NavLink>
          <NavLink to="/customers" className={linkClass}>
            {t("customerFile")}
          </NavLink>
          <NavLink to="/orders" className={linkClass}>
            {t("orders")}
          </NavLink>
          <div className="nav-group-label">{t("navStock")}</div>
          <NavLink to="/items" className={linkClass}>
            {t("items")}
          </NavLink>
          <NavLink to="/restock" className={linkClass}>
            {t("restock")}
          </NavLink>
          <NavLink to="/damage" className={linkClass}>
            {t("damage")}
          </NavLink>
          <NavLink to="/returns" className={linkClass}>
            {t("returns")}
          </NavLink>
          <div className="nav-group-label">{t("navOffice")}</div>
          <NavLink to="/reports" className={linkClass}>
            {t("reports")}
          </NavLink>
          <NavLink to="/settings" className={linkClass}>
            {t("settings")}
          </NavLink>
        </nav>
        <div className="sidebar-foot">
          <NavLink to="/shop" className="btn ghost block">
            {t("openShop")}
          </NavLink>
          <LanguageSwitch />
          {user ? (
            <div className="user-chip">
              <span className="user-avatar">{(user.display_name || user.username).trim().charAt(0).toUpperCase()}</span>
              <span className="muted" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {user.display_name}
              </span>
            </div>
          ) : null}
          <button className="btn ghost small" type="button" onClick={() => logout()}>
            {t("logout")}
          </button>
        </div>
      </aside>
      <div className="main-pane">
        <header className="topbar">
          <Brand to="/" kicker={t("backOffice")} name={name} />
          <div className="row">
            <LanguageSwitch />
            <button className="btn ghost" type="button" onClick={() => logout()}>
              {t("logout")}
            </button>
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
          <Route path="/customers" element={<CustomersPage />} />
          <Route path="/customers/:id" element={<CustomerDetailPage />} />
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

function DesktopHotkeys() {
  const navigate = useNavigate();
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (!document.documentElement.classList.contains("desktop-app")) return;
      if (!(event.metaKey || event.ctrlKey) || event.altKey) return;
      const comma = event.key === "," || event.code === "Comma";
      if (event.shiftKey && !comma) return;
      const target = event.target as HTMLElement | null;
      const typing =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable);
      if (typing) return;
      if (event.key === "1") {
        event.preventDefault();
        navigate("/till");
      } else if (event.key === "2") {
        event.preventDefault();
        navigate("/shop");
      } else if (comma) {
        event.preventDefault();
        navigate("/settings");
      }
    }
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [navigate]);
  return null;
}

export default function App() {
  const loc = useLocation();
  return (
    <>
      <DesktopHotkeys />
      <AuthGate>{loc.pathname.startsWith("/shop") ? <ShopShell /> : <OpShell />}</AuthGate>
    </>
  );
}
