from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Invoice,
    InvoiceLine,
    InvoicePayment,
    Item,
    PurchaseOrder,
    PurchaseOrderLine,
    ShopSettings,
    Shopper,
    StockMovement,
)
from app.qty import from_store, money_qty
from app.services.stock import apply_movement, restore_outbound
from app.timeutil import add_shop_days, today_shop, utcnow


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
            name="Toko Bangunan Makmur",
            address="Jl. Magelang Km. 5, Yogyakarta",
            phone="+62 274-555-2210",
            tax_rate_bps=0,
            currency_symbol="Rp",
            currency_code="IDR",
            invoice_prefix="INV",
            next_invoice_seq=1,
            po_prefix="PO",
            next_po_seq=1,
            restock_prefix="RST",
            next_restock_seq=1,
            damage_prefix="DMG",
            next_damage_seq=1,
            return_prefix="RTN",
            next_return_seq=1,
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
            selectinload(PurchaseOrder.invoice).selectinload(Invoice.payments),
        )
        .where(PurchaseOrder.id == po_id)
    ).scalar_one_or_none()


def get_draft(db: Session, shopper_id: int) -> PurchaseOrder | None:
    rows = list(
        db.execute(
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
            .order_by(PurchaseOrder.updated_at.desc(), PurchaseOrder.id.desc())
        ).scalars()
    )
    if not rows:
        return None
    with_lines = [po for po in rows if po.lines]
    return with_lines[0] if with_lines else rows[0]


def draft_reserved(
    db: Session,
    item_ids: list[int] | None = None,
    exclude_po_id: int | None = None,
    exclude_shopper_id: int | None = None,
) -> dict[int, int]:
    """Qty sitting in other (or all) draft carts, keyed by item_id."""
    stmt = (
        select(PurchaseOrderLine.item_id, func.coalesce(func.sum(PurchaseOrderLine.quantity), 0))
        .join(PurchaseOrder, PurchaseOrderLine.purchase_order_id == PurchaseOrder.id)
        .where(PurchaseOrder.status == "draft")
        .group_by(PurchaseOrderLine.item_id)
    )
    if item_ids:
        stmt = stmt.where(PurchaseOrderLine.item_id.in_(item_ids))
    if exclude_po_id is not None:
        stmt = stmt.where(PurchaseOrder.id != exclude_po_id)
    if exclude_shopper_id is not None:
        stmt = stmt.where(PurchaseOrder.shopper_id != exclude_shopper_id)
    return {int(item_id): int(qty) for item_id, qty in db.execute(stmt)}


def sellable_qty(
    db: Session,
    item: Item,
    exclude_po_id: int | None = None,
    exclude_shopper_id: int | None = None,
) -> int:
    reserved = draft_reserved(
        db, [item.id], exclude_po_id=exclude_po_id, exclude_shopper_id=exclude_shopper_id
    ).get(item.id, 0)
    return max(0, item.quantity - reserved)


def require_sellable(
    db: Session,
    item: Item,
    quantity: int,
    exclude_po_id: int | None = None,
    exclude_shopper_id: int | None = None,
) -> None:
    available = sellable_qty(
        db, item, exclude_po_id=exclude_po_id, exclude_shopper_id=exclude_shopper_id
    )
    if available < quantity:
        raise ShortageError(
            [
                {
                    "item_id": item.id,
                    "sku": item.sku,
                    "name": item.name,
                    "name_id": item.name_id or item.name,
                    "requested": from_store(quantity),
                    "available": from_store(available),
                }
            ]
        )


def abandon_drafts(db: Session, shopper_id: int) -> int:
    rows = list(
        db.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.shopper_id == shopper_id,
                PurchaseOrder.status == "draft",
            )
        ).scalars()
    )
    for po in rows:
        db.delete(po)
    if rows:
        db.flush()
    return len(rows)


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


