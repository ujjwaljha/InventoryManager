from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    DamageLine,
    DamageNote,
    Item,
    Restock,
    RestockLine,
    Supplier,
    SupplierReturn,
    SupplierReturnLine,
)
from app.services import checkout as chk
from app.services.stock import StockError, apply_movement
from app.timeutil import utcnow


def allocate_seq(db: Session, prefix_attr: str, seq_attr: str) -> str:
    settings = chk.get_settings(db)
    prefix = getattr(settings, prefix_attr) or "DOC"
    seq = int(getattr(settings, seq_attr) or 1)
    number = f"{prefix}-{seq:04d}"
    setattr(settings, seq_attr, seq + 1)
    db.flush()
    return number


def upsert_supplier(db: Session, name: str, phone: str = "", notes: str = "") -> Supplier:
    name = name.strip()
    if not name:
        raise chk.CheckoutError("Supplier name is required")
    phone = phone.strip()
    if phone:
        existing = db.execute(select(Supplier).where(Supplier.phone == phone)).scalar_one_or_none()
        if existing:
            existing.name = name
            if notes:
                existing.notes = notes
            db.flush()
            return existing
    existing = db.execute(select(Supplier).where(Supplier.name == name)).scalar_one_or_none()
    if existing:
        if phone:
            existing.phone = phone
        if notes:
            existing.notes = notes
        db.flush()
        return existing
    row = Supplier(name=name, phone=phone, notes=notes.strip(), created_at=utcnow())
    db.add(row)
    db.flush()
    return row


def load_restock(db: Session, restock_id: int) -> Restock | None:
    return db.execute(
        select(Restock)
        .options(
            selectinload(Restock.lines).selectinload(RestockLine.item),
            selectinload(Restock.supplier),
        )
        .where(Restock.id == restock_id)
    ).scalar_one_or_none()


