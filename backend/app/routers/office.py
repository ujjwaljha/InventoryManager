from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_db, raise_checkout
from app.models import DamageNote, Restock, RestockLine, Supplier, SupplierReturn, SupplierReturnLine
from app.schemas import DamageIn, RestockCreateIn, RestockLineIn, SupplierIn, SupplierReturnIn, TillSaleIn
from app.serialize import damage_out, invoice_out, restock_out, supplier_return_out
from app.services import office as off
from app.services.stock import StockError, stock_http

router = APIRouter(prefix="/api", tags=["office"])


def _merge_lines(lines) -> list[tuple[int, int]]:
    merged: dict[int, int] = {}
    for line in lines:
        merged[line.item_id] = merged.get(line.item_id, 0) + line.quantity
    return list(merged.items())


@router.get("/suppliers")
def list_suppliers(db: Session = Depends(get_db)):
    rows = db.execute(select(Supplier).order_by(Supplier.name)).scalars()
    return [{"id": s.id, "name": s.name, "phone": s.phone, "notes": s.notes} for s in rows]


@router.post("/suppliers")
def create_supplier(body: SupplierIn, db: Session = Depends(get_db)):
    try:
        row = off.upsert_supplier(db, body.name, body.phone, body.notes)
        db.commit()
        db.refresh(row)
        return {"id": row.id, "name": row.name, "phone": row.phone, "notes": row.notes}
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.get("/restocks")
def list_restocks(status: str | None = Query(default=None), db: Session = Depends(get_db)):
    stmt = (
        select(Restock)
        .options(selectinload(Restock.lines), selectinload(Restock.supplier))
        .order_by(Restock.created_at.desc())
    )
    if status:
        stmt = stmt.where(Restock.status == status)
    return [restock_out(row) for row in db.execute(stmt).scalars()]


@router.post("/restocks")
def create_restock(body: RestockCreateIn, db: Session = Depends(get_db)):
    try:
        supplier = None
        if body.supplier_id:
            supplier = db.get(Supplier, body.supplier_id)
            if supplier is None:
                raise HTTPException(status_code=404, detail="Supplier not found")
        elif body.supplier_name:
            supplier = off.upsert_supplier(db, body.supplier_name, body.supplier_phone)
        row = off.create_restock(db, supplier, body.note)
        db.commit()
        return restock_out(off.load_restock(db, row.id) or row)
    except HTTPException:
        db.rollback()
        raise
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.get("/restocks/{restock_id}")
def get_restock(restock_id: int, db: Session = Depends(get_db)):
    row = off.load_restock(db, restock_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Restock not found")
    return restock_out(row)


@router.post("/restocks/{restock_id}/lines")
def restock_add_line(restock_id: int, body: RestockLineIn, db: Session = Depends(get_db)):
    row = off.load_restock(db, restock_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Restock not found")
    try:
        row = off.upsert_restock_line(db, row, body.item_id, body.quantity, body.unit_cost_cents)
        db.commit()
        return restock_out(off.load_restock(db, restock_id) or row)
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.delete("/restocks/{restock_id}/lines/{item_id}")
def restock_remove_line(restock_id: int, item_id: int, db: Session = Depends(get_db)):
    row = off.load_restock(db, restock_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Restock not found")
    try:
        row = off.remove_restock_line(db, row, item_id)
        db.commit()
        return restock_out(off.load_restock(db, restock_id) or row)
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.post("/restocks/{restock_id}/receive")
def restock_receive(restock_id: int, db: Session = Depends(get_db)):
    row = off.load_restock(db, restock_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Restock not found")
    try:
        row = off.receive_restock(db, row)
        db.commit()
        return restock_out(off.load_restock(db, restock_id) or row)
    except StockError as err:
        db.rollback()
        raise stock_http(err) from err
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.get("/damage")
def list_damage(db: Session = Depends(get_db)):
    rows = db.execute(
        select(DamageNote).options(selectinload(DamageNote.lines)).order_by(DamageNote.created_at.desc())
    ).scalars()
    return [damage_out(row) for row in rows]


@router.post("/damage")
def create_damage(body: DamageIn, db: Session = Depends(get_db)):
    try:
        row = off.record_damage(db, body.reason, _merge_lines(body.lines))
        db.commit()
        loaded = db.execute(
            select(DamageNote).options(selectinload(DamageNote.lines)).where(DamageNote.id == row.id)
        ).scalar_one()
        return damage_out(loaded)
    except StockError as err:
        db.rollback()
        raise stock_http(err) from err
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.get("/supplier-returns")
def list_returns(db: Session = Depends(get_db)):
    rows = db.execute(
        select(SupplierReturn)
        .options(selectinload(SupplierReturn.lines), selectinload(SupplierReturn.supplier))
        .order_by(SupplierReturn.created_at.desc())
    ).scalars()
    return [supplier_return_out(row) for row in rows]


@router.post("/supplier-returns")
def create_return(body: SupplierReturnIn, db: Session = Depends(get_db)):
    try:
        supplier = None
        if body.supplier_id:
            supplier = db.get(Supplier, body.supplier_id)
            if supplier is None:
                raise HTTPException(status_code=404, detail="Supplier not found")
        elif body.supplier_name:
            supplier = off.upsert_supplier(db, body.supplier_name, body.supplier_phone)
        row = off.record_supplier_return(db, body.reason, _merge_lines(body.lines), supplier)
        db.commit()
        loaded = db.execute(
            select(SupplierReturn)
            .options(selectinload(SupplierReturn.lines), selectinload(SupplierReturn.supplier))
            .where(SupplierReturn.id == row.id)
        ).scalar_one()
        return supplier_return_out(loaded)
    except HTTPException:
        db.rollback()
        raise
    except StockError as err:
        db.rollback()
        raise stock_http(err) from err
    except Exception as err:
        db.rollback()
        raise_checkout(err)


@router.post("/sales")
def till_sale(body: TillSaleIn, db: Session = Depends(get_db)):
    try:
        _po, invoice = off.till_sale(
            db,
            customer_name=body.customer_name,
            customer_phone=body.customer_phone,
            salesperson_name=body.salesperson_name,
            lines=_merge_lines(body.lines),
            note=body.note,
        )
        db.commit()
        return invoice_out(invoice)
    except StockError as err:
        db.rollback()
        raise stock_http(err) from err
    except Exception as err:
        db.rollback()
        raise_checkout(err)
