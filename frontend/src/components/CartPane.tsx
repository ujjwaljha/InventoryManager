import type { ReactNode } from "react";
import { formatQty, money, unitLabel } from "../money";
import { useI18n } from "../i18n";

export type CartPaneLine = {
  key: string | number;
  name: string;
  sku?: string;
  quantity: number;
  unit?: string;
  lineTotalCents: number;
  onInc?: () => void;
  onDec?: () => void;
  onRemove?: () => void;
};

export function CartPane({
  lines,
  totalCents,
  count,
  collapsed,
  onToggle,
  footer,
  error,
}: {
  lines: CartPaneLine[];
  totalCents: number;
  count: number;
  collapsed: boolean;
  onToggle: () => void;
  footer?: ReactNode;
  error?: string;
}) {
  const { t, locale } = useI18n();

  if (collapsed) {
    return (
      <button
        type="button"
        className="cart-pane-tab"
        onClick={onToggle}
        aria-expanded={false}
        aria-controls="cart-pane"
        data-cart-pane-target
        title={t("showCart")}
      >
        <span className="cart-pane-tab-label">{t("cart")}</span>
        {count > 0 ? <span className="badge">{count}</span> : null}
      </button>
    );
  }

  return (
    <>
      <button type="button" className="cart-pane-backdrop" aria-label={t("hideCart")} onClick={onToggle} />
      <aside id="cart-pane" className="cart-pane" aria-label={t("cart")}>
      <header className="cart-pane-head">
        <div className="row" style={{ gap: 8 }}>
          <b data-cart-pane-target>{t("cart")}</b>
          {count > 0 ? <span className="badge">{count}</span> : null}
        </div>
        <button type="button" className="btn ghost small" onClick={onToggle} title={t("hideCart")}>
          {t("hideCart")}
        </button>
      </header>
      <div className="cart-pane-body">
        {error ? <div className="banner">{error}</div> : null}
        {lines.length === 0 ? (
          <p className="muted">{t("cartEmpty")}</p>
        ) : (
          <ul className="cart-pane-list">
            {lines.map((ln) => (
              <li key={ln.key} className="cart-pane-line">
                <div className="cart-pane-line-copy">
                  <b>{ln.name}</b>
                  {ln.sku ? <div className="sku">{ln.sku}</div> : null}
                  <div className="price">{money(ln.lineTotalCents)}</div>
                </div>
                <div className="cart-pane-line-ops">
                  {ln.onDec || ln.onInc ? (
                    <div className="stepper">
                      <button type="button" className="icon-btn" onClick={ln.onDec} disabled={!ln.onDec} aria-label="−">
                        −
                      </button>
                      <b>
                        {formatQty(ln.quantity)}
                        {ln.unit ? ` ${unitLabel(ln.unit, locale)}` : ""}
                      </b>
                      <button type="button" className="icon-btn" onClick={ln.onInc} disabled={!ln.onInc} aria-label="+">
                        +
                      </button>
                    </div>
                  ) : (
                    <b>
                      {formatQty(ln.quantity)}
                      {ln.unit ? ` ${unitLabel(ln.unit, locale)}` : ""}
                    </b>
                  )}
                  {ln.onRemove ? (
                    <button type="button" className="btn danger-ghost small" onClick={ln.onRemove}>
                      ×
                    </button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
      <footer className="cart-pane-foot">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span>{t("total")}</span>
          <b className="price">{money(totalCents)}</b>
        </div>
        {footer}
      </footer>
    </aside>
    </>
  );
}

export function readCartPaneOpen(): boolean {
  try {
    const stored = localStorage.getItem("im_cart_pane");
    if (stored === "0") return false;
    if (stored === "1") return true;
  } catch {
    /* ignore */
  }
  if (typeof window !== "undefined" && window.matchMedia("(max-width: 859px)").matches) return false;
  return true;
}

export function writeCartPaneOpen(open: boolean) {
  try {
    localStorage.setItem("im_cart_pane", open ? "1" : "0");
  } catch {
    /* ignore */
  }
}
