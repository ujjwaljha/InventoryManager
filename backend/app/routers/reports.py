from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_db
from app.models import Invoice, InvoicePayment, Item, Shopper, StockMovement
from app.qty import from_store, money_qty
from app.serialize import invoice_out, item_out, movement_out
from app.services import checkout as chk
from app.services.checkout import get_settings
from app.services.stock import lot_stats
from app.timeutil import range_bounds, shop_day_bounds, today_shop

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _margin_bps(profit: int, revenue: int) -> int:
    if revenue <= 0:
        return 0
    return int(round(profit * 10000 / revenue))


def _active_invoices(db: Session, start: str, end: str, shopper_id: int | None = None) -> list[Invoice]:
    stmt = (
        select(Invoice)
        .options(
            selectinload(Invoice.lines),
            selectinload(Invoice.shopper),
            selectinload(Invoice.purchase_order),
            selectinload(Invoice.payments),
        )
        .where(
            Invoice.status.in_(("issued", "paid")),
            Invoice.issued_at >= start,
            Invoice.issued_at < end,
        )
        .order_by(Invoice.issued_at.asc())
    )
    if shopper_id is not None:
        stmt = stmt.where(Invoice.shopper_id == shopper_id)
    return list(db.execute(stmt).scalars())


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
    reserved_map = chk.draft_reserved(db, [i.id for i in items])
    rows = []
    total_value = 0
    for item in items:
        fifo, value = lot_stats(item)
        total_value += value
        sell = item.unit_price_cents
        potential = money_qty(item.quantity, sell - fifo)
        rows.append(
            {
                **item_out(item, reserved_map.get(item.id, 0)).model_dump(),
                "potential_profit_cents": potential,
                "potential_margin_bps": _margin_bps(sell - fifo, sell) if sell else 0,
            }
        )
    return {
        "currency_symbol": settings.currency_symbol or "Rp",
        "currency_code": "IDR",
        "sku_count": len(rows),
        "units_on_hand": from_store(sum(i.quantity for i in items)),
        "inventory_value_cents": total_value,
        "items": rows,
    }


def _pnl_for_range(
    db: Session,
    date_from: str | None,
    date_to: str | None,
    shopper_id: int | None = None,
) -> dict:
    settings = get_settings(db)
    start, end = range_bounds(date_from, date_to)
    invoices = _active_invoices(db, start, end, shopper_id)
    return _sales_bundle(
        db,
        settings,
        invoices,
        date_from=date_from or today_shop(),
        date_to=date_to or today_shop(),
        start=start,
        end=end,
        shopper_id=shopper_id,
    )


@router.get("/daily")
def daily_sales(
    date: str | None = Query(default=None),
    shopper_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    settings = get_settings(db)
    day = date or today_shop()
    start, end = shop_day_bounds(day)
    invoices = _active_invoices(db, start, end, shopper_id)
    return _sales_bundle(
        db,
        settings,
        invoices,
        date_from=day,
        date_to=day,
        start=start,
        end=end,
        shopper_id=shopper_id,
    )


@router.get("/pnl")
def item_pnl(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    shopper_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return _pnl_for_range(db, date_from, date_to, shopper_id)


@router.get("/categories")
def category_report(
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    shopper_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    bundle = _pnl_for_range(db, date_from, date_to, shopper_id)
    return {
        "date_from": bundle["date_from"],
        "date_to": bundle["date_to"],
        "currency_symbol": bundle["currency_symbol"],
        "currency_code": "IDR",
        "shopper_id": bundle.get("shopper_id"),
        "shopper": bundle.get("shopper"),
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
    date_from: str | None = None,
    date_to: str | None = None,
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
    if date_from or date_to:
        start, end = range_bounds(date_from, date_to)
        stmt = stmt.where(StockMovement.created_at >= start, StockMovement.created_at < end)
    rows = db.execute(stmt).scalars()
    return [movement_out(m) for m in rows]


def _writeoffs_by_sku(db: Session, start: str, end: str) -> list[tuple[str, int, str, str]]:
    rows = db.execute(
        select(
            Item.sku,
            func.coalesce(func.sum(StockMovement.cogs_cents), 0),
            Item.name,
            Item.name_id,
        )
        .join(Item, Item.id == StockMovement.item_id)
        .where(
            StockMovement.purpose.in_(("damage", "supplier_return")),
            StockMovement.created_at >= start,
            StockMovement.created_at < end,
        )
        .group_by(Item.sku, Item.name, Item.name_id)
    )
    return [(str(sku), int(cents or 0), name or sku, name_id or name or sku) for sku, cents, name, name_id in rows]


def _purpose_cogs(db: Session, start: str, end: str, purpose: str) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(StockMovement.cogs_cents), 0)).where(
                StockMovement.purpose == purpose,
                StockMovement.created_at >= start,
                StockMovement.created_at < end,
            )
        )
        or 0
    )


