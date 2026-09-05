import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { ItemPicker, PageHeader, StatusTag, SupplierPicker } from "../components/ui";
import { ResultList } from "../components/Finder";
import { useI18n } from "../i18n";
import { centsFromRupiah, formatQty, money, qtyStep, when } from "../money";
import type { Item, Restock, RestockLine } from "../types";

type SupplierChoice = { value: number | "new" | ""; name: string; phone: string };

function restockBody(choice: SupplierChoice, note: string) {
  if (typeof choice.value === "number") {
    return { supplier_id: choice.value, note };
  }
  return {
    supplier_name: choice.name.trim(),
    supplier_phone: choice.phone.trim(),
    note,
  };
}

export function RestockList() {
  const { t, locale } = useI18n();
  const [rows, setRows] = useState<Restock[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Restock[]>("/api/restocks")
      .then(setRows)
      .catch((e) => setError(e instanceof Error ? e.message : t("updateFailed")));
  }, [t]);
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
      {error && <div className="banner">{error}</div>}
      {rows.length === 0 && !error && <p className="empty-state">{t("noRows")}</p>}
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
  const [note, setNote] = useState("");
  const [supplier, setSupplier] = useState<SupplierChoice>({ value: "new", name: "", phone: "" });

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (supplier.value === "") {
      setError(t("supplierRequired"));
      return;
    }
    if (supplier.value === "new" && !supplier.name.trim()) {
      setError(t("supplierRequired"));
      return;
    }
    try {
      const created = await api<Restock>("/api/restocks", {
        method: "POST",
        body: JSON.stringify(restockBody(supplier, note)),
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
        <SupplierPicker
          value={supplier.value}
          name={supplier.name}
          phone={supplier.phone}
          onChange={setSupplier}
        />
        <label>
          {t("notes")}
          <input value={note} onChange={(e) => setNote(e.target.value)} />
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
  const nav = useNavigate();
  const { id } = useParams();
  const [row, setRow] = useState<Restock | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [supplier, setSupplier] = useState<SupplierChoice>({ value: "", name: "", phone: "" });

  async function load() {
    const next = await api<Restock>(`/api/restocks/${id}`);
    setRow(next);
    setNote(next.note || "");
    setSupplier({
      value: next.supplier_id ?? (next.supplier_name ? "new" : ""),
      name: next.supplier_name || "",
      phone: next.supplier_phone || "",
    });
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

  async function setLineQty(ln: RestockLine, nextQty: number) {
    setError("");
    try {
      if (nextQty <= 0) {
        setRow(await api<Restock>(`/api/restocks/${id}/lines/${ln.item_id}`, { method: "DELETE" }));
        return;
      }
      setRow(
        await api<Restock>(`/api/restocks/${id}/lines`, {
          method: "POST",
          body: JSON.stringify({
            item_id: ln.item_id,
            quantity: nextQty,
            unit_cost_cents: ln.unit_cost_cents,
            replace: true,
          }),
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : t("updateFailed"));
    }
  }

  async function saveHeader() {
    setError("");
    if (supplier.value === "" || (supplier.value === "new" && !supplier.name.trim())) {
      setError(t("supplierRequired"));
      return;
    }
    try {
      setRow(
        await api<Restock>(`/api/restocks/${id}`, {
          method: "PATCH",
          body: JSON.stringify(restockBody(supplier, note)),
        }),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : t("updateFailed"));
    }
  }

  async function receive() {
    if (!window.confirm(t("confirmReceive"))) return;
    setError("");
    setBusy(true);
    try {
      setRow(await api<Restock>(`/api/restocks/${id}/receive`, { method: "POST" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("movementFailed"));
    } finally {
      setBusy(false);
    }
  }

  async function discard() {
    if (!window.confirm(t("confirmDiscardDraft"))) return;
    setError("");
    setBusy(true);
    try {
      await api(`/api/restocks/${id}`, { method: "DELETE" });
      nav("/restock");
    } catch (e) {
      setError(e instanceof Error ? e.message : t("updateFailed"));
      setBusy(false);
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
              <button className="btn ghost" type="button" onClick={discard} disabled={busy}>
                {t("discardDraft")}
              </button>
            ) : null}
            {row.status === "draft" ? (
              <button className="btn" type="button" onClick={receive} disabled={!row.lines.length || busy}>
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
      {row.status === "draft" ? (
        <form
          className="card form-grid"
          onSubmit={(e) => {
            e.preventDefault();
            saveHeader();
          }}
        >
          <SupplierPicker
            value={supplier.value}
            name={supplier.name}
            phone={supplier.phone}
            onChange={setSupplier}
          />
          <label>
            {t("notes")}
            <input value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <button className="btn ghost" type="submit">
            {t("save")}
          </button>
        </form>
      ) : (
        <div className="card">
          <div>
            {row.supplier_name || t("supplier")}
            {row.supplier_phone ? ` · ${row.supplier_phone}` : ""}
          </div>
          {row.note ? <p className="muted">{row.note}</p> : null}
        </div>
      )}
      {row.status === "draft" && (
        <div className="card form-grid">
          <h3>{t("addLine")}</h3>
          <p className="muted" style={{ margin: 0 }}>
            {t("restockAddHint")}
          </p>
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
                <td>
                  {row.status === "draft" ? (
                    <div className="stepper">
                      <button
                        type="button"
                        className="icon-btn"
                        onClick={() => setLineQty(ln, Math.round((ln.quantity - qtyStep(ln.unit || "ea")) * 1000) / 1000)}
                      >
                        −
                      </button>
                      <b>{formatQty(ln.quantity)}</b>
                      <button
                        type="button"
                        className="icon-btn"
                        onClick={() => setLineQty(ln, Math.round((ln.quantity + qtyStep(ln.unit || "ea")) * 1000) / 1000)}
                      >
                        +
                      </button>
                    </div>
                  ) : (
                    formatQty(ln.quantity)
                  )}
                </td>
                <td>{money(ln.unit_cost_cents)}</td>
                <td>{money(ln.line_total_cents)}</td>
                {row.status === "draft" ? (
                  <td>
                    <button
                      type="button"
                      className="btn ghost"
                      onClick={() => setLineQty(ln, 0)}
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
