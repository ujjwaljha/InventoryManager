from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Item, LotConsumption, StockLot, StockMovement
from app.timeutil import utcnow


class StockError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def lot_stats(item: Item) -> tuple[int, int]:
    """Weighted FIFO unit COGS and inventory value of remaining lots."""
    remaining = [lot for lot in (item.lots or []) if lot.qty_remaining > 0]
    qty = sum(lot.qty_remaining for lot in remaining)
    value = sum(lot.qty_remaining * lot.unit_cost_cents for lot in remaining)
    if qty <= 0:
        return item.unit_cost_cents, 0
    return value // qty, value


def remaining_lot_qty(db: Session, item_id: int) -> int:
    lots = db.scalars(select(StockLot).where(StockLot.item_id == item_id)).all()
    return sum(lot.qty_remaining for lot in lots)


def ensure_lots_cover(db: Session, item: Item) -> None:
    """If on-hand is ahead of FIFO layers (legacy rows), add an opening lot."""
    covered = remaining_lot_qty(db, item.id)
    gap = item.quantity - covered
    if gap <= 0:
        return
    now = utcnow()
    db.add(
        StockLot(
            item_id=item.id,
            received_at=item.created_at or now,
            unit_cost_cents=item.unit_cost_cents,
            qty_original=gap,
            qty_remaining=gap,
            source="opening",
        )
    )
    db.flush()


def create_lot(
    db: Session,
    *,
    item: Item,
    quantity: int,
    unit_cost_cents: int,
    source: str,
    restock_id: int | None = None,
    movement_id: int | None = None,
    received_at: str | None = None,
) -> StockLot:
    lot = StockLot(
        item_id=item.id,
        received_at=received_at or utcnow(),
        unit_cost_cents=max(0, unit_cost_cents),
        qty_original=quantity,
        qty_remaining=quantity,
        source=source,
        restock_id=restock_id,
        movement_id=movement_id,
    )
    db.add(lot)
    db.flush()
    return lot


def consume_fifo(db: Session, item: Item, quantity: int, movement: StockMovement) -> int:
    """Take quantity from oldest remaining lots. Returns total COGS in sen."""
    ensure_lots_cover(db, item)
    remaining = quantity
    total_cogs = 0
    lots = db.scalars(
        select(StockLot)
        .where(StockLot.item_id == item.id, StockLot.qty_remaining > 0)
        .order_by(StockLot.received_at.asc(), StockLot.id.asc())
    ).all()
    for lot in lots:
        if remaining <= 0:
            break
        take = min(lot.qty_remaining, remaining)
        lot.qty_remaining -= take
        remaining -= take
        total_cogs += take * lot.unit_cost_cents
        db.add(
            LotConsumption(
                lot_id=lot.id,
                movement_id=movement.id,
                quantity=take,
                unit_cost_cents=lot.unit_cost_cents,
            )
        )
    if remaining > 0:
        # Last resort: cost the uncovered qty at last purchase cost.
        total_cogs += remaining * item.unit_cost_cents
        remaining = 0
    db.flush()
    return total_cogs


def restore_consumptions(db: Session, movement: StockMovement) -> int:
    """Put FIFO layers back after a cancelled sale. Returns restored COGS."""
    total = 0
    cons = list(movement.consumptions)
    if not cons:
        cons = list(
            db.scalars(select(LotConsumption).where(LotConsumption.movement_id == movement.id)).all()
        )
    for row in cons:
        lot = db.get(StockLot, row.lot_id)
        if lot is None:
            continue
        lot.qty_remaining += row.quantity
        total += row.quantity * row.unit_cost_cents
        db.delete(row)
    db.flush()
    return total