def _collected_payments(
    db: Session, start: str, end: str, shopper_id: int | None = None
) -> tuple[int, int]:
    filters = [
        InvoicePayment.created_at >= start,
        InvoicePayment.created_at < end,
    ]
    sum_stmt = select(func.coalesce(func.sum(InvoicePayment.amount_cents), 0))
    count_stmt = select(func.count()).select_from(InvoicePayment)
    if shopper_id is not None:
        join_on = Invoice.id == InvoicePayment.invoice_id
        shopper_filters = [*filters, Invoice.shopper_id == shopper_id, Invoice.status != "void"]
        sum_stmt = sum_stmt.join(Invoice, join_on).where(*shopper_filters)
        count_stmt = count_stmt.join(Invoice, join_on).where(*shopper_filters)
    else:
        sum_stmt = sum_stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)
    return int(db.scalar(sum_stmt) or 0), int(db.scalar(count_stmt) or 0)


def _voided_invoices(db: Session, start: str, end: str, shopper_id: int | None = None) -> list[Invoice]:
    stmt = select(Invoice).where(
        Invoice.status == "void",
        Invoice.voided_at.is_not(None),
        Invoice.voided_at >= start,
        Invoice.voided_at < end,
    )
    if shopper_id is not None:
        stmt = stmt.where(Invoice.shopper_id == shopper_id)
    return list(db.execute(stmt).scalars())


def _collected_invoices(db: Session, start: str, end: str) -> list[Invoice]:
    return list(
        db.execute(
            select(Invoice)
            .options(
                selectinload(Invoice.lines),
                selectinload(Invoice.shopper),
                selectinload(Invoice.purchase_order),
                selectinload(Invoice.payments),
            )
            .where(
                Invoice.status == "paid",
                Invoice.paid_at.is_not(None),
                Invoice.paid_at >= start,
                Invoice.paid_at < end,
            )
            .order_by(Invoice.paid_at.asc())
        ).scalars()
    )


def _shopper_out(db: Session, shopper_id: int | None) -> dict | None:
    if shopper_id is None:
        return None
    shopper = db.get(Shopper, shopper_id)
    if shopper is None:
        return None
    return {"id": shopper.id, "name": shopper.name, "phone": shopper.phone, "email": shopper.email}


