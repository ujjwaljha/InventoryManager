from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_db, raise_checkout
from app.models import Invoice, PurchaseOrder, Shopper
from app.schemas import CounterOrderIn, PlaceIn, PoLineIn
from app.serialize import invoice_out, po_out_with_settings
from app.services import checkout as chk

router = APIRouter(prefix="/api", tags=["orders"])


def _load_orders(db: Session, status: str | None):
    stmt = (
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.lines),
            selectinload(PurchaseOrder.shopper),
            selectinload(PurchaseOrder.invoice).selectinload(Invoice.lines),
            selectinload(PurchaseOrder.invoice).selectinload(Invoice.shopper),
        )
        .order_by(PurchaseOrder.created_at.desc())
    )
    if status:
        stmt = stmt.where(PurchaseOrder.status == status)
    return list(db.execute(stmt).scalars())


@router.get("/shoppers")
def list_shoppers(db: Session = Depends(get_db)):
    rows = db.execute(select(Shopper).order_by(Shopper.name)).scalars()
    return [{"id": s.id, "name": s.name, "phone": s.phone, "email": s.email} for s in rows]


@router.get("/orders")
def list_orders(status: str | None = Query(default=None), db: Session = Depends(get_db)):
    return [po_out_with_settings(db, po) for po in _load_orders(db, status)]


@router.get("/orders/{order_id}")
def get_order(order_id: int, db: Session = Depends(get_db)):
    po = chk.load_po(db, order_id)
    if po is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return po_out_with_settings(db, po)


@router.post("/orders")
def create_counter_order(body: CounterOrderIn, db: Session = Depends(get_db)):
    try:
        if body.shopper_id:
            shopper = db.get(Shopper, body.shopper_id)
            if shopper is None:
                raise HTTPException(status_code=404, detail="Shopper not found")
        else:
            if not body.name or not body.phone:
                raise HTTPException(status_code=400, detail="Provide shopper_id or name and phone")
            shopper = chk.upsert_shopper(db, body.name, body.phone, body.email or "")
        po = chk.get_or_create_draft(db, shopper.id)
        db.commit()
        po = chk.load_po(db, po.id)
        return po_out_with_settings(db, po)
    except HTTPException:
        db.rollback()
        raise
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.post("/orders/{order_id}/lines")
def operator_add_line(order_id: int, body: PoLineIn, db: Session = Depends(get_db)):
    po = chk.load_po(db, order_id)
    if po is None:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        po = chk.upsert_line(db, po, body.item_id, body.quantity)
        db.commit()
        po = chk.load_po(db, po.id)
        return po_out_with_settings(db, po)
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.post("/orders/{order_id}/place")
def operator_place(order_id: int, body: PlaceIn, db: Session = Depends(get_db)):
    po = chk.load_po(db, order_id)
    if po is None:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        po, _inv = chk.place_order(db, po, note=body.note, salesperson_name=body.salesperson_name)
        db.commit()
        po = chk.load_po(db, po.id)
        return po_out_with_settings(db, po)
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.post("/orders/{order_id}/cancel")
def operator_cancel(order_id: int, db: Session = Depends(get_db)):
    po = chk.load_po(db, order_id)
    if po is None:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        po = chk.cancel_order(db, po)
        db.commit()
        po = chk.load_po(db, po.id)
        return po_out_with_settings(db, po)
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.get("/invoices")
def list_invoices(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    stmt = (
        select(Invoice)
        .options(
            selectinload(Invoice.lines),
            selectinload(Invoice.shopper),
            selectinload(Invoice.purchase_order),
        )
        .order_by(Invoice.issued_at.desc())
    )
    if status:
        stmt = stmt.where(Invoice.status == status)
    if q:
        needle = q.strip()
        digits = "".join(ch for ch in needle if ch.isdigit())
        stmt = stmt.join(Invoice.shopper)
        clauses = [Invoice.number.ilike(f"%{needle}%"), Shopper.name.ilike(f"%{needle}%")]
        if digits:
            clauses.append(Shopper.phone.contains(digits))
        stmt = stmt.where(or_(*clauses))
    return [invoice_out(inv) for inv in db.execute(stmt).scalars()]


@router.get("/receipts")
def search_receipts(q: str | None = Query(default=None), db: Session = Depends(get_db)):
    return list_invoices(status=None, q=q, db=db)


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    inv = db.execute(
        select(Invoice)
        .options(
            selectinload(Invoice.lines),
            selectinload(Invoice.shopper),
            selectinload(Invoice.purchase_order),
        )
        .where(Invoice.id == invoice_id)
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice_out(inv)


@router.post("/invoices/{invoice_id}/mark-paid")
def invoice_paid(invoice_id: int, db: Session = Depends(get_db)):
    inv = db.execute(
        select(Invoice)
        .options(
            selectinload(Invoice.lines),
            selectinload(Invoice.shopper),
            selectinload(Invoice.purchase_order),
        )
        .where(Invoice.id == invoice_id)
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        chk.mark_paid(db, inv)
        db.commit()
        inv = db.execute(
            select(Invoice)
            .options(
                selectinload(Invoice.lines),
                selectinload(Invoice.shopper),
                selectinload(Invoice.purchase_order),
            )
            .where(Invoice.id == invoice_id)
        ).scalar_one()
        return invoice_out(inv)
    except Exception as err:
        db.rollback()
        raise_checkout(err)