def restore_outbound(
    db: Session,
    *,
    movement: StockMovement,
    reason: str,
    purpose: str = "cancel",
) -> StockMovement:
    item = db.get(Item, movement.item_id)
    if item is None:
        raise StockError("Item not found")
    qty = abs(movement.quantity_delta)
    cogs = restore_consumptions(db, movement)
    if cogs == 0 and qty:
        # Legacy movement with no lot rows: treat as a new inbound layer at last cost.
        cogs = qty * item.unit_cost_cents
        create_lot(
            db,
            item=item,
            quantity=qty,
            unit_cost_cents=item.unit_cost_cents,
            source="restore",
        )
    item.quantity += qty
    now = utcnow()
    item.updated_at = now
    inbound = StockMovement(
        item_id=item.id,
        kind="in",
        quantity_delta=qty,
        quantity_after=item.quantity,
        reason=reason,
        purpose=purpose,
        cogs_cents=cogs,
        unit_cost_cents=(cogs // qty) if qty else 0,
        purchase_order_id=movement.purchase_order_id,
        invoice_id=movement.invoice_id,
        created_at=now,
    )
    db.add(inbound)
    db.flush()
    return inbound


def apply_movement(
    db: Session,
    *,
    item_id: int,
    kind: str,
    quantity: int,
    reason: str = "",
    purchase_order_id: int | None = None,
    invoice_id: int | None = None,
    restock_id: int | None = None,
    damage_id: int | None = None,
    supplier_return_id: int | None = None,
    purpose: str = "",
    unit_cost_cents: int | None = None,
) -> StockMovement:
    item = db.get(Item, item_id)
    if item is None:
        raise StockError("Item not found")
    if item.archived and kind != "adjust":
        raise StockError("Item is archived")

    kind = kind.lower().strip()
    if kind not in ("in", "out", "adjust"):
        raise StockError("kind must be in, out, or adjust")

    cost = item.unit_cost_cents if unit_cost_cents is None else max(0, int(unit_cost_cents))
    purpose = (purpose or "").strip()
    cogs = 0
    inbound_qty = 0
    inbound_source = purpose or "receive"

    if kind == "in":
        if quantity <= 0:
            raise StockError("Quantity must be greater than 0")
        item.quantity += quantity
        delta = quantity
        inbound_qty = quantity
        if purpose == "purchase":
            item.unit_cost_cents = cost
            inbound_source = "purchase"
        elif purpose == "opening":
            inbound_source = "opening"
        else:
            inbound_source = purpose or "receive"
            if unit_cost_cents is not None:
                item.unit_cost_cents = cost
        cogs = quantity * cost
    elif kind == "out":
        if quantity <= 0:
            raise StockError("Quantity must be greater than 0")
        if item.quantity < quantity:
            raise StockError(
                f"Insufficient stock for {item.sku}: have {item.quantity}, need {quantity}"
            )
        item.quantity -= quantity
        delta = -quantity
        if not purpose:
            purpose = "shrinkage"
    else:
        if quantity < 0:
            raise StockError("Count cannot be negative")
        delta = quantity - item.quantity
        item.quantity = quantity
        purpose = purpose or "adjust"
        if delta > 0:
            inbound_qty = delta
            inbound_source = "adjust"
            cogs = delta * cost
        elif delta < 0:
            pass  # consume after the movement row exists

    now = utcnow()
    item.updated_at = now
    movement = StockMovement(
        item_id=item.id,
        kind=kind,
        quantity_delta=delta,
        quantity_after=item.quantity,
        reason=reason or "",
        purpose=purpose,
        cogs_cents=cogs,
        unit_cost_cents=cost,
        purchase_order_id=purchase_order_id,
        invoice_id=invoice_id,
        restock_id=restock_id,
        damage_id=damage_id,
        supplier_return_id=supplier_return_id,
        created_at=now,
    )
    db.add(movement)
    db.flush()

    if inbound_qty > 0:
        create_lot(
            db,
            item=item,
            quantity=inbound_qty,
            unit_cost_cents=cost,
            source=inbound_source,
            restock_id=restock_id,
            movement_id=movement.id,
            received_at=now,
        )
        movement.cogs_cents = inbound_qty * cost
    elif delta < 0:
        consumed = consume_fifo(db, item, abs(delta), movement)
        movement.cogs_cents = consumed
        movement.unit_cost_cents = (consumed // abs(delta)) if delta else cost

    db.flush()
    return movement


def backfill_opening_lots(db: Session) -> None:
    items = db.scalars(select(Item)).all()
    for item in items:
        ensure_lots_cover(db, item)


def stock_http(err: StockError) -> HTTPException:
    status = 404 if err.message == "Item not found" else 400
    if "Insufficient stock" in err.message:
        status = 409
    return HTTPException(status_code=status, detail=err.message)
