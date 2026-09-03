from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_db, raise_checkout
from app.models import CreditNote, Invoice, PurchaseOrder, Shopper
from app.schemas import CounterOrderIn, CreditNoteIn, InvoiceDueIn, PaymentIn, PlaceIn, PoLineIn, ShopperPatch
from app.serialize import invoice_out, po_out_with_settings
from app.qty import to_store
from app.services import checkout as chk
from app.timeutil import age_days, aging_bucket, overdue_days, today_shop, utcnow

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
def list_shoppers(
    q: str | None = Query(default=None),
    limit: int = Query(default=80, le=500),
    db: Session = Depends(get_db),
):
    return chk.shopper_summaries(db, q, limit)


@router.get("/shoppers/{shopper_id}")
def get_shopper(shopper_id: int, db: Session = Depends(get_db)):
    shopper = db.get(Shopper, shopper_id)
    if shopper is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    card = chk.decorate_shoppers(db, [shopper])[0]
    invoices = list(
        db.execute(
            select(Invoice)
            .options(
                selectinload(Invoice.lines),
                selectinload(Invoice.shopper),
                selectinload(Invoice.purchase_order),
                selectinload(Invoice.payments),
            )
            .where(Invoice.shopper_id == shopper_id, Invoice.status.in_(("issued", "paid")))
            .order_by(Invoice.issued_at.desc())
            .limit(50)
        ).scalars()
    )
    card["invoices"] = [invoice_out(inv) for inv in invoices]
    return card


@router.patch("/shoppers/{shopper_id}")
def patch_shopper(shopper_id: int, body: ShopperPatch, db: Session = Depends(get_db)):
    try:
        shopper = chk.update_shopper(db, shopper_id, name=body.name, phone=body.phone, email=body.email)
        db.commit()
        db.refresh(shopper)
    except Exception as err:
        db.rollback()
        raise_checkout(err)
    return chk.decorate_shoppers(db, [shopper])[0]


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
        po = chk.upsert_line(db, po, body.item_id, to_store(body.quantity))
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
            selectinload(Invoice.payments),
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


@router.get("/credit")
def credit_report(db: Session = Depends(get_db)):
    invoices = list(
        db.execute(
            select(Invoice)
            .options(
                selectinload(Invoice.lines),
                selectinload(Invoice.shopper),
                selectinload(Invoice.purchase_order),
                selectinload(Invoice.payments),
            )
            .where(Invoice.status == "issued")
            .order_by(Invoice.issued_at.asc())
        ).scalars()
    )
    today = today_shop()
    empty_aging = {"d0_30": 0, "d31_60": 0, "d61_90": 0, "d90_plus": 0}
    aging = dict(empty_aging)
    by_shopper: dict[int, dict] = {}
    invoice_rows = []
    for inv in invoices:
        days = age_days(inv.issued_at, today)
        late = overdue_days(getattr(inv, "due_date", None), inv.issued_at, today)
        bucket = aging_bucket(late)
        aging[bucket] += chk.balance_cents(inv)
        row = by_shopper.setdefault(
            inv.shopper_id,
            {
                "shopper_id": inv.shopper_id,
                "shopper_name": inv.shopper.name if inv.shopper else "",
                "shopper_phone": inv.shopper.phone if inv.shopper else "",
                "invoice_count": 0,
                "unpaid_cents": 0,
                "oldest_issued_at": inv.issued_at,
                "aging_cents": dict(empty_aging),
            },
        )
        row["invoice_count"] += 1
        row["unpaid_cents"] += chk.balance_cents(inv)
        row["aging_cents"][bucket] += chk.balance_cents(inv)
        if inv.issued_at and (not row["oldest_issued_at"] or inv.issued_at < row["oldest_issued_at"]):
            row["oldest_issued_at"] = inv.issued_at
        payload = invoice_out(inv).model_dump()
        payload["age_days"] = days
        payload["overdue_days"] = late
        invoice_rows.append(payload)
    customers = sorted(by_shopper.values(), key=lambda r: r["unpaid_cents"], reverse=True)
    note_rows: list[CreditNote] = []
    if by_shopper:
        note_rows = list(
            db.execute(
                select(CreditNote)
                .where(CreditNote.shopper_id.in_(list(by_shopper)))
                .order_by(CreditNote.created_at.desc(), CreditNote.id.desc())
            ).scalars()
        )
    notes_by: dict[int, list[dict]] = {}
    for note in note_rows:
        bucket = notes_by.setdefault(note.shopper_id, [])
        if len(bucket) >= 8:
            continue
        bucket.append(
            {
                "id": note.id,
                "body": note.body,
                "invoice_id": note.invoice_id,
                "promised_date": getattr(note, "promised_date", None),
                "created_at": note.created_at,
            }
        )
    for row in customers:
        row["notes"] = notes_by.get(row["shopper_id"], [])
    return {
        "currency_symbol": "Rp",
        "invoice_count": len(invoices),
        "unpaid_cents": sum(chk.balance_cents(inv) for inv in invoices),
        "aging_cents": aging,
        "customers": customers,
        "invoices": invoice_rows,
        "promises_due_count": sum(
            1
            for row in customers
            if any((n.get("promised_date") or "") and n["promised_date"] <= today for n in row.get("notes") or [])
        ),
    }


