from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Invoice,
    InvoiceLine,
    Item,
    PurchaseOrder,
    PurchaseOrderLine,
    ShopSettings,
    Shopper,
)
from app.services.stock import apply_movement
from app.timeutil import utcnow


class ShortageError(Exception):
    def __init__(self, shortages: list[dict]):
        super().__init__("Insufficient stock")
        self.shortages = shortages


class CheckoutError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_settings(db: Session) -> ShopSettings:
    settings = db.get(ShopSettings, 1)
    if settings is None:
        settings = ShopSettings(
            id=1,
            name="Warung Pojok",
            address="Jl. Malioboro No. 12, Yogyakarta",
            phone="+62 274-555-0142",
            tax_rate_bps=0,
            currency_symbol="Rp",
            currency_code="IDR",
            invoice_prefix="INV",
            next_invoice_seq=1,
            po_prefix="PO",
            next_po_seq=1,
        )
        db.add(settings)
        db.flush()
        return settings
    settings.currency_symbol = "Rp"
    settings.currency_code = "IDR"
    return settings


def allocate_po_number(db: Session) -> str:
    settings = get_settings(db)
    number = f"{settings.po_prefix}-{settings.next_po_seq:04d}"
    settings.next_po_seq += 1
    db.flush()
    return number


def allocate_invoice_number(db: Session) -> str:
    settings = get_settings(db)
    year = utcnow()[:4]
    number = f"{settings.invoice_prefix}-{year}-{settings.next_invoice_seq:04d}"
    settings.next_invoice_seq += 1
    db.flush()
    return number


def load_po(db: Session, po_id: int) -> PurchaseOrder | None:
    return db.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.lines).selectinload(PurchaseOrderLine.item),
            selectinload(PurchaseOrder.shopper),
            selectinload(PurchaseOrder.invoice).selectinload(Invoice.lines),
            selectinload(PurchaseOrder.invoice).selectinload(Invoice.shopper),
        )
        .where(PurchaseOrder.id == po_id)
    ).scalar_one_or_none()


def get_draft(db: Session, shopper_id: int) -> PurchaseOrder | None:
    return db.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.lines).selectinload(PurchaseOrderLine.item),
            selectinload(PurchaseOrder.shopper),
            selectinload(PurchaseOrder.invoice),
        )
        .where(
            PurchaseOrder.shopper_id == shopper_id,
            PurchaseOrder.status == "draft",
        )
    ).scalar_one_or_none()


def get_or_create_draft(db: Session, shopper_id: int) -> PurchaseOrder:
    po = get_draft(db, shopper_id)
    if po:
        return po
    now = utcnow()
    po = PurchaseOrder(
        number=allocate_po_number(db),
        shopper_id=shopper_id,
        status="draft",
        note="",
        created_at=now,
        updated_at=now,
    )
    db.add(po)
    db.flush()
    return load_po(db, po.id) or po


def upsert_line(db: Session, po: PurchaseOrder, item_id: int, quantity: int) -> PurchaseOrder:
    if po.status != "draft":
        raise CheckoutError("Only a draft purchase order can be edited")
    item = db.get(Item, item_id)
    if item is None or item.archived:
        raise CheckoutError("Item is not available", 404)
    if quantity <= 0:
        raise CheckoutError("Quantity must be greater than 0")
    if item.quantity < quantity:
        raise ShortageError(
            [
                {
                    "item_id": item.id,
                    "sku": item.sku,
                    "name": item.name,
                    "name_id": item.name_id or item.name,
                    "requested": quantity,
                    "available": item.quantity,
                }
            ]
        )
    line = next((ln for ln in po.lines if ln.item_id == item_id), None)
    if line is None:
        db.add(
            PurchaseOrderLine(
                purchase_order_id=po.id,
                item_id=item.id,
                quantity=quantity,
                sku=item.sku,
                name=item.name,
                name_id=item.name_id or item.name,
                unit_price_cents=item.unit_price_cents,
            )
        )
    else:
        line.quantity = quantity
        line.sku = item.sku
        line.name = item.name
        line.name_id = item.name_id or item.name
        line.unit_price_cents = item.unit_price_cents
    po.updated_at = utcnow()
    db.flush()
    loaded = load_po(db, po.id)
    assert loaded is not None
    return loaded


def remove_line(db: Session, po: PurchaseOrder, item_id: int) -> PurchaseOrder:
    if po.status != "draft":
        raise CheckoutError("Only a draft purchase order can be edited")
    line = next((ln for ln in po.lines if ln.item_id == item_id), None)
    if line is None:
        raise CheckoutError("Line not found", 404)
    db.delete(line)
    po.updated_at = utcnow()
    db.flush()
    loaded = load_po(db, po.id)
    assert loaded is not None
    return loaded


def line_total(quantity: int, unit_price_cents: int) -> int:
    return quantity * unit_price_cents


def compute_tax_cents(subtotal: int, tax_bps: int) -> int:
    return int(round(subtotal * tax_bps / 10000))


