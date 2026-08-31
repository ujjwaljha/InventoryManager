from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_db
from app.models import Invoice, Item, StockMovement
from app.serialize import invoice_out, item_out, movement_out
from app.services.checkout import get_settings
from app.services.stock import lot_stats
from app.timeutil import range_bounds, shop_day_bounds, today_shop

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _margin_bps(profit: int, revenue: int) -> int:
    if revenue <= 0:
        return 0
    return int(round(profit * 10000 / revenue))


def _active_invoices(db: Session, start: str, end: str) -> list[Invoice]:
    return list(
        db.execute(
            select(Invoice)
            .options(
                selectinload(Invoice.lines),
                selectinload(Invoice.shopper),
                selectinload(Invoice.purchase_order),
            )
            .where(
                Invoice.status.in_(("issued", "paid")),
                Invoice.issued_at >= start,
                Invoice.issued_at < end,
            )
            .order_by(Invoice.issued_at.asc())
        ).scalars()
    )


def _sku_meta(db: Session, skus: set[str]) -> dict[str, Item]:
    if not skus:
        return {}
    rows = db.execute(
        select(Item).options(selectinload(Item.category)).where(Item.sku.in_(skus))
    ).scalars()
    return {item.sku: item for item in rows}


@router.get("/stock")
def stock_report(db: Session = Depends(get_db)):
    settings = get_settings(db)
    items = list(
        db.execute(
            select(Item)
            .options(selectinload(Item.category), selectinload(Item.location), selectinload(Item.lots))
            .where(Item.archived == 0)
            .order_by(Item.name)
        ).scalars()
    )
    rows = []
    total_value = 0
    for item in items:
        fifo, value = lot_stats(item)
        total_value += value
        sell = item.unit_price_cents
        potential = (sell - fifo) * item.quantity
        rows.append(
            {
                **item_out(item).model_dump(),
                "potential_profit_cents": potential,
                "potential_margin_bps": _margin_bps(sell - fifo, sell) if sell else 0,
            }
        )
    return {
        "currency_symbol": settings.currency_symbol or "Rp",
        "currency_code": "IDR",
        "sku_count": len(rows),
        "units_on_hand": sum(i.quantity for i in items),
        "inventory_value_cents": total_value,
        "items": rows,
    }


@router.get("/daily")
def daily_sales(date: str | None = Query(default=None), db: Session = Depends(get_db)):
    settings = get_settings(db)
    day = date or today_shop()
    start, end = shop_day_bounds(day)
    invoices = _active_invoices(db, start, end)
    return _sales_bundle(db, settings, invoices, date_from=day, date_to=day)


@router.get("/pnl")
def item_pnl(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    settings = get_settings(db)
    start, end = range_bounds(date_from, date_to)
    invoices = _active_invoices(db, start, end)
    return _sales_bundle(db, settings, invoices, date_from=date_from or today_shop(), date_to=date_to or today_shop())


@router.get("/categories")
def category_report(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    bundle = item_pnl(date_from, date_to, db)
    return {
        "date_from": bundle["date_from"],
        "date_to": bundle["date_to"],
        "currency_symbol": bundle["currency_symbol"],
        "currency_code": "IDR",
        "revenue_cents": bundle["revenue_cents"],
        "cogs_cents": bundle["cogs_cents"],
        "profit_cents": bundle["profit_cents"],
        "margin_bps": bundle["margin_bps"],
        "categories": bundle["categories"],
    }


@router.get("/ledger")
def ledger(
    item_id: int | None = None,
    purpose: str | None = None,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
):
    stmt = (
        select(StockMovement)
        .options(selectinload(StockMovement.item))
        .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
        .limit(limit)
    )
    if item_id:
        stmt = stmt.where(StockMovement.item_id == item_id)
    if purpose:
        stmt = stmt.where(StockMovement.purpose == purpose)
    rows = db.execute(stmt).scalars()
    return [movement_out(m) for m in rows]


def _sales_bundle(db: Session, settings, invoices: list[Invoice], date_from: str, date_to: str) -> dict:
    item_acc: dict[str, dict] = defaultdict(
        lambda: {
            "sku": "",
            "name": "",
            "name_id": "",
            "category_id": None,
            "category_name": "",
            "category_name_id": "",
            "quantity": 0,
            "revenue_cents": 0,
            "cogs_cents": 0,
        }
    )
    revenue = 0
    cogs = 0
    for inv in invoices:
        revenue += inv.total_cents
        cogs += inv.cogs_cents or 0
        for ln in inv.lines:
            row = item_acc[ln.sku]
            row["sku"] = ln.sku
            row["name"] = ln.name
            row["name_id"] = ln.name_id or ln.name
            row["quantity"] += ln.quantity
            row["revenue_cents"] += ln.line_total_cents
            row["cogs_cents"] += ln.cogs_cents or 0

    meta = _sku_meta(db, set(item_acc))
    items = []
    cat_acc: dict[str, dict] = defaultdict(
        lambda: {
            "category_id": None,
            "name": "Uncategorized",
            "name_id": "Tanpa kategori",
            "quantity": 0,
            "revenue_cents": 0,
            "cogs_cents": 0,
        }
    )
    for sku, row in item_acc.items():
        item = meta.get(sku)
        if item and item.category:
            row["category_id"] = item.category_id
            row["category_name"] = item.category.name
            row["category_name_id"] = item.category.name_id or item.category.name
        else:
            row["category_name"] = row["category_name"] or "Uncategorized"
            row["category_name_id"] = row["category_name_id"] or "Tanpa kategori"
        profit = row["revenue_cents"] - row["cogs_cents"]
        row["profit_cents"] = profit
        row["margin_bps"] = _margin_bps(profit, row["revenue_cents"])
        items.append(row)
        key = str(row["category_id"] or "none")
        cat = cat_acc[key]
        cat["category_id"] = row["category_id"]
        cat["name"] = row["category_name"] or "Uncategorized"
        cat["name_id"] = row["category_name_id"] or "Tanpa kategori"
        cat["quantity"] += row["quantity"]
        cat["revenue_cents"] += row["revenue_cents"]
        cat["cogs_cents"] += row["cogs_cents"]

    categories = []
    for cat in cat_acc.values():
        profit = cat["revenue_cents"] - cat["cogs_cents"]
        cat["profit_cents"] = profit
        cat["margin_bps"] = _margin_bps(profit, cat["revenue_cents"])
        categories.append(cat)

    items.sort(key=lambda r: r["revenue_cents"], reverse=True)
    categories.sort(key=lambda r: r["revenue_cents"], reverse=True)
    profit = revenue - cogs
    return {
        "date_from": date_from,
        "date_to": date_to,
        "currency_symbol": settings.currency_symbol or "Rp",
        "currency_code": "IDR",
        "receipt_count": len(invoices),
        "revenue_cents": revenue,
        "cogs_cents": cogs,
        "profit_cents": profit,
        "margin_bps": _margin_bps(profit, revenue),
        "receipts": [invoice_out(inv) for inv in invoices],
        "items": items,
        "categories": categories,
    }
