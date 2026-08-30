from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_db, raise_checkout, shopper_id_from_request
from app.models import Invoice, Item, PurchaseOrder, Shopper
from app.schemas import PlaceIn, PoLineIn, SessionIn
from app.serialize import invoice_out, item_out, po_out_with_settings
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
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


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
    return [item_out(i) for i in items]


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
        po = chk.upsert_line(db, po, body.item_id, body.quantity)
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


@router.post("/po/place")
def place(body: PlaceIn, request: Request, db: Session = Depends(get_db)):
    sid = shopper_id_from_request(request)
    try:
        po = chk.get_draft(db, sid)
        if po is None:
            raise HTTPException(status_code=400, detail="No draft purchase order to place")
        po, _invoice = chk.place_order(db, po, note=body.note)
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
        )
        .where(Invoice.id == invoice_id, Invoice.shopper_id == sid)
    ).scalar_one_or_none()
    if inv is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice_out(inv)