@router.post("/credit/notes")
def add_credit_note(body: CreditNoteIn, db: Session = Depends(get_db)):
    text = body.body.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Note is required")
    shopper = db.get(Shopper, body.shopper_id)
    if shopper is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    invoice_id = body.invoice_id
    if invoice_id:
        inv = db.get(Invoice, invoice_id)
        if inv is None or inv.shopper_id != shopper.id:
            raise HTTPException(status_code=404, detail="Invoice not found")
    promised = (body.promised_date or "").strip()[:10] or None
    if promised:
        try:
            date.fromisoformat(promised)
        except ValueError as err:
            raise HTTPException(status_code=400, detail="promised_date must be YYYY-MM-DD") from err
    note = CreditNote(
        shopper_id=shopper.id,
        invoice_id=invoice_id,
        body=text,
        promised_date=promised,
        created_at=utcnow(),
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return {
        "id": note.id,
        "shopper_id": note.shopper_id,
        "invoice_id": note.invoice_id,
        "body": note.body,
        "promised_date": note.promised_date,
        "created_at": note.created_at,
    }


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    inv = db.execute(
        select(Invoice)
        .options(
            selectinload(Invoice.lines),
            selectinload(Invoice.shopper),
            selectinload(Invoice.purchase_order),
            selectinload(Invoice.payments),
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
            selectinload(Invoice.payments),
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
                selectinload(Invoice.payments),
            )
            .where(Invoice.id == invoice_id)
        ).scalar_one()
        return invoice_out(inv)
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.post("/invoices/{invoice_id}/unpay")
def invoice_unpaid(invoice_id: int, db: Session = Depends(get_db)):
    inv = db.execute(
        select(Invoice)
        .options(
            selectinload(Invoice.lines),
            selectinload(Invoice.shopper),
            selectinload(Invoice.purchase_order),
            selectinload(Invoice.payments),
        )
        .where(Invoice.id == invoice_id)
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        chk.mark_unpaid(db, inv)
        db.commit()
        inv = db.execute(
            select(Invoice)
            .options(
                selectinload(Invoice.lines),
                selectinload(Invoice.shopper),
                selectinload(Invoice.purchase_order),
                selectinload(Invoice.payments),
            )
            .where(Invoice.id == invoice_id)
        ).scalar_one()
        return invoice_out(inv)
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.post("/invoices/{invoice_id}/pay")
def invoice_pay(invoice_id: int, body: PaymentIn, db: Session = Depends(get_db)):
    inv = db.execute(
        select(Invoice)
        .options(
            selectinload(Invoice.lines),
            selectinload(Invoice.shopper),
            selectinload(Invoice.purchase_order),
            selectinload(Invoice.payments),
        )
        .where(Invoice.id == invoice_id)
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    try:
        chk.apply_payment(db, inv, body.amount_cents, note=body.note)
        db.commit()
        inv = db.execute(
            select(Invoice)
            .options(
                selectinload(Invoice.lines),
                selectinload(Invoice.shopper),
                selectinload(Invoice.purchase_order),
                selectinload(Invoice.payments),
            )
            .where(Invoice.id == invoice_id)
        ).scalar_one()
        return invoice_out(inv)
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.patch("/invoices/{invoice_id}/due")
def invoice_due(invoice_id: int, body: InvoiceDueIn, db: Session = Depends(get_db)):
    try:
        date.fromisoformat(body.due_date[:10])
    except ValueError as err:
        raise HTTPException(status_code=400, detail="due_date must be YYYY-MM-DD") from err
    inv = db.execute(
        select(Invoice)
        .options(
            selectinload(Invoice.lines),
            selectinload(Invoice.shopper),
            selectinload(Invoice.purchase_order),
            selectinload(Invoice.payments),
        )
        .where(Invoice.id == invoice_id)
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status == "void":
        raise HTTPException(status_code=400, detail="Void invoices cannot change due date")
    inv.due_date = body.due_date[:10]
    db.commit()
    inv = db.execute(
        select(Invoice)
        .options(
            selectinload(Invoice.lines),
            selectinload(Invoice.shopper),
            selectinload(Invoice.purchase_order),
            selectinload(Invoice.payments),
        )
        .where(Invoice.id == invoice_id)
    ).scalar_one()
    return invoice_out(inv)
