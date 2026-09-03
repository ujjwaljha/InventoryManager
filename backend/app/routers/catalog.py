from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import delete as sql_delete, or_, select, update
from sqlalchemy.orm import Session, selectinload

from app.deps import get_db, raise_checkout
from app.models import (
    Category,
    DamageLine,
    Item,
    Location,
    LotConsumption,
    PurchaseOrderLine,
    RestockLine,
    StockLot,
    StockMovement,
    SupplierReturnLine,
)
from app.qty import from_store, to_store
from app.schemas import CategoryIn, ItemIn, ItemPatch, LocationIn, MovementIn
from app.serialize import item_out, movement_out
from app.services import checkout as chk
from app.services.stock import StockError, apply_movement, stock_http
from app.timeutil import utcnow

router = APIRouter(prefix="/api", tags=["catalog"])


def _item_matches(item: Item, needle: str) -> bool:
    fields = (
        item.name,
        item.name_id or "",
        item.sku,
        item.description or "",
        item.description_id or "",
        item.notes or "",
    )
    return any(needle in (field or "").lower() for field in fields)


def _item_in_use(db: Session, item_id: int) -> bool:
    for model in (PurchaseOrderLine, RestockLine, DamageLine, SupplierReturnLine):
        if db.scalar(select(model.id).where(model.item_id == item_id).limit(1)):
            return True
    linked_move = db.scalar(
        select(StockMovement.id)
        .where(
            StockMovement.item_id == item_id,
            or_(
                StockMovement.purchase_order_id.is_not(None),
                StockMovement.invoice_id.is_not(None),
                StockMovement.restock_id.is_not(None),
                StockMovement.damage_id.is_not(None),
                StockMovement.supplier_return_id.is_not(None),
            ),
        )
        .limit(1)
    )
    if linked_move:
        return True
    linked_lot = db.scalar(
        select(StockLot.id).where(StockLot.item_id == item_id, StockLot.restock_id.is_not(None)).limit(1)
    )
    return linked_lot is not None


def _purge_item_stock(db: Session, item_id: int) -> None:
    lot_ids = list(db.execute(select(StockLot.id).where(StockLot.item_id == item_id)).scalars())
    move_ids = list(db.execute(select(StockMovement.id).where(StockMovement.item_id == item_id)).scalars())
    if lot_ids:
        db.execute(sql_delete(LotConsumption).where(LotConsumption.lot_id.in_(lot_ids)))
    if move_ids:
        db.execute(sql_delete(LotConsumption).where(LotConsumption.movement_id.in_(move_ids)))
    if lot_ids:
        db.execute(sql_delete(StockLot).where(StockLot.id.in_(lot_ids)))
    if move_ids:
        db.execute(sql_delete(StockMovement).where(StockMovement.id.in_(move_ids)))


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    rows = db.execute(select(Category).order_by(Category.name)).scalars()
    return [{"id": c.id, "name": c.name, "name_id": c.name_id or c.name} for c in rows]


@router.post("/categories")
def create_category(body: CategoryIn, db: Session = Depends(get_db)):
    existing = db.execute(select(Category).where(Category.name == body.name.strip())).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Category already exists")
    cat = Category(name=body.name.strip(), name_id=(body.name_id or body.name).strip(), created_at=utcnow())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return {"id": cat.id, "name": cat.name, "name_id": cat.name_id or cat.name}


@router.get("/locations")
def list_locations(db: Session = Depends(get_db)):
    rows = db.execute(select(Location).order_by(Location.name)).scalars()
    return [{"id": c.id, "name": c.name, "name_id": c.name_id or c.name} for c in rows]


@router.post("/locations")
def create_location(body: LocationIn, db: Session = Depends(get_db)):
    existing = db.execute(select(Location).where(Location.name == body.name.strip())).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Location already exists")
    loc = Location(
        name=body.name.strip(),
        name_id=(body.name_id or body.name).strip(),
        created_at=utcnow(),
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return {"id": loc.id, "name": loc.name, "name_id": loc.name_id or loc.name}


def _named_out(row) -> dict:
    return {"id": row.id, "name": row.name, "name_id": getattr(row, "name_id", None) or row.name}


@router.patch("/categories/{category_id}")
def patch_category(category_id: int, body: CategoryIn, db: Session = Depends(get_db)):
    cat = db.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    name = body.name.strip()
    clash = db.execute(select(Category).where(Category.name == name, Category.id != category_id)).scalar_one_or_none()
    if clash:
        raise HTTPException(status_code=409, detail="Category already exists")
    cat.name = name
    cat.name_id = (body.name_id or name).strip()
    db.commit()
    db.refresh(cat)
    return _named_out(cat)


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, into_id: int | None = Query(default=None), db: Session = Depends(get_db)):
    cat = db.get(Category, category_id)
    if cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    if into_id:
        if into_id == category_id:
            raise HTTPException(status_code=400, detail="Cannot merge a category into itself")
        dest = db.get(Category, into_id)
        if dest is None:
            raise HTTPException(status_code=404, detail="Target category not found")
        db.execute(update(Item).where(Item.category_id == category_id).values(category_id=into_id))
    db.delete(cat)
    db.commit()
    return {"ok": True}


