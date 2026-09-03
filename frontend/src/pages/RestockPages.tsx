import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { ItemPicker, PageHeader, StatusTag } from "../components/ui";
import { ResultList } from "../components/Finder";
import { useI18n } from "../i18n";
import { centsFromRupiah, formatQty, money, when } from "../money";
import type { Item, Restock } from "../types";

export function RestockList() {
  const { t, locale } = useI18n();
  const [rows, setRows] = useState<Restock[]>([]);
  useEffect(() => {
    api<Restock[]>("/api/restocks").then(setRows);
  }, []);
  return (
    <div className="grid">
      <PageHeader
        title={t("restockTitle")}
        hint={t("restockHint")}
        actions={
          <Link className="btn" to="/restock/new">
            {t("newRestock")}
          </Link>
        }
      />
      {rows.length === 0 && <p className="empty-state">{t("noRows")}</p>}
      {rows.length > 0 ? (
        <ResultList>
          {rows.map((row) => (
            <Link className="result-row" key={row.id} to={`/restock/${row.id}`}>
              <div>
                <b>{row.number}</b> <StatusTag status={row.status === "received" ? "received" : "draft"} />
                <div className="muted">
                  {row.supplier_name || t("supplier")} · {when(row.received_at || row.created_at, locale)}
                </div>
              </div>
              <div className="price">{money(row.total_cost_cents)}</div>
            </Link>
          ))}
        </ResultList>
      ) : null}
    </div>
  );
}

export function RestockNew() {
  const { t } = useI18n();
  const nav = useNavigate();
  const [error, setError] = useState("");
  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    try {
      const created = await api<Restock>("/api/restocks", {
        method: "POST",
        body: JSON.stringify({
          supplier_name: fd.get("supplier_name"),
          supplier_phone: fd.get("supplier_phone") || "",
          note: fd.get("note") || "",
        }),
      });
      nav(`/restock/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("couldNotCreate"));
    }
  }
  return (
    <div className="grid">
      <PageHeader
        title={t("newRestock")}
        actions={
          <Link className="btn ghost" to="/restock">
            {t("restock")}
          </Link>
        }
      />
      <form className="card form-grid" onSubmit={onSubmit}>
      {error && <div className="banner">{error}</div>}
      <label>
        {t("supplierName")}
        <input name="supplier_name" required />
      </label>
      <label>
        {t("phone")}
        <input name="supplier_phone" />
      </label>
      <label>
        {t("notes")}
        <input name="note" />
      </label>
      <button className="btn" type="submit">
        {t("create")}
      </button>
    </form>
    </div>
  );
}

export function RestockDetail() {
  const { t, pick, locale } = useI18n();
  const { id } = useParams();
  const [row, setRow] = useState<Restock | null>(null);
  const [error, setError] = useState("");

  async function load() {
    setRow(await api<Restock>(`/api/restocks/${id}`));
  }
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [id]);

  async function add(item: Item, qty: number, costRupiah?: number) {
    setError("");
    try {
      setRow(
        await api<Restock>(`/api/restocks/${id}/lines`, {
          method: "POST",
          body: JSON.stringify({
            item_id: item.id,
            quantity: qty,
            unit_cost_cents: centsFromRupiah(String(costRupiah ?? 0)),
          }),
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : t("couldNotAdd"));
    }
  }

  async function receive() {
    setError("");
    try {
      setRow(await api<Restock>(`/api/restocks/${id}/receive`, { method: "POST" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("movementFailed"));
    }
  }

  if (!row) return <p className="muted">{error || t("loading")}</p>;
  return (
    <div className="grid">
      <PageHeader
        kicker={row.number}
        title={row.supplier_name || t("supplier")}
        hint={when(row.received_at || row.created_at, locale)}
        actions={
          <>
            <Link className="btn ghost" to="/restock">
              {t("restock")}
            </Link>
            {row.status === "draft" ? (
              <button className="btn" type="button" onClick={receive} disabled={!row.lines.length}>
                {t("receiveStock")}
              </button>
            ) : null}
          </>
        }
      />
      {error && <div className="banner">{error}</div>}
      <div className="row">
        <StatusTag status={row.status === "received" ? "received" : "draft"} />
        <div className="price">{money(row.total_cost_cents)}</div>
      </div>
      {row.status === "draft" && (
        <div className="card form-grid">
          <h3>{t("addLine")}</h3>
          <ItemPicker costMode onAdd={(item, qty, extra) => add(item, qty, extra)} />
        </div>
      )}
      <div className="card table-wrap">
        <table>
          <thead>
            <tr>
              <th>{t("item")}</th>
              <th>{t("qty")}</th>
              <th>{t("unitCost")}</th>
              <th>{t("amount")}</th>
              {row.status === "draft" ? <th /> : null}
            </tr>
          </thead>
          <tbody>
            {row.lines.map((ln) => (
              <tr key={ln.id}>
                <td>
                  {pick(ln.name, ln.name_id)}
                  <div className="sku">{ln.sku}</div>
                </td>
                <td>{formatQty(ln.quantity)}</td>
                <td>{money(ln.unit_cost_cents)}</td>
                <td>{money(ln.line_total_cents)}</td>
                {row.status === "draft" ? (
                  <td>
                    <button
                      type="button"
                      className="btn ghost"
                      onClick={async () => {
                        setError("");
                        try {
                          setRow(await api<Restock>(`/api/restocks/${id}/lines/${ln.item_id}`, { method: "DELETE" }));
                        } catch (e) {
                          setError(e instanceof Error ? e.message : t("updateFailed"));
                        }
                      }}
                    >
                      ×
                    </button>
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