def place_order(db: Session, po: PurchaseOrder, note: str | None = None) -> tuple[PurchaseOrder, Invoice]:
    """Place a draft PO: stock out every line and raise an invoice in one transaction."""
    if po.status != "draft":
        raise CheckoutError("Only a draft purchase order can be placed")
    if not po.lines:
        raise CheckoutError("Add at least one item before placing the order")

    settings = get_settings(db)
    now = utcnow()
    if note is not None:
        po.note = note

    shortages: list[dict] = []
    live_items: dict[int, Item] = {}
    for line in po.lines:
        item = db.get(Item, line.item_id)
        if item is None or item.archived:
            shortages.append(
                {
                    "item_id": line.item_id,
                    "sku": line.sku,
                    "name": line.name,
                    "name_id": line.name_id or line.name,
                    "requested": line.quantity,
                    "available": 0,
                }
            )
            continue
        live_items[item.id] = item
        if item.quantity < line.quantity:
            shortages.append(
                {
                    "item_id": item.id,
                    "sku": item.sku,
                    "name": item.name,
                    "name_id": item.name_id or item.name,
                    "requested": line.quantity,
                    "available": item.quantity,
                }
            )
    if shortages:
        raise ShortageError(shortages)

    movements = []
    subtotal = 0
    for line in po.lines:
        item = live_items[line.item_id]
        line.sku = item.sku
        line.name = item.name
        line.name_id = item.name_id or item.name
        line.unit_price_cents = item.unit_price_cents
        mov = apply_movement(
            db,
            item_id=item.id,
            kind="out",
            quantity=line.quantity,
            reason=f"Sale {po.number}",
            purchase_order_id=po.id,
        )
        movements.append(mov)
        subtotal += line_total(line.quantity, line.unit_price_cents)

    tax_bps = settings.tax_rate_bps
    tax = compute_tax_cents(subtotal, tax_bps)
    invoice = Invoice(
        number=allocate_invoice_number(db),
        purchase_order_id=po.id,
        shopper_id=po.shopper_id,
        status="issued",
        subtotal_cents=subtotal,
        tax_bps=tax_bps,
        tax_cents=tax,
        total_cents=subtotal + tax,
        shop_name=settings.name,
        shop_address=settings.address,
        shop_phone=settings.phone,
        currency_symbol="Rp",
        issued_at=now,
    )
    db.add(invoice)
    db.flush()

    for line in po.lines:
        db.add(
            InvoiceLine(
                invoice_id=invoice.id,
                sku=line.sku,
                name=line.name,
                name_id=line.name_id or line.name,
                quantity=line.quantity,
                unit_price_cents=line.unit_price_cents,
                line_total_cents=line_total(line.quantity, line.unit_price_cents),
            )
        )

    for mov in movements:
        mov.invoice_id = invoice.id

    po.status = "placed"
    po.placed_at = now
    po.updated_at = now
    db.flush()
    db.expire_all()
    loaded = load_po(db, po.id)
    assert loaded is not None and loaded.invoice is not None
    return loaded, loaded.invoice


def cancel_order(db: Session, po: PurchaseOrder) -> PurchaseOrder:
    if po.status != "placed":
        raise CheckoutError("Only a placed order can be cancelled")
    invoice = db.execute(select(Invoice).where(Invoice.purchase_order_id == po.id)).scalar_one_or_none()
    if invoice is None:
        raise CheckoutError("Invoice missing for placed order")
    if invoice.status == "paid":
        raise CheckoutError("Paid invoices cannot be cancelled")
    if invoice.status == "void":
        raise CheckoutError("Invoice is already void")

    now = utcnow()
    for line in po.lines:
        apply_movement(
            db,
            item_id=line.item_id,
            kind="in",
            quantity=line.quantity,
            reason=f"Cancel {po.number}",
            purchase_order_id=po.id,
            invoice_id=invoice.id,
        )
    invoice.status = "void"
    invoice.voided_at = now
    po.status = "cancelled"
    po.cancelled_at = now
    po.updated_at = now
    db.flush()
    db.expire_all()
    loaded = load_po(db, po.id)
    assert loaded is not None
    return loaded


def mark_paid(db: Session, invoice: Invoice) -> Invoice:
    if invoice.status != "issued":
        raise CheckoutError("Only an issued invoice can be marked paid")
    invoice.status = "paid"
    invoice.paid_at = utcnow()
    db.flush()
    return invoice


def upsert_shopper(db: Session, name: str, phone: str, email: str = "") -> Shopper:
    phone = "".join(ch for ch in phone.strip() if ch.isdigit() or ch == "+")
    name = name.strip()
    if not name:
        raise CheckoutError("Name is required")
    if len(phone) < 6:
        raise CheckoutError("Phone is required")
    existing = db.execute(select(Shopper).where(Shopper.phone == phone)).scalar_one_or_none()
    if existing:
        existing.name = name
        if email:
            existing.email = email.strip()
        db.flush()
        return existing
    shopper = Shopper(name=name, phone=phone, email=email.strip(), created_at=utcnow())
    db.add(shopper)
    db.flush()
    return shopper