@router.patch("/locations/{location_id}")
def patch_location(location_id: int, body: LocationIn, db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found")
    name = body.name.strip()
    clash = db.execute(select(Location).where(Location.name == name, Location.id != location_id)).scalar_one_or_none()
    if clash:
        raise HTTPException(status_code=409, detail="Location already exists")
    loc.name = name
    loc.name_id = (body.name_id or name).strip()
    db.commit()
    db.refresh(loc)
    return _named_out(loc)


@router.delete("/locations/{location_id}")
def delete_location(location_id: int, into_id: int | None = Query(default=None), db: Session = Depends(get_db)):
    loc = db.get(Location, location_id)
    if loc is None:
        raise HTTPException(status_code=404, detail="Location not found")
    if into_id:
        if into_id == location_id:
            raise HTTPException(status_code=400, detail="Cannot merge a location into itself")
        dest = db.get(Location, into_id)
        if dest is None:
            raise HTTPException(status_code=404, detail="Target location not found")
        db.execute(update(Item).where(Item.location_id == location_id).values(location_id=into_id))
    db.delete(loc)
    db.commit()
    return {"ok": True}


@router.get("/items")
def list_items(
    q: str | None = None,
    category_id: int | None = None,
    location_id: int | None = None,
    low_stock: bool = False,
    include_archived: bool = False,
    db: Session = Depends(get_db),
):
    stmt = (
        select(Item)
        .options(selectinload(Item.category), selectinload(Item.location), selectinload(Item.lots))
        .order_by(Item.name)
    )
    if not include_archived:
        stmt = stmt.where(Item.archived == 0)
    if category_id:
        stmt = stmt.where(Item.category_id == category_id)
    if location_id:
        stmt = stmt.where(Item.location_id == location_id)
    items = list(db.execute(stmt).scalars())
    if q:
        needle = q.strip().lower()
        items = [i for i in items if _item_matches(i, needle)]
    if low_stock:
        items = [i for i in items if i.quantity <= i.reorder_point]
    reserved = chk.draft_reserved(db, [i.id for i in items])
    return [item_out(i, reserved.get(i.id, 0)) for i in items]


@router.post("/items")
def create_item(body: ItemIn, db: Session = Depends(get_db)):
    sku = body.sku.strip()
    if db.execute(select(Item).where(Item.sku == sku)).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="SKU already exists")
    now = utcnow()
    item = Item(
        sku=sku,
        name=body.name.strip(),
        name_id=(body.name_id or body.name).strip(),
        description=body.description or "",
        description_id=body.description_id or body.description or "",
        category_id=body.category_id,
        location_id=body.location_id,
        quantity=0,
        unit=body.unit or "ea",
        reorder_point=to_store(body.reorder_point),
        unit_cost_cents=body.unit_cost_cents,
        unit_price_cents=body.unit_price_cents,
        notes=body.notes or "",
        archived=0,
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.flush()
    if body.quantity and body.quantity > 0:
        try:
            apply_movement(
                db,
                item_id=item.id,
                kind="in",
                quantity=to_store(body.quantity),
                reason="Opening stock",
                purpose="opening",
                unit_cost_cents=body.unit_cost_cents,
            )
        except StockError as err:
            db.rollback()
            raise stock_http(err) from err
    db.commit()
    item = db.execute(
        select(Item)
        .options(selectinload(Item.category), selectinload(Item.location), selectinload(Item.lots))
        .where(Item.id == item.id)
    ).scalar_one()
    return item_out(item)


@router.get("/items/{item_id}")
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.execute(
        select(Item)
        .options(selectinload(Item.category), selectinload(Item.location), selectinload(Item.lots))
        .where(Item.id == item_id)
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    reserved = chk.draft_reserved(db, [item.id]).get(item.id, 0)
    return item_out(item, reserved)


@router.get("/items/{item_id}/sku-qr")
def item_sku_qr(item_id: int, db: Session = Depends(get_db)):
    import io

    import segno

    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    buf = io.BytesIO()
    segno.make(item.sku, error="m").save(buf, kind="svg", scale=10, border=4)
    return Response(
        content=buf.getvalue(),
        media_type="image/svg+xml",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.patch("/items/{item_id}")
def patch_item(item_id: int, body: ItemPatch, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    data = body.model_dump(exclude_unset=True)
    if "sku" in data and data["sku"]:
        clash = db.execute(
            select(Item).where(Item.sku == data["sku"].strip(), Item.id != item_id)
        ).scalar_one_or_none()
        if clash:
            raise HTTPException(status_code=409, detail="SKU already exists")
        data["sku"] = data["sku"].strip()
    if "name" in data and data["name"] is not None:
        data["name"] = data["name"].strip()
    if "unit" in data and data["unit"] is not None:
        data["unit"] = (data["unit"] or "").strip() or "ea"
    if "reorder_point" in data and data["reorder_point"] is not None:
        data["reorder_point"] = to_store(data["reorder_point"])
    for key, value in data.items():
        setattr(item, key, value)
    item.updated_at = utcnow()
    db.commit()
    item = db.execute(
        select(Item)
        .options(selectinload(Item.category), selectinload(Item.location), selectinload(Item.lots))
        .where(Item.id == item_id)
    ).scalar_one()
    return item_out(item)


def _archive_item_row(item: Item) -> None:
    item.archived = 1
    item.updated_at = utcnow()


@router.post("/items/{item_id}/archive")
def archive_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    _archive_item_row(item)
    db.commit()
    return {"ok": True, "archived": True, "deleted": False}


@router.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    if _item_in_use(db, item_id):
        _archive_item_row(item)
        db.commit()
        return {"ok": True, "archived": True, "deleted": False}
    _purge_item_stock(db, item_id)
    db.delete(item)
    db.commit()
    return {"ok": True, "deleted": True, "archived": False}


@router.post("/items/{item_id}/movements")
def item_movement(item_id: int, body: MovementIn, db: Session = Depends(get_db)):
    if body.kind == "out":
        reason = body.reason.strip() or "Shrinkage"
        purpose = body.purpose.strip() or "damage"
    elif body.kind == "in":
        reason = body.reason.strip() or "Receive"
        purpose = body.purpose.strip() or "receive"
    else:
        reason = body.reason.strip()
        purpose = body.purpose.strip() or "adjust"
    try:
        chk.begin_immediate(db)
        qty = to_store(body.quantity)
        item = db.get(Item, item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        if body.kind == "out":
            chk.require_sellable(db, item, qty)
        elif body.kind == "adjust":
            reserved = chk.draft_reserved(db, [item.id]).get(item.id, 0)
            if qty < reserved:
                chk.require_sellable(db, item, item.quantity - qty)
        mov = apply_movement(
            db,
            item_id=item_id,
            kind=body.kind,
            quantity=qty,
            reason=reason,
            purpose=purpose,
            unit_cost_cents=body.unit_cost_cents,
        )
        db.commit()
        db.refresh(mov)
        return movement_out(mov)
    except HTTPException:
        db.rollback()
        raise
    except StockError as err:
        db.rollback()
        raise stock_http(err) from err
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.get("/items/{item_id}/movements")
def item_movements(item_id: int, db: Session = Depends(get_db)):
    if db.get(Item, item_id) is None:
        raise HTTPException(status_code=404, detail="Item not found")
    rows = db.execute(
        select(StockMovement)
        .options(selectinload(StockMovement.item))
        .where(StockMovement.item_id == item_id)
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(100)
    ).scalars()
    return [movement_out(m) for m in rows]


@router.get("/movements")
def all_movements(limit: int = Query(default=30, le=200), db: Session = Depends(get_db)):
    rows = db.execute(
        select(StockMovement)
        .options(selectinload(StockMovement.item))
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(limit)
    ).scalars()
    return [movement_out(m) for m in rows]


@router.get("/items/{item_id}/lots")
def item_lots(item_id: int, db: Session = Depends(get_db)):
    if db.get(Item, item_id) is None:
        raise HTTPException(status_code=404, detail="Item not found")
    lots = db.execute(
        select(StockLot).where(StockLot.item_id == item_id).order_by(StockLot.received_at.asc(), StockLot.id.asc())
    ).scalars()
    return [
        {
            "id": lot.id,
            "received_at": lot.received_at,
            "unit_cost_cents": lot.unit_cost_cents,
            "qty_original": from_store(lot.qty_original),
            "qty_remaining": from_store(lot.qty_remaining),
            "source": lot.source,
            "restock_id": lot.restock_id,
        }
        for lot in lots
    ]
