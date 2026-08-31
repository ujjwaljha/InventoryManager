import csv
import io
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from app.db import make_session_factory, replace_sqlite_file
from app.deps import get_db, raise_checkout
from app.models import Category, Item, Location
from app.netutil import lan_ip, shop_url
from app.operator import SESSION_KEY, clear_pin, pin_is_set, set_pin, verify_pin
from app.schemas import PinIn, SettingsIn, UnlockIn
from app.serialize import settings_out
from app.qty import from_store, to_store
from app.services.checkout import get_settings
from app.services.stock import StockError, apply_movement
from app.timeutil import utcnow

router = APIRouter(prefix="/api", tags=["ops"])


@router.get("/settings")
def read_settings(db: Session = Depends(get_db)):
    return settings_out(get_settings(db))


@router.patch("/settings")
def update_settings(body: SettingsIn, db: Session = Depends(get_db)):
    s = get_settings(db)
    data = body.model_dump(exclude_unset=True)
    data.pop("currency_symbol", None)
    data.pop("currency_code", None)
    for key, value in data.items():
        if value is None:
            continue
        if key == "allow_lan":
            setattr(s, key, 1 if value else 0)
            continue
        if isinstance(value, str):
            value = value.strip()
        setattr(s, key, value)
    s.currency_symbol = "Rp"
    s.currency_code = "IDR"
    db.commit()
    db.refresh(s)
    return settings_out(s)


@router.get("/operator/status")
def operator_status(request: Request, db: Session = Depends(get_db)):
    needed = pin_is_set(get_settings(db))
    return {"required": needed, "unlocked": bool(request.session.get(SESSION_KEY)) if needed else True}


