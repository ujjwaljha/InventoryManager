from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_db
from app.models import Invoice, Item, PurchaseOrder, StockMovement
from app.schemas import DashboardOut
from app.serialize import item_out, movement_out
from app.services.checkout import get_settings
from app.timeutil import today_utc

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db)):
    settings = get_settings(db)
    sku_count = db.scalar(select(func.count()).select_from(Item).where(Item.archived == 0)) or 0
    units = db.scalar(select(func.coalesce(func.sum(Item.quantity), 0)).where(Item.archived == 0)) or 0
    items = list(
        db.execute(
            select(Item).options(selectinload(Item.category), selectinload(Item.location)).where(Item.archived == 0)
        ).scalars()
    )
    low = [i for i in items if i.quantity <= i.reorder_point]
    draft_count = (
        db.scalar(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.status == "draft")) or 0
    )
    today = today_utc()
    today_orders = (
        db.scalar(
            select(func.count())
            .select_from(PurchaseOrder)
            .where(PurchaseOrder.status == "placed", PurchaseOrder.placed_at.is_not(None), PurchaseOrder.placed_at.startswith(today))
        )
        or 0
    )
    today_sales = (
        db.scalar(
            select(func.coalesce(func.sum(Invoice.total_cents), 0)).where(
                Invoice.status.in_(("issued", "paid")),
                Invoice.issued_at.startswith(today),
            )
        )
        or 0
    )
    recent = db.execute(
        select(StockMovement)
        .options(selectinload(StockMovement.item))
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(10)
    ).scalars()
    return DashboardOut(
        sku_count=int(sku_count),
        units_on_hand=int(units),
        low_stock_count=len(low),
        draft_po_count=int(draft_count),
        today_order_count=int(today_orders),
        today_sales_cents=int(today_sales),
        currency_symbol=settings.currency_symbol or "Rp",
        currency_code=getattr(settings, "currency_code", None) or "IDR",
        shop_name=settings.name,
        low_stock_items=[item_out(i) for i in sorted(low, key=lambda x: x.quantity)[:8]],
        recent_movements=[movement_out(m) for m in recent],
    )
