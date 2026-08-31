from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_db
from app.models import Category, Item, Location, StockLot, StockMovement
from app.schemas import CategoryIn, ItemIn, ItemPatch, LocationIn, MovementIn
from app.serialize import item_out, movement_out
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
    loc = Location(name=body.name.strip(), created_at=utcnow())
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return {"id": loc.id, "name": loc.name}


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
    return [item_out(i) for i in items]


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
        reorder_point=body.reorder_point,
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
                quantity=body.quantity,
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
    return item_out(item)


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


@router.post("/items/{item_id}/archive")
def archive_item(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    item.archived = 1
    item.updated_at = utcnow()
    db.commit()
    return {"ok": True}


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
        mov = apply_movement(
            db,
            item_id=item_id,
            kind=body.kind,
            quantity=body.quantity,
            reason=reason,
            purpose=purpose,
            unit_cost_cents=body.unit_cost_cents,
        )
        db.commit()
        db.refresh(mov)
        return movement_out(mov)
    except StockError as err:
        db.rollback()
        raise stock_http(err) from err


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
            "qty_original": lot.qty_original,
            "qty_remaining": lot.qty_remaining,
            "source": lot.source,
            "restock_id": lot.restock_id,
        }
        for lot in lots
    ]