@router.post("/operator/unlock")
def operator_unlock(body: UnlockIn, request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    if not pin_is_set(settings):
        request.session[SESSION_KEY] = True
        return {"ok": True, "required": False, "unlocked": True}
    if not verify_pin(settings, body.pin):
        raise HTTPException(status_code=401, detail="Wrong PIN")
    request.session[SESSION_KEY] = True
    return {"ok": True, "required": True, "unlocked": True}


@router.post("/operator/lock")
def operator_lock(request: Request):
    request.session.pop(SESSION_KEY, None)
    return {"ok": True, "unlocked": False}


@router.post("/operator/pin")
def operator_set_pin(body: PinIn, request: Request, db: Session = Depends(get_db)):
    try:
        settings = set_pin(db, body.pin, body.current_pin)
        db.commit()
    except Exception as err:
        db.rollback()
        raise_checkout(err)
    request.session[SESSION_KEY] = True
    return {"ok": True, "pin_set": pin_is_set(settings)}


@router.post("/operator/pin/clear")
def operator_clear_pin(body: UnlockIn, request: Request, db: Session = Depends(get_db)):
    try:
        settings = clear_pin(db, body.pin)
        db.commit()
    except Exception as err:
        db.rollback()
        raise_checkout(err)
    request.session.pop(SESSION_KEY, None)
    return {"ok": True, "pin_set": pin_is_set(settings)}


@router.get("/health")
def health(db: Session = Depends(get_db)):
    s = get_settings(db)
    return {
        "ok": True,
        "shop": s.name,
        "currency": s.currency_symbol or "Rp",
        "currency_code": getattr(s, "currency_code", None) or "IDR",
        "db": str(Path(db.get_bind().url.database or "")),
    }


@router.get("/backup")
def backup(db: Session = Depends(get_db)):
    engine = db.get_bind()
    database = engine.url.database
    if not database or database == ":memory:":
        raise HTTPException(status_code=400, detail="Backup is only available for a file database")
    with engine.connect() as conn:
        conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
        conn.commit()
    path = Path(database)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Database file not found")
    return FileResponse(path, filename="inventory.db", media_type="application/octet-stream")


@router.post("/backup/restore")
async def restore_backup(request: Request, file: UploadFile = File(...)):
    payload = await file.read()
    if not payload or not payload.startswith(b"SQLite format 3"):
        raise HTTPException(status_code=400, detail="This is not a shop backup file")
    engine = request.app.state.engine
    try:
        new_engine = replace_sqlite_file(engine, payload)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    request.app.state.engine = new_engine
    request.app.state.SessionLocal = make_session_factory(new_engine)
    return {"ok": True}


@router.get("/export/items.csv")
def export_items(db: Session = Depends(get_db)):
    items = db.execute(
        select(Item).options(selectinload(Item.category), selectinload(Item.location)).order_by(Item.sku)
    ).scalars()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "sku",
            "name",
            "name_id",
            "description",
            "description_id",
            "category",
            "location",
            "quantity",
            "unit",
            "reorder_point",
            "unit_cost_cents",
            "unit_price_cents",
            "archived",
        ]
    )
    for item in items:
        writer.writerow(
            [
                item.sku,
                item.name,
                item.name_id or "",
                item.description,
                item.description_id or "",
                item.category.name if item.category else "",
                item.location.name if item.location else "",
                from_store(item.quantity),
                item.unit,
                from_store(item.reorder_point),
                item.unit_cost_cents,
                item.unit_price_cents,
                item.archived,
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=items.csv"},
    )


def _cell(row: dict, *keys: str) -> str:
    for key in keys:
        if key in row and row[key] is not None:
            return str(row[key]).strip()
    return ""


def _int_cell(row: dict, *keys: str, default: int = 0) -> int:
    raw = _cell(row, *keys)
    if not raw:
        return default
    return int(round(float(raw)))


def _qty_cell(row: dict, *keys: str) -> float:
    raw = _cell(row, *keys)
    if not raw:
        return 0.0
    return float(raw)


def _named(db: Session, model, name: str):
    name = name.strip()
    if not name:
        return None
    row = db.execute(select(model).where(model.name == name)).scalar_one_or_none()
    if row:
        return row
    row = model(name=name, name_id=name, created_at=utcnow())
    db.add(row)
    db.flush()
    return row


@router.post("/import/items.csv")
async def import_items(file: UploadFile = File(...), db: Session = Depends(get_db)):
    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV has no header row")
    created = 0
    updated = 0
    errors: list[dict] = []
    now = utcnow()
    for index, row in enumerate(reader, start=2):
        sku = _cell(row, "sku")
        if not sku:
            continue
        try:
            with db.begin_nested():
                name = _cell(row, "name") or sku
                item = db.execute(select(Item).where(Item.sku == sku)).scalar_one_or_none()
                cat = _named(db, Category, _cell(row, "category"))
                loc = _named(db, Location, _cell(row, "location"))
                archived = 1 if _cell(row, "archived").lower() in {"1", "true", "yes", "y"} else 0
                if item is None:
                    item = Item(
                        sku=sku,
                        name=name,
                        name_id=_cell(row, "name_id") or name,
                        description=_cell(row, "description"),
                        description_id=_cell(row, "description_id") or _cell(row, "description"),
                        category_id=cat.id if cat else None,
                        location_id=loc.id if loc else None,
                        quantity=0,
                        unit=_cell(row, "unit") or "ea",
                        reorder_point=to_store(_qty_cell(row, "reorder_point")),
                        unit_cost_cents=max(0, _int_cell(row, "unit_cost_cents")),
                        unit_price_cents=max(0, _int_cell(row, "unit_price_cents")),
                        notes="",
                        archived=archived,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(item)
                    db.flush()
                    qty = _qty_cell(row, "quantity")
                    if qty > 0:
                        apply_movement(
                            db,
                            item_id=item.id,
                            kind="in",
                            quantity=to_store(qty),
                            reason="CSV import opening",
                            purpose="opening",
                            unit_cost_cents=item.unit_cost_cents,
                        )
                    created += 1
                else:
                    item.name = name
                    item.name_id = _cell(row, "name_id") or item.name_id or name
                    if _cell(row, "description") or "description" in row:
                        item.description = _cell(row, "description")
                    if _cell(row, "description_id") or "description_id" in row:
                        item.description_id = _cell(row, "description_id") or item.description
                    item.category_id = cat.id if cat else item.category_id
                    item.location_id = loc.id if loc else item.location_id
                    if _cell(row, "unit"):
                        item.unit = _cell(row, "unit")
                    if _cell(row, "reorder_point"):
                        item.reorder_point = to_store(_qty_cell(row, "reorder_point"))
                    if _cell(row, "unit_cost_cents"):
                        item.unit_cost_cents = max(0, _int_cell(row, "unit_cost_cents"))
                    if _cell(row, "unit_price_cents"):
                        item.unit_price_cents = max(0, _int_cell(row, "unit_price_cents"))
                    item.archived = archived
                    item.updated_at = now
                    updated += 1
        except (StockError, ValueError) as err:
            errors.append({"line": index, "sku": sku, "error": str(err)})
    db.commit()
    return {"created": created, "updated": updated, "errors": errors, "error_count": len(errors)}


@router.get("/lan")
def lan_hint():
    host = lan_ip()
    return {
        "lan_host": host,
        "shop_path": "/shop",
        "operator_path": "/",
        "shop_url": shop_url(8000),
        "till_url": f"http://{host}:8000/",
    }


@router.get("/lan/qr")
def lan_qr():
    import segno

    url = shop_url(8000)
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="svg", scale=5, border=2)
    return Response(content=buf.getvalue(), media_type="image/svg+xml")
