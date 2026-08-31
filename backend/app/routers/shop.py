from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_db, raise_checkout, shopper_id_from_request
from app.models import Invoice, Item, PurchaseOrder, Shopper
from app.schemas import PlaceIn, PoLineIn, SessionIn
from app.serialize import invoice_out, item_out, po_out_with_settings
from app.qty import to_store
from app.services import checkout as chk

router = APIRouter(prefix="/api/shop", tags=["shop"])


@router.post("/session")
def create_session(body: SessionIn, request: Request, db: Session = Depends(get_db)):
    try:
        shopper = chk.upsert_shopper(db, body.name, body.phone, body.email)
        db.commit()
        db.refresh(shopper)
    except Exception as err:
        db.rollback()
        raise_checkout(err)
    request.session["shopper_id"] = shopper.id
    return {"id": shopper.id, "name": shopper.name, "phone": shopper.phone, "email": shopper.email}


@router.get("/me")
def me(request: Request, db: Session = Depends(get_db)):
    sid = request.session.get("shopper_id")
    if not sid:
        return {"shopper": None}
    shopper = db.get(Shopper, int(sid))
    if shopper is None:
        request.session.clear()
        return {"shopper": None}
    return {"shopper": {"id": shopper.id, "name": shopper.name, "phone": shopper.phone, "email": shopper.email}}


@router.post("/logout")
def logout(
    request: Request,
    keep_cart: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    sid = request.session.get("shopper_id")
    if sid and not keep_cart:
        chk.abandon_drafts(db, int(sid))
        db.commit()
    request.session.clear()
    return {"ok": True, "kept_cart": bool(keep_cart and sid)}


@router.get("/catalog")
def catalog(q: str | None = None, category_id: int | None = None, db: Session = Depends(get_db)):
    stmt = (
        select(Item)
        .options(selectinload(Item.category), selectinload(Item.location))
        .where(Item.archived == 0)
        .order_by(Item.name)
    )
    items = list(db.execute(stmt).scalars())
    if category_id:
        items = [i for i in items if i.category_id == category_id]
    if q:
        needle = q.strip().lower()
        items = [
            i
            for i in items
            if needle in i.name.lower()
            or needle in (i.name_id or "").lower()
            or needle in i.sku.lower()
            or needle in (i.description or "").lower()
            or needle in (i.description_id or "").lower()
            or needle in (i.notes or "").lower()
        ]
    reserved = chk.draft_reserved(db, [i.id for i in items])
    return [item_out(i, reserved.get(i.id, 0)) for i in items]


@router.get("/po")
def current_po(request: Request, db: Session = Depends(get_db)):
    sid = shopper_id_from_request(request)
    try:
        po = chk.get_or_create_draft(db, sid)
        db.commit()
        po = chk.load_po(db, po.id)
        return po_out_with_settings(db, po)
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.post("/po/lines")
def add_line(body: PoLineIn, request: Request, db: Session = Depends(get_db)):
    sid = shopper_id_from_request(request)
    try:
        po = chk.get_or_create_draft(db, sid)
        qty = to_store(body.quantity)
        if body.increment:
            existing = next((ln for ln in po.lines if ln.item_id == body.item_id), None)
            if existing:
                qty = existing.quantity + qty
        po = chk.upsert_line(db, po, body.item_id, qty)
        db.commit()
        po = chk.load_po(db, po.id)
        return po_out_with_settings(db, po)
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.delete("/po/lines/{item_id}")
def delete_line(item_id: int, request: Request, db: Session = Depends(get_db)):
    sid = shopper_id_from_request(request)
    try:
        po = chk.get_or_create_draft(db, sid)
        po = chk.remove_line(db, po, item_id)
        db.commit()
        po = chk.load_po(db, po.id)
        return po_out_with_settings(db, po)
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.post("/po/abandon")
def abandon_po(request: Request, db: Session = Depends(get_db)):
    sid = shopper_id_from_request(request)
    try:
        chk.abandon_drafts(db, sid)
        po = chk.get_or_create_draft(db, sid)
        db.commit()
        po = chk.load_po(db, po.id)
        return po_out_with_settings(db, po)
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.post("/po/place")
def place(body: PlaceIn, request: Request, db: Session = Depends(get_db)):
    sid = shopper_id_from_request(request)
    try:
        po = chk.get_draft(db, sid)
        if po is None:
            raise HTTPException(status_code=400, detail="No draft purchase order to place")
        po, invoice = chk.place_order(db, po, note=body.note, salesperson_name=body.salesperson_name)
        if body.paid:
            invoice = chk.mark_paid(db, invoice)
        db.commit()
        po = chk.load_po(db, po.id)
        return po_out_with_settings(db, po)
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.get("/orders")
def my_orders(request: Request, db: Session = Depends(get_db)):
    sid = shopper_id_from_request(request)
    rows = db.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.lines),
            selectinload(PurchaseOrder.shopper),
            selectinload(PurchaseOrder.invoice).selectinload(Invoice.lines),
            selectinload(PurchaseOrder.invoice).selectinload(Invoice.shopper),
        )
        .where(PurchaseOrder.shopper_id == sid, PurchaseOrder.status != "draft")
        .order_by(PurchaseOrder.created_at.desc())
    ).scalars()
    return [po_out_with_settings(db, po) for po in rows]


