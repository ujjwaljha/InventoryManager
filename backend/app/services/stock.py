from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Item, StockMovement
from app.timeutil import utcnow


class StockError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def apply_movement(
    db: Session,
    *,
    item_id: int,
    kind: str,
    quantity: int,
    reason: str = "",
    purchase_order_id: int | None = None,
    invoice_id: int | None = None,
) -> StockMovement:
    item = db.get(Item, item_id)
    if item is None:
        raise StockError("Item not found")
    if item.archived and kind != "adjust":
        raise StockError("Item is archived")

    kind = kind.lower().strip()
    if kind not in ("in", "out", "adjust"):
        raise StockError("kind must be in, out, or adjust")

    if kind == "in":
        if quantity <= 0:
            raise StockError("Quantity must be greater than 0")
        item.quantity += quantity
        delta = quantity
    elif kind == "out":
        if quantity <= 0:
            raise StockError("Quantity must be greater than 0")
        if item.quantity < quantity:
            raise StockError(
                f"Insufficient stock for {item.sku}: have {item.quantity}, need {quantity}"
            )
        item.quantity -= quantity
        delta = -quantity
    else:
        if quantity < 0:
            raise StockError("Count cannot be negative")
        delta = quantity - item.quantity
        item.quantity = quantity

    now = utcnow()
    item.updated_at = now
    movement = StockMovement(
        item_id=item.id,
        kind=kind,
        quantity_delta=delta,
        quantity_after=item.quantity,
        reason=reason or "",
        purchase_order_id=purchase_order_id,
        invoice_id=invoice_id,
        created_at=now,
    )
    db.add(movement)
    db.flush()
    return movement


def stock_http(err: StockError) -> HTTPException:
    status = 404 if err.message == "Item not found" else 400
    if "Insufficient stock" in err.message:
        status = 409
    return HTTPException(status_code=status, detail=err.message)
