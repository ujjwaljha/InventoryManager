import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../api";
import { ItemPicker } from "../components/ui";
import { useI18n } from "../i18n";
import { money } from "../money";
import type { Item } from "../types";

type Line = { item: Item; quantity: number };

export function TillPage() {
  const { t, pick } = useI18n();
  const nav = useNavigate();
  const [salesperson, setSalesperson] = useState(() => {
    try {
      return localStorage.getItem("im_salesperson") || "";
    } catch {
      return "";
    }
  });
  const [customer, setCustomer] = useState("");
  const [phone, setPhone] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem("im_salesperson", salesperson);
    } catch {
      /* ignore */
    }
  }, [salesperson]);

  const total = useMemo(
    () => lines.reduce((n, ln) => n + ln.quantity * ln.item.unit_price_cents, 0),
    [lines],
  );

  function add(item: Item, quantity: number) {
    setError("");
    setLines((cur) => {
      const found = cur.find((ln) => ln.item.id === item.id);
      if (!found) return [...cur, { item, quantity }];
      return cur.map((ln) => (ln.item.id === item.id ? { ...ln, quantity: ln.quantity + quantity } : ln));
    });
  }

  async function submit() {
    setError("");
    setBusy(true);
    try {
      const inv = await api<{ id: number }>("/api/sales", {
        method: "POST",
        body: JSON.stringify({
          salesperson_name: salesperson,
          customer_name: customer,
          customer_phone: phone,
          lines: lines.map((ln) => ({ item_id: ln.item.id, quantity: ln.quantity })),
        }),
      });
      nav(`/receipts/${inv.id}`);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : e instanceof Error ? e.message : t("couldNotPlace");
      setError(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid">
      <div>
        <div className="sku">{t("till")}</div>
        <h2 style={{ margin: "4px 0 0" }}>{t("completeSale")}</h2>
        <p className="muted">{t("tillHint")}</p>
      </div>
      {error && <div className="banner">{error}</div>}
      <form
        className="card form-grid"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <label>
          {t("salesperson")}
          <input
            required
            value={salesperson}
            onChange={(e) => setSalesperson(e.target.value)}
            placeholder={t("salespersonPlaceholder")}
          />
        </label>
        <label>
          {t("customer")}
          <input required value={customer} onChange={(e) => setCustomer(e.target.value)} />
        </label>
        <label>
          {t("customerPhone")}
          <input required value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" />
        </label>
        <ItemPicker onAdd={(item, qty) => add(item, qty)} />
        {lines.length === 0 ? (
          <p className="muted">{t("cartEmpty")}</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>{t("item")}</th>
                <th>{t("qty")}</th>
                <th>{t("unitPrice")}</th>
                <th>{t("lineTotal")}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {lines.map((ln) => (
                <tr key={ln.item.id}>
                  <td>{pick(ln.item.name, ln.item.name_id)}</td>
                  <td>{ln.quantity}</td>
                  <td>{money(ln.item.unit_price_cents)}</td>
                  <td>{money(ln.quantity * ln.item.unit_price_cents)}</td>
                  <td>
                    <button type="button" className="btn ghost" onClick={() => setLines((c) => c.filter((x) => x.item.id !== ln.item.id))}>
                      ×
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <div className="price">{t("total")} {money(total)}</div>
        <button className="btn" type="submit" disabled={busy || !lines.length}>
          {t("completeSale")}
        </button>
      </form>
    </div>
  );
}