def upsert_line(
    db: Session,
    po: PurchaseOrder,
    item_id: int,
    quantity: int,
    ignore_own_holds: bool = False,
) -> PurchaseOrder:
    if po.status != "draft":
        raise CheckoutError("Only a draft purchase order can be edited")
    item = db.get(Item, item_id)
    if item is None or item.archived:
        raise CheckoutError("Item is not available", 404)
    if quantity <= 0:
        raise CheckoutError("Quantity must be greater than 0")
    available = sellable_qty(
        db,
        item,
        exclude_po_id=None if ignore_own_holds else po.id,
        exclude_shopper_id=po.shopper_id if ignore_own_holds else None,
    )
    if available < quantity:
        raise ShortageError(
            [
                {
                    "item_id": item.id,
                    "sku": item.sku,
                    "name": item.name,
                    "name_id": item.name_id or item.name,
                    "requested": from_store(quantity),
                    "available": from_store(available),
                }
            ]
        )
    line = next((ln for ln in po.lines if ln.item_id == item_id), None)
    if line is None:
        po.lines.append(
            PurchaseOrderLine(
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
    db.expire(po, ["lines"])
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
    return money_qty(quantity, unit_price_cents)


def compute_tax_cents(subtotal: int, tax_bps: int) -> int:
    return int(round(subtotal * tax_bps / 10000))


def create_fresh_draft(db: Session, shopper_id: int) -> PurchaseOrder:
    """Always start a new draft (till sales must not mix with an open shop cart)."""
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
    loaded = load_po(db, po.id)
    assert loaded is not None
    return loaded


def begin_immediate(db: Session) -> None:
    """Take a SQLite reserved lock so two places cannot both pass the stock check."""
    if db.get_bind().dialect.name != "sqlite":
        return
    db.execute(text("UPDATE shop_settings SET id = 1 WHERE id = 1"))


def place_order(
    db: Session,
    po: PurchaseOrder,
    note: str | None = None,
    salesperson_name: str = "",
) -> tuple[PurchaseOrder, Invoice]:
    """Place a draft PO: FIFO stock out every line and raise an invoice in one transaction."""
    begin_immediate(db)
    if po.status != "draft":
        raise CheckoutError("Only a draft purchase order can be placed")
    if not list(po.lines):
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
                    "requested": from_store(line.quantity),
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
                    "requested": from_store(line.quantity),
                    "available": from_store(item.quantity),
                }
            )
    if shortages:
        raise ShortageError(shortages)

    movements: list[StockMovement] = []
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
            purpose="sale",
        )
        movements.append(mov)
        subtotal += line_total(line.quantity, line.unit_price_cents)

    tax_bps = settings.tax_rate_bps
    tax = compute_tax_cents(subtotal, tax_bps)
    invoice_cogs = sum(mov.cogs_cents for mov in movements)
    invoice = Invoice(
        number=allocate_invoice_number(db),
        purchase_order_id=po.id,
        shopper_id=po.shopper_id,
        status="issued",
        subtotal_cents=subtotal,
        tax_bps=tax_bps,
        tax_cents=tax,
        total_cents=subtotal + tax,
        cogs_cents=invoice_cogs,
        shop_name=settings.name,
        shop_address=settings.address,
        shop_phone=settings.phone,
        currency_symbol="Rp",
        salesperson_name=(salesperson_name or "").strip(),
        issued_at=now,
        due_date=add_shop_days(today_shop(), int(getattr(settings, "credit_days", 30) or 0)),
    )
    db.add(invoice)
    db.flush()

    for line, mov in zip(po.lines, movements, strict=True):
        db.add(
            InvoiceLine(
                invoice_id=invoice.id,
                sku=line.sku,
                name=line.name,
                name_id=line.name_id or line.name,
                quantity=line.quantity,
                unit=live_items[line.item_id].unit or "ea",
                unit_price_cents=line.unit_price_cents,
                line_total_cents=line_total(line.quantity, line.unit_price_cents),
                cogs_cents=mov.cogs_cents,
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
    movements = list(
        db.scalars(
            select(StockMovement)
            .options(selectinload(StockMovement.consumptions))
            .where(
                StockMovement.purchase_order_id == po.id,
                StockMovement.kind == "out",
            )
            .order_by(StockMovement.id.asc())
        ).all()
    )
    if movements:
        for mov in movements:
            restore_outbound(db, movement=mov, reason=f"Cancel {po.number}", purpose="cancel")
    else:
        for line in po.lines:
            apply_movement(
                db,
                item_id=line.item_id,
                kind="in",
                quantity=line.quantity,
                reason=f"Cancel {po.number}",
                purchase_order_id=po.id,
                invoice_id=invoice.id,
                purpose="cancel",
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


def paid_cents(invoice: Invoice) -> int:
    return sum(p.amount_cents for p in (invoice.payments or []))


def balance_cents(invoice: Invoice) -> int:
    return max(0, invoice.total_cents - paid_cents(invoice))


def apply_payment(db: Session, invoice: Invoice, amount_cents: int, note: str = "") -> Invoice:
    if invoice.status == "void":
        raise CheckoutError("Void invoices cannot take payment")
    if invoice.status == "paid":
        raise CheckoutError("Invoice is already paid")
    remaining = balance_cents(invoice)
    if amount_cents <= 0:
        raise CheckoutError("Payment must be greater than 0")
    if amount_cents > remaining:
        raise CheckoutError("Payment is more than the remaining balance")
    db.add(
        InvoicePayment(
            invoice_id=invoice.id,
            amount_cents=amount_cents,
            note=(note or "").strip(),
            created_at=utcnow(),
        )
    )
    if amount_cents == remaining:
        invoice.status = "paid"
        invoice.paid_at = utcnow()
    db.flush()
    db.expire(invoice, ["payments"])
    return invoice


def mark_paid(db: Session, invoice: Invoice) -> Invoice:
    if invoice.status != "issued":
        raise CheckoutError("Only an issued invoice can be marked paid")
    remaining = balance_cents(invoice)
    if remaining <= 0:
        invoice.status = "paid"
        invoice.paid_at = invoice.paid_at or utcnow()
        db.flush()
        return invoice
    return apply_payment(db, invoice, remaining, note="Paid in full")


def mark_unpaid(db: Session, invoice: Invoice) -> Invoice:
    if invoice.status == "void":
        raise CheckoutError("Void invoices cannot be unpaid")
    if invoice.status != "paid" and not invoice.payments:
        raise CheckoutError("Only a paid or partly paid invoice can be marked unpaid")
    for payment in list(invoice.payments or []):
        db.delete(payment)
    invoice.status = "issued"
    invoice.paid_at = None
    db.flush()
    db.expire(invoice, ["payments"])
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
