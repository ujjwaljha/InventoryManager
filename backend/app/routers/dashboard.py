from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_db
from app.models import CreditNote, Invoice, InvoicePayment, Item, PurchaseOrder, StockMovement
from app.schemas import DashboardOut
from app.qty import from_store
from app.serialize import item_out, movement_out
from app.services import checkout as chk
from app.services.checkout import get_settings
from app.timeutil import shop_day_bounds, today_shop

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db)):
    settings = get_settings(db)
    sku_count = db.scalar(select(func.count()).select_from(Item).where(Item.archived == 0)) or 0
    units = db.scalar(select(func.coalesce(func.sum(Item.quantity), 0)).where(Item.archived == 0)) or 0
    items = list(
        db.execute(
            select(Item)
            .options(selectinload(Item.category), selectinload(Item.location), selectinload(Item.lots))
            .where(Item.archived == 0)
        ).scalars()
    )
    reserved_map = chk.draft_reserved(db)
    reserved_units = sum(reserved_map.values())
    low = [i for i in items if i.quantity <= i.reorder_point]
    draft_count = (
        db.scalar(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.status == "draft")) or 0
    )
    start, end = shop_day_bounds()
    today_orders = (
        db.scalar(
            select(func.count())
            .select_from(PurchaseOrder)
            .where(
                PurchaseOrder.status == "placed",
                PurchaseOrder.placed_at.is_not(None),
                PurchaseOrder.placed_at >= start,
                PurchaseOrder.placed_at < end,
            )
        )
        or 0
    )
    today_sales = (
        db.scalar(
            select(func.coalesce(func.sum(Invoice.total_cents), 0)).where(
                Invoice.status.in_(("issued", "paid")),
                Invoice.issued_at >= start,
                Invoice.issued_at < end,
            )
        )
        or 0
    )
    unpaid_count = (
        db.scalar(select(func.count()).select_from(Invoice).where(Invoice.status == "issued")) or 0
    )
    paid_sub = (
        select(func.coalesce(func.sum(InvoicePayment.amount_cents), 0))
        .where(InvoicePayment.invoice_id == Invoice.id)
        .scalar_subquery()
    )
    unpaid_cents = (
        db.scalar(
            select(func.coalesce(func.sum(Invoice.total_cents - paid_sub), 0)).where(Invoice.status == "issued")
        )
        or 0
    )
    issued_shoppers = select(Invoice.shopper_id).where(Invoice.status == "issued").distinct()
    promises_due_count = (
        db.scalar(
            select(func.count(func.distinct(CreditNote.shopper_id))).where(
                CreditNote.shopper_id.in_(issued_shoppers),
                CreditNote.promised_date.is_not(None),
                CreditNote.promised_date != "",
                CreditNote.promised_date <= today_shop(),
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
        units_on_hand=from_store(int(units)),
        units_reserved=from_store(int(reserved_units)),
        low_stock_count=len(low),
        draft_po_count=int(draft_count),
        today_order_count=int(today_orders),
        today_sales_cents=int(today_sales),
        unpaid_count=int(unpaid_count),
        unpaid_cents=int(unpaid_cents),
        promises_due_count=int(promises_due_count),
        currency_symbol=settings.currency_symbol or "Rp",
        currency_code=getattr(settings, "currency_code", None) or "IDR",
        shop_name=settings.name,
        low_stock_items=[item_out(i, reserved_map.get(i.id, 0)) for i in sorted(low, key=lambda x: x.quantity)[:8]],
        recent_movements=[movement_out(m) for m in recent],
    )
