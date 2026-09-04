from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Invoice, InvoiceLine, PurchaseOrder, PurchaseOrderLine, Shopper
from app.serialize import invoice_out, po_out_with_settings
from app.timeutil import shop_day_bounds

PAGE_DEFAULT = 25
PAGE_MAX = 100


def clamp_page(limit: int | None, offset: int | None) -> tuple[int, int]:
    size = PAGE_DEFAULT if limit is None else int(limit)
    size = max(1, min(size, PAGE_MAX))
    start = 0 if offset is None else int(offset)
    start = max(0, start)
    return size, start


def parse_day(raw: str | None) -> str | None:
    value = (raw or "").strip()[:10]
    if not value:
        return None
    date.fromisoformat(value)
    return value


def _like(needle: str) -> str:
    safe = needle.replace("%", "").replace("_", "").strip()
    return f"%{safe}%"


def _page_payload(rows: list, total: int, limit: int, offset: int) -> dict:
    return {"items": rows, "total": int(total), "limit": limit, "offset": offset}


def search_invoices(
    db: Session,
    *,
    q: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> dict:
    size, start = clamp_page(limit, offset)
    needle = (q or "").strip()
    stmt = select(Invoice.id).join(Invoice.shopper)
    if needle:
        stmt = stmt.outerjoin(Invoice.lines).outerjoin(Invoice.purchase_order)
        like = _like(needle)
        digits = "".join(ch for ch in needle if ch.isdigit())
        clauses = [
            Invoice.number.ilike(like),
            Shopper.name.ilike(like),
            Invoice.salesperson_name.ilike(like),
            InvoiceLine.sku.ilike(like),
            InvoiceLine.name.ilike(like),
            InvoiceLine.name_id.ilike(like),
            PurchaseOrder.number.ilike(like),
            PurchaseOrder.note.ilike(like),
        ]
        if digits:
            clauses.append(Shopper.phone.contains(digits))
        stmt = stmt.where(or_(*clauses))
    if status:
        stmt = stmt.where(Invoice.status == status)
    if date_from:
        start, _ = shop_day_bounds(date_from)
        stmt = stmt.where(Invoice.issued_at >= start)
    if date_to:
        _, end = shop_day_bounds(date_to)
        stmt = stmt.where(Invoice.issued_at < end)
    stmt = stmt.group_by(Invoice.id).order_by(func.max(Invoice.issued_at).desc(), Invoice.id.desc())
    total = int(db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
    ids = [int(row[0]) for row in db.execute(stmt.offset(start).limit(size))]
    if not ids:
        return _page_payload([], total, size, start)
    loaded = list(
        db.execute(
            select(Invoice)
            .options(
                selectinload(Invoice.lines),
                selectinload(Invoice.shopper),
                selectinload(Invoice.purchase_order),
                selectinload(Invoice.payments),
            )
            .where(Invoice.id.in_(ids))
        ).scalars()
    )
    by_id = {inv.id: inv for inv in loaded}
    rows = [invoice_out(by_id[i]) for i in ids if i in by_id]
    return _page_payload(rows, total, size, start)


def search_orders(
    db: Session,
    *,
    q: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> dict:
    size, start = clamp_page(limit, offset)
    needle = (q or "").strip()
    when_at = func.coalesce(PurchaseOrder.placed_at, PurchaseOrder.created_at)
    stmt = select(PurchaseOrder.id).join(PurchaseOrder.shopper)
    if needle:
        stmt = stmt.outerjoin(PurchaseOrder.lines).outerjoin(PurchaseOrder.invoice)
        like = _like(needle)
        digits = "".join(ch for ch in needle if ch.isdigit())
        clauses = [
            PurchaseOrder.number.ilike(like),
            PurchaseOrder.note.ilike(like),
            Shopper.name.ilike(like),
            PurchaseOrderLine.sku.ilike(like),
            PurchaseOrderLine.name.ilike(like),
            PurchaseOrderLine.name_id.ilike(like),
            Invoice.number.ilike(like),
            Invoice.salesperson_name.ilike(like),
        ]
        if digits:
            clauses.append(Shopper.phone.contains(digits))
        stmt = stmt.where(or_(*clauses))
    if status:
        stmt = stmt.where(PurchaseOrder.status == status)
    if date_from:
        start, _ = shop_day_bounds(date_from)
        stmt = stmt.where(when_at >= start)
    if date_to:
        _, end = shop_day_bounds(date_to)
        stmt = stmt.where(when_at < end)
    stmt = stmt.group_by(PurchaseOrder.id).order_by(func.max(when_at).desc(), PurchaseOrder.id.desc())
    total = int(db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
    ids = [int(row[0]) for row in db.execute(stmt.offset(start).limit(size))]
    if not ids:
        return _page_payload([], total, size, start)
    loaded = list(
        db.execute(
            select(PurchaseOrder)
            .options(
                selectinload(PurchaseOrder.lines),
                selectinload(PurchaseOrder.shopper),
                selectinload(PurchaseOrder.invoice).selectinload(Invoice.lines),
                selectinload(PurchaseOrder.invoice).selectinload(Invoice.shopper),
            )
            .where(PurchaseOrder.id.in_(ids))
        ).scalars()
    )
    by_id = {po.id: po for po in loaded}
    rows = [po_out_with_settings(db, by_id[i]) for i in ids if i in by_id]
    return _page_payload(rows, total, size, start)
