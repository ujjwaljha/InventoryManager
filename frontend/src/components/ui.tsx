import { NavLink } from "react-router-dom";
import { money, when } from "../money";
import type { Invoice } from "../types";

export function InvoiceSheet({ invoice }: { invoice: Invoice }) {
  return (
    <article className="invoice-sheet">
      <header className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1>{invoice.shop_name}</h1>
          <div className="muted">
            {invoice.shop_address}
            {invoice.shop_phone ? ` · ${invoice.shop_phone}` : ""}
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="sku">Invoice</div>
          <b>{invoice.number}</b>
          <div className="muted">{when(invoice.issued_at)}</div>
          <span className={`tag ${invoice.status}`}>{invoice.status}</span>
        </div>
      </header>
      <p>
        <b>Bill to</b>
        <br />
        {invoice.shopper_name}
        <br />
        <span className="muted">{invoice.shopper_phone}</span>
        <br />
        <span className="muted">{invoice.purchase_order_number}</span>
      </p>
      <table>
        <thead>
          <tr>
            <th>Item</th>
            <th>Qty</th>
            <th>Price</th>
            <th>Amount</th>
          </tr>
        </thead>
        <tbody>
          {invoice.lines.map((ln) => (
            <tr key={ln.id}>
              <td>
                <div>{ln.name}</div>
                <div className="sku">{ln.sku}</div>
              </td>
              <td>{ln.quantity}</td>
              <td>{money(ln.unit_price_cents, invoice.currency_symbol)}</td>
              <td>{money(ln.line_total_cents, invoice.currency_symbol)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 16, textAlign: "right" }}>
        <div className="muted">Subtotal {money(invoice.subtotal_cents, invoice.currency_symbol)}</div>
        {invoice.tax_cents > 0 && (
          <div className="muted">
            Tax ({(invoice.tax_bps / 100).toFixed(2)}%) {money(invoice.tax_cents, invoice.currency_symbol)}
          </div>
        )}
        <h2 style={{ margin: "8px 0 0" }}>Total {money(invoice.total_cents, invoice.currency_symbol)}</h2>
      </div>
    </article>
  );
}

export function StatusTag({ status }: { status: string }) {
  return <span className={`tag ${status}`}>{status}</span>;
}

export function IdentifyForm({
  onDone,
  pending,
}: {
  onDone: (name: string, phone: string) => void;
  pending?: boolean;
}) {
  return (
    <form
      className="card form-grid"
      onSubmit={(e) => {
        e.preventDefault();
        const fd = new FormData(e.currentTarget);
        onDone(String(fd.get("name") || ""), String(fd.get("phone") || ""));
      }}
    >
      <h3 style={{ margin: 0 }}>Who is shopping?</h3>
      <p className="muted" style={{ margin: 0 }}>
        We keep your purchase order on this phone until you place it.
      </p>
      <label>
        Name
        <input name="name" required placeholder="Your name" autoComplete="name" />
      </label>
      <label>
        Phone
        <input name="phone" required placeholder="Mobile number" inputMode="tel" autoComplete="tel" />
      </label>
      <button className="btn" type="submit" disabled={pending}>
        Continue
      </button>
    </form>
  );
}

export function ShopNav({ count }: { count: number }) {
  return (
    <nav className="bottom-nav">
      <NavLink to="/shop" end>
        Shop
      </NavLink>
      <NavLink to="/shop/order">
        Order{count > 0 ? <span className="badge">{count}</span> : null}
      </NavLink>
      <NavLink to="/shop/invoices">Invoices</NavLink>
    </nav>
  );
}

export function OpNav() {
  return (
    <nav className="bottom-nav">
      <NavLink to="/" end>
        Home
      </NavLink>
      <NavLink to="/items">Items</NavLink>
      <NavLink to="/orders">Orders</NavLink>
      <NavLink to="/invoices">Invoices</NavLink>
      <NavLink to="/settings">More</NavLink>
    </nav>
  );
}