def create_restock(db: Session, supplier: Supplier | None, note: str = "") -> Restock:
    now = utcnow()
    row = Restock(
        number=allocate_seq(db, "restock_prefix", "next_restock_seq"),
        supplier_id=supplier.id if supplier else None,
        status="draft",
        note=note or "",
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.flush()
    loaded = load_restock(db, row.id)
    assert loaded is not None
    return loaded


def upsert_restock_line(db: Session, restock: Restock, item_id: int, quantity: int, unit_cost_cents: int) -> Restock:
    if restock.status != "draft":
        raise chk.CheckoutError("Only a draft restock can be edited")
    item = db.get(Item, item_id)
    if item is None or item.archived:
        raise chk.CheckoutError("Item is not available", 404)
    if quantity <= 0:
        raise chk.CheckoutError("Quantity must be greater than 0")
    if unit_cost_cents < 0:
        raise chk.CheckoutError("Cost cannot be negative")
    line = next((ln for ln in restock.lines if ln.item_id == item_id), None)
    if line is None:
        restock.lines.append(
            RestockLine(
                item_id=item.id,
                quantity=quantity,
                sku=item.sku,
                name=item.name,
                name_id=item.name_id or item.name,
                unit_cost_cents=unit_cost_cents,
            )
        )
    else:
        line.quantity = quantity
        line.sku = item.sku
        line.name = item.name
        line.name_id = item.name_id or item.name
        line.unit_cost_cents = unit_cost_cents
    restock.updated_at = utcnow()
    db.flush()
    db.expire(restock, ["lines"])
    loaded = load_restock(db, restock.id)
    assert loaded is not None
    return loaded


def remove_restock_line(db: Session, restock: Restock, item_id: int) -> Restock:
    if restock.status != "draft":
        raise chk.CheckoutError("Only a draft restock can be edited")
    line = next((ln for ln in restock.lines if ln.item_id == item_id), None)
    if line is None:
        raise chk.CheckoutError("Line not found", 404)
    db.delete(line)
    restock.updated_at = utcnow()
    db.flush()
    loaded = load_restock(db, restock.id)
    assert loaded is not None
    return loaded


def receive_restock(db: Session, restock: Restock) -> Restock:
    if restock.status != "draft":
        raise chk.CheckoutError("This restock was already received")
    if not restock.lines:
        raise chk.CheckoutError("Add at least one item before receiving")
    now = utcnow()
    for line in restock.lines:
        item = db.get(Item, line.item_id)
        if item is None or item.archived:
            raise chk.CheckoutError(f"Item {line.sku} is not available", 404)
        line.sku = item.sku
        line.name = item.name
        line.name_id = item.name_id or item.name
        apply_movement(
            db,
            item_id=item.id,
            kind="in",
            quantity=line.quantity,
            reason=f"Restock {restock.number}",
            purpose="purchase",
            unit_cost_cents=line.unit_cost_cents,
            restock_id=restock.id,
        )
    restock.status = "received"
    restock.received_at = now
    restock.updated_at = now
    db.flush()
    loaded = load_restock(db, restock.id)
    assert loaded is not None
    return loaded


def record_damage(db: Session, reason: str, lines: list[tuple[int, int]]) -> DamageNote:
    reason = reason.strip()
    if not reason:
        raise chk.CheckoutError("Reason is required")
    if not lines:
        raise chk.CheckoutError("Add at least one damaged item")
    now = utcnow()
    note = DamageNote(
        number=allocate_seq(db, "damage_prefix", "next_damage_seq"),
        reason=reason,
        created_at=now,
        cogs_cents=0,
    )
    db.add(note)
    db.flush()
    total_cogs = 0
    for item_id, quantity in lines:
        item = db.get(Item, item_id)
        if item is None or item.archived:
            raise chk.CheckoutError("Item is not available", 404)
        if quantity <= 0:
            raise chk.CheckoutError("Quantity must be greater than 0")
        mov = apply_movement(
            db,
            item_id=item.id,
            kind="out",
            quantity=quantity,
            reason=f"Damage {note.number}: {reason}",
            purpose="damage",
            damage_id=note.id,
        )
        db.add(
            DamageLine(
                damage_id=note.id,
                item_id=item.id,
                quantity=quantity,
                sku=item.sku,
                name=item.name,
                name_id=item.name_id or item.name,
                cogs_cents=mov.cogs_cents,
            )
        )
        total_cogs += mov.cogs_cents
    note.cogs_cents = total_cogs
    db.flush()
    loaded = db.execute(
        select(DamageNote)
        .options(selectinload(DamageNote.lines).selectinload(DamageLine.item))
        .where(DamageNote.id == note.id)
    ).scalar_one()
    return loaded


def record_supplier_return(
    db: Session,
    reason: str,
    lines: list[tuple[int, int]],
    supplier: Supplier | None = None,
) -> SupplierReturn:
    reason = reason.strip()
    if not reason:
        raise chk.CheckoutError("Reason is required")
    if not lines:
        raise chk.CheckoutError("Add at least one item to return")
    now = utcnow()
    row = SupplierReturn(
        number=allocate_seq(db, "return_prefix", "next_return_seq"),
        supplier_id=supplier.id if supplier else None,
        reason=reason,
        created_at=now,
        cogs_cents=0,
    )
    db.add(row)
    db.flush()
    total_cogs = 0
    for item_id, quantity in lines:
        item = db.get(Item, item_id)
        if item is None or item.archived:
            raise chk.CheckoutError("Item is not available", 404)
        if quantity <= 0:
            raise chk.CheckoutError("Quantity must be greater than 0")
        mov = apply_movement(
            db,
            item_id=item.id,
            kind="out",
            quantity=quantity,
            reason=f"Supplier return {row.number}: {reason}",
            purpose="supplier_return",
            supplier_return_id=row.id,
        )
        db.add(
            SupplierReturnLine(
                supplier_return_id=row.id,
                item_id=item.id,
                quantity=quantity,
                sku=item.sku,
                name=item.name,
                name_id=item.name_id or item.name,
                cogs_cents=mov.cogs_cents,
            )
        )
        total_cogs += mov.cogs_cents
    row.cogs_cents = total_cogs
    db.flush()
    return db.execute(
        select(SupplierReturn)
        .options(
            selectinload(SupplierReturn.lines).selectinload(SupplierReturnLine.item),
            selectinload(SupplierReturn.supplier),
        )
        .where(SupplierReturn.id == row.id)
    ).scalar_one()


def till_sale(
    db: Session,
    *,
    customer_name: str,
    customer_phone: str,
    salesperson_name: str,
    lines: list[tuple[int, int]],
    note: str = "",
):
    """Create a draft PO, add lines at sell price, place it, return (po, invoice)."""
    if not lines:
        raise chk.CheckoutError("Add at least one item")
    shopper = chk.upsert_shopper(db, customer_name, customer_phone)
    po = chk.create_fresh_draft(db, shopper.id)
    for item_id, quantity in lines:
        po = chk.upsert_line(db, po, item_id, quantity)
    db.expire(po, ["lines"])
    po = chk.load_po(db, po.id) or po
    po, invoice = chk.place_order(db, po, note=note, salesperson_name=salesperson_name)
    return po, invoice
