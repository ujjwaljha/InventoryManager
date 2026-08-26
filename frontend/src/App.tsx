import { useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api";
import { OpNav, ShopNav } from "./components/ui";
import { OpDashboard, OpInvoices, OpItems, OpOrders } from "./pages/OpPages";
import { OpInvoiceDetail, OpItemDetail, OpNewItem, OpSettings } from "./pages/OpDetailPages";
import { ShopInvoiceDetail, ShopInvoices } from "./pages/ShopInvoicePages";
import { ShopCart, ShopHome } from "./pages/ShopPages";
import type { PurchaseOrder, Shopper } from "./types";

function Brand({ to, kicker }: { to: string; kicker: string }) {
  return (
    <Link to={to} className="brand">
      <span className="mark">C</span>
      <span>
        The Corner Shop
        <div className="muted" style={{ fontFamily: "var(--sans)", fontSize: "0.78rem", fontWeight: 400 }}>
          {kicker}
        </div>
      </span>
    </Link>
  );
}

function ShopShell() {
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
        <Brand to="/shop" kicker="Shop floor" />
        <div className="row desktop-only">
          <NavLink to="/shop">Shop</NavLink>
          <NavLink to="/shop/order">Order{count ? ` (${count})` : ""}</NavLink>
          <NavLink to="/shop/invoices">Invoices</NavLink>
          <NavLink to="/" className="btn ghost">
            Operator
          </NavLink>
        </div>
        <div className="muted">{shopper ? shopper.name : "Guest"}</div>
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
  const loc = useLocation();
  const linkClass = ({ isActive }: { isActive: boolean }) => (isActive ? "active" : "");
  return (
    <div className="app-shell side">
      <aside className="sidebar desktop-only">
        <Brand to="/" kicker="Operator till" />
        <NavLink to="/" end className={linkClass}>
          Home
        </NavLink>
        <NavLink to="/items" className={linkClass}>
          Items
        </NavLink>
        <NavLink to="/orders" className={linkClass}>
          Orders
        </NavLink>
        <NavLink to="/invoices" className={linkClass}>
          Invoices
        </NavLink>
        <NavLink to="/settings" className={linkClass}>
          Settings
        </NavLink>
        <NavLink to="/shop" className="btn ghost" style={{ marginTop: 12, textAlign: "center" }}>
          Open shop
        </NavLink>
      </aside>
      <div>
        <header className="topbar">
          <Brand to="/" kicker="Operator till" />
          <NavLink to="/shop" className="btn ghost">
            Open shop
          </NavLink>
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