def _sales_bundle(
    db: Session,
    settings,
    invoices: list[Invoice],
    date_from: str,
    date_to: str,
    start: str,
    end: str,
    shopper_id: int | None = None,
) -> dict:
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
            "writeoff_cents": 0,
        }
    )
    revenue = 0
    cogs = 0
    cash = 0
    credit = 0
    tax = 0
    subtotal = 0
    paid_count = 0
    unpaid_count = 0
    salespeople: dict[str, dict] = defaultdict(
        lambda: {"name": "", "receipt_count": 0, "revenue_cents": 0, "cogs_cents": 0, "collected_cents": 0}
    )
    customers: dict[int, dict] = defaultdict(
        lambda: {
            "shopper_id": 0,
            "name": "",
            "phone": "",
            "receipt_count": 0,
            "revenue_cents": 0,
            "cogs_cents": 0,
            "collected_cents": 0,
        }
    )
    for inv in invoices:
        revenue += inv.total_cents
        cogs += inv.cogs_cents or 0
        tax += inv.tax_cents or 0
        subtotal += inv.subtotal_cents or 0
        if inv.status == "paid":
            cash += inv.total_cents
            paid_count += 1
        else:
            credit += inv.total_cents
            unpaid_count += 1
        seller = (inv.salesperson_name or "").strip()
        sp = salespeople[seller or "_"]
        sp["name"] = seller
        sp["receipt_count"] += 1
        sp["revenue_cents"] += inv.total_cents
        sp["cogs_cents"] += inv.cogs_cents or 0
        cust = customers[inv.shopper_id]
        cust["shopper_id"] = inv.shopper_id
        cust["name"] = inv.shopper.name if inv.shopper else ""
        cust["phone"] = inv.shopper.phone if inv.shopper else ""
        cust["receipt_count"] += 1
        cust["revenue_cents"] += inv.total_cents
        cust["cogs_cents"] += inv.cogs_cents or 0
        for ln in inv.lines:
            row = item_acc[ln.sku]
            row["sku"] = ln.sku
            row["name"] = ln.name
            row["name_id"] = ln.name_id or ln.name
            row["quantity"] += ln.quantity
            row["revenue_cents"] += ln.line_total_cents
            row["cogs_cents"] += ln.cogs_cents or 0

    if shopper_id is None:
        for sku, cents, name, name_id in _writeoffs_by_sku(db, start, end):
            row = item_acc[sku]
            row["sku"] = sku
            row["name"] = row["name"] or name
            row["name_id"] = row["name_id"] or name_id
            row["writeoff_cents"] += cents

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
            "writeoff_cents": 0,
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
        row["quantity"] = from_store(row["quantity"])
        profit = row["revenue_cents"] - row["cogs_cents"]
        writeoff = row.get("writeoff_cents", 0)
        row["writeoff_cents"] = writeoff
        row["profit_cents"] = profit
        row["margin_bps"] = _margin_bps(profit, row["revenue_cents"])
        row["adjusted_profit_cents"] = profit - writeoff
        row["adjusted_margin_bps"] = _margin_bps(profit - writeoff, row["revenue_cents"])
        items.append(row)
        key = str(row["category_id"] or "none")
        cat = cat_acc[key]
        cat["category_id"] = row["category_id"]
        cat["name"] = row["category_name"] or "Uncategorized"
        cat["name_id"] = row["category_name_id"] or "Tanpa kategori"
        cat["quantity"] += row["quantity"]
        cat["revenue_cents"] += row["revenue_cents"]
        cat["cogs_cents"] += row["cogs_cents"]
        cat["writeoff_cents"] += row.get("writeoff_cents", 0)

    categories = []
    for cat in cat_acc.values():
        profit = cat["revenue_cents"] - cat["cogs_cents"]
        writeoff = cat.get("writeoff_cents", 0)
        cat["writeoff_cents"] = writeoff
        cat["profit_cents"] = profit
        cat["margin_bps"] = _margin_bps(profit, cat["revenue_cents"])
        cat["adjusted_profit_cents"] = profit - writeoff
        cat["adjusted_margin_bps"] = _margin_bps(profit - writeoff, cat["revenue_cents"])
        categories.append(cat)

    pay_stmt = (
        select(InvoicePayment)
        .options(
            selectinload(InvoicePayment.invoice).selectinload(Invoice.shopper),
        )
        .where(InvoicePayment.created_at >= start, InvoicePayment.created_at < end)
    )
    if shopper_id is not None:
        pay_stmt = pay_stmt.join(Invoice, Invoice.id == InvoicePayment.invoice_id).where(
            Invoice.shopper_id == shopper_id
        )
    pay_rows = list(db.execute(pay_stmt).scalars())
    for pay in pay_rows:
        inv = pay.invoice
        if inv is None or inv.status == "void":
            continue
        seller = (inv.salesperson_name or "").strip()
        sp = salespeople[seller or "_"]
        sp["name"] = seller
        sp["collected_cents"] += pay.amount_cents
        cust = customers[inv.shopper_id]
        cust["shopper_id"] = inv.shopper_id
        cust["name"] = inv.shopper.name if inv.shopper else cust["name"]
        cust["phone"] = inv.shopper.phone if inv.shopper else cust["phone"]
        cust["collected_cents"] += pay.amount_cents

    items.sort(key=lambda r: r["revenue_cents"], reverse=True)
    categories.sort(key=lambda r: r["revenue_cents"], reverse=True)

    def _close(rows: list[dict]) -> list[dict]:
        out = []
        for row in rows:
            profit_row = row["revenue_cents"] - row["cogs_cents"]
            row["profit_cents"] = profit_row
            row["margin_bps"] = _margin_bps(profit_row, row["revenue_cents"])
            out.append(row)
        out.sort(key=lambda r: r["revenue_cents"], reverse=True)
        return out

    profit = revenue - cogs
    collected_cents, collected_count = _collected_payments(db, start, end, shopper_id)
    if shopper_id is None:
        damage = _purpose_cogs(db, start, end, "damage")
        supplier_return = _purpose_cogs(db, start, end, "supplier_return")
    else:
        damage = 0
        supplier_return = 0
    writeoffs = damage + supplier_return
    voided = _voided_invoices(db, start, end, shopper_id)
    adjusted = profit - writeoffs
    return {
        "date_from": date_from,
        "date_to": date_to,
        "shopper_id": shopper_id,
        "shopper": _shopper_out(db, shopper_id),
        "currency_symbol": settings.currency_symbol or "Rp",
        "currency_code": "IDR",
        "receipt_count": len(invoices),
        "paid_count": paid_count,
        "unpaid_count": unpaid_count,
        "revenue_cents": revenue,
        "subtotal_cents": subtotal,
        "tax_cents": tax,
        "tax_bps": settings.tax_rate_bps,
        "cash_cents": cash,
        "credit_cents": credit,
        "collected_cents": collected_cents,
        "collected_count": collected_count,
        "cogs_cents": cogs,
        "profit_cents": profit,
        "margin_bps": _margin_bps(profit, revenue),
        "damage_cents": damage,
        "supplier_return_cents": supplier_return,
        "writeoff_cents": writeoffs,
        "adjusted_profit_cents": adjusted,
        "adjusted_margin_bps": _margin_bps(adjusted, revenue),
        "voided_cents": sum(inv.total_cents for inv in voided),
        "voided_count": len(voided),
        "receipts": [invoice_out(inv) for inv in invoices],
        "items": items,
        "categories": categories,
        "salespeople": _close(list(salespeople.values())),
        "customers": _close(list(customers.values())),
    }