@router.get("/invoices")
def my_invoices(request: Request, db: Session = Depends(get_db)):
    sid = shopper_id_from_request(request)
    rows = db.execute(
        select(Invoice)
        .options(
            selectinload(Invoice.lines),
            selectinload(Invoice.shopper),
            selectinload(Invoice.purchase_order),
            selectinload(Invoice.payments),
        )
        .where(Invoice.shopper_id == sid)
        .order_by(Invoice.issued_at.desc())
    ).scalars()
    return [invoice_out(inv) for inv in rows]


@router.get("/invoices/{invoice_id}")
def my_invoice(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    sid = shopper_id_from_request(request)
    inv = db.execute(
        select(Invoice)
        .options(
            selectinload(Invoice.lines),
            selectinload(Invoice.shopper),
            selectinload(Invoice.purchase_order),
            selectinload(Invoice.payments),
        )
        .where(Invoice.id == invoice_id, Invoice.shopper_id == sid)
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice_out(inv)


def _own_invoice(invoice_id: int, sid: int, db: Session) -> Invoice:
    inv = db.execute(
        select(Invoice)
        .options(
            selectinload(Invoice.lines),
            selectinload(Invoice.shopper),
            selectinload(Invoice.purchase_order),
            selectinload(Invoice.payments),
        )
        .where(Invoice.id == invoice_id, Invoice.shopper_id == sid)
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv


@router.post("/invoices/{invoice_id}/mark-paid")
def shop_mark_paid(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    sid = shopper_id_from_request(request)
    inv = _own_invoice(invoice_id, sid, db)
    try:
        chk.mark_paid(db, inv)
        db.commit()
        return invoice_out(_own_invoice(invoice_id, sid, db))
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.post("/invoices/{invoice_id}/unpay")
def shop_unpay(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    sid = shopper_id_from_request(request)
    inv = _own_invoice(invoice_id, sid, db)
    try:
        chk.mark_unpaid(db, inv)
        db.commit()
        return invoice_out(_own_invoice(invoice_id, sid, db))
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.post("/invoices/{invoice_id}/cancel")
def shop_cancel(invoice_id: int, request: Request, db: Session = Depends(get_db)):
    sid = shopper_id_from_request(request)
    inv = _own_invoice(invoice_id, sid, db)
    po = chk.load_po(db, inv.purchase_order_id)
    if po is None:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        chk.cancel_order(db, po)
        db.commit()
        return invoice_out(_own_invoice(invoice_id, sid, db))
    except Exception as err:
        db.rollback()
        raise_checkout(err)
