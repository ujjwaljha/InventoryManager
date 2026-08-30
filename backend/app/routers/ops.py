import csv
import io
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from app.db import make_session_factory, replace_sqlite_file
from app.deps import get_db
from app.models import Item
from app.netutil import lan_ip, shop_url
from app.schemas import SettingsIn
from app.serialize import settings_out
from app.services.checkout import get_settings

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
        if isinstance(value, str):
            value = value.strip()
        setattr(s, key, value)
    s.currency_symbol = "Rp"
    s.currency_code = "IDR"
    db.commit()
    db.refresh(s)
    return settings_out(s)


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
                item.quantity,
                item.unit,
                item.reorder_point,
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
