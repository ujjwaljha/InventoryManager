from app.models import (
    DamageNote,
    Invoice,
    Item,
    PurchaseOrder,
    Restock,
    ShopSettings,
    StockMovement,
    SupplierReturn,
)
from app.schemas import (
    InvoiceLineOut,
    InvoiceOut,
    ItemOut,
    MovementOut,
    PoLineOut,
    PurchaseOrderOut,
    SettingsOut,
)
from app.qty import from_store, money_qty
from app.services.checkout import balance_cents, compute_tax_cents, get_settings, line_total, paid_cents
from app.services.stock import lot_stats
from app.timeutil import today_shop


def item_out(item: Item, reserved: int = 0) -> ItemOut:
    fifo_cogs, value = lot_stats(item)
    sellable = max(0, item.quantity - reserved)
    return ItemOut(
        id=item.id,
        sku=item.sku,
        name=item.name,
        name_id=item.name_id or item.name,
        description=item.description or "",
        description_id=item.description_id or item.description or "",
        category_id=item.category_id,
        category_name=item.category.name if item.category else None,
        category_name_id=(item.category.name_id or item.category.name) if item.category else None,
        location_id=item.location_id,
        location_name=item.location.name if item.location else None,
        location_name_id=(item.location.name_id or item.location.name) if item.location else None,
        quantity=from_store(item.quantity),
        available=from_store(sellable),
        reserved=from_store(reserved),
        unit=item.unit,
        reorder_point=from_store(item.reorder_point),
        unit_cost_cents=item.unit_cost_cents,
        fifo_cogs_cents=fifo_cogs,
        inventory_value_cents=value,
        unit_price_cents=item.unit_price_cents,
        notes=item.notes or "",
        archived=bool(item.archived),
        created_at=item.created_at,
        updated_at=item.updated_at,
        low_stock=item.quantity <= item.reorder_point and not item.archived,
    )


def movement_out(mov: StockMovement) -> MovementOut:
    item = mov.item
    return MovementOut(
        id=mov.id,
        item_id=mov.item_id,
        item_sku=item.sku if item else None,
        item_name=item.name if item else None,
        item_name_id=(item.name_id or item.name) if item else None,
        kind=mov.kind,
        purpose=mov.purpose or "",
        quantity_delta=from_store(mov.quantity_delta),
        quantity_after=from_store(mov.quantity_after),
        reason=mov.reason or "",
        cogs_cents=mov.cogs_cents or 0,
        unit_cost_cents=mov.unit_cost_cents or 0,
        purchase_order_id=mov.purchase_order_id,
        invoice_id=mov.invoice_id,
        restock_id=mov.restock_id,
        damage_id=mov.damage_id,
        supplier_return_id=mov.supplier_return_id,
        created_at=mov.created_at,
    )


def invoice_out(inv: Invoice) -> InvoiceOut:
    po = inv.purchase_order
    shopper = inv.shopper
    return InvoiceOut(
        id=inv.id,
        number=inv.number,
        purchase_order_id=inv.purchase_order_id,
        purchase_order_number=po.number if po else "",
        shopper_id=inv.shopper_id,
        shopper_name=shopper.name if shopper else "",
        shopper_phone=shopper.phone if shopper else "",
        status=inv.status,
        subtotal_cents=inv.subtotal_cents,
        tax_bps=inv.tax_bps,
        tax_cents=inv.tax_cents,
        total_cents=inv.total_cents,
        cogs_cents=inv.cogs_cents or 0,
        shop_name=inv.shop_name,
        shop_address=inv.shop_address,
        shop_phone=inv.shop_phone,
        currency_symbol=inv.currency_symbol or "Rp",
        currency_code="IDR",
        salesperson_name=inv.salesperson_name or "",
        issued_at=inv.issued_at,
        paid_at=inv.paid_at,
        voided_at=inv.voided_at,
        due_date=getattr(inv, "due_date", None),
        amount_paid_cents=paid_cents(inv),
        balance_cents=balance_cents(inv),
        lines=[
            InvoiceLineOut(
                id=ln.id,
                sku=ln.sku,
                name=ln.name,
                name_id=ln.name_id or ln.name,
                quantity=from_store(ln.quantity),
                unit=getattr(ln, "unit", None) or "ea",
                unit_price_cents=ln.unit_price_cents,
                line_total_cents=ln.line_total_cents,
                cogs_cents=getattr(ln, "cogs_cents", 0) or 0,
            )
            for ln in inv.lines
        ],
    )


def po_out(po: PurchaseOrder, settings: ShopSettings | None = None) -> PurchaseOrderOut:
    subtotal = sum(line_total(ln.quantity, ln.unit_price_cents) for ln in po.lines)
    tax_bps = 0
    symbol = "Rp"
    code = "IDR"
    if settings is None and po.invoice:
        tax_bps = po.invoice.tax_bps
        symbol = po.invoice.currency_symbol or "Rp"
    elif settings is not None:
        tax_bps = settings.tax_rate_bps
        symbol = settings.currency_symbol or "Rp"
        code = getattr(settings, "currency_code", None) or "IDR"
    tax = compute_tax_cents(subtotal, tax_bps) if po.status == "draft" else (po.invoice.tax_cents if po.invoice else 0)
    total = subtotal + tax if po.status == "draft" else (po.invoice.total_cents if po.invoice else subtotal)
    shopper = po.shopper
    return PurchaseOrderOut(
        id=po.id,
        number=po.number,
        shopper_id=po.shopper_id,
        shopper_name=shopper.name if shopper else "",
        shopper_phone=shopper.phone if shopper else "",
        status=po.status,
        note=po.note or "",
        placed_at=po.placed_at,
        cancelled_at=po.cancelled_at,
        created_at=po.created_at,
        updated_at=po.updated_at,
        subtotal_cents=subtotal if po.status == "draft" else (po.invoice.subtotal_cents if po.invoice else subtotal),
        tax_bps=tax_bps if po.status == "draft" else (po.invoice.tax_bps if po.invoice else 0),
        tax_cents=tax,
        total_cents=total,
        currency_symbol=symbol,
        currency_code=code,
        lines=[
            PoLineOut(
                id=ln.id,
                item_id=ln.item_id,
                sku=ln.sku,
                name=ln.name,
                name_id=ln.name_id or ln.name,
                quantity=from_store(ln.quantity),
                unit=ln.item.unit if ln.item is not None else "ea",
                unit_price_cents=ln.unit_price_cents,
                line_total_cents=line_total(ln.quantity, ln.unit_price_cents),
                available=from_store(ln.item.quantity) if ln.item is not None else None,
            )
            for ln in po.lines
        ],
        invoice=invoice_out(po.invoice) if po.invoice else None,
    )


def settings_out(s: ShopSettings) -> SettingsOut:
    return SettingsOut(
        name=s.name,
        address=s.address,
        phone=s.phone,
        tax_rate_bps=s.tax_rate_bps,
        currency_symbol=s.currency_symbol or "Rp",
        currency_code=getattr(s, "currency_code", None) or "IDR",
        invoice_prefix=s.invoice_prefix,
        po_prefix=s.po_prefix,
        next_invoice_seq=s.next_invoice_seq,
        next_po_seq=s.next_po_seq,
        restock_prefix=getattr(s, "restock_prefix", None) or "RST",
        next_restock_seq=int(getattr(s, "next_restock_seq", None) or 1),
        damage_prefix=getattr(s, "damage_prefix", None) or "DMG",
        next_damage_seq=int(getattr(s, "next_damage_seq", None) or 1),
        return_prefix=getattr(s, "return_prefix", None) or "RTN",
        next_return_seq=int(getattr(s, "next_return_seq", None) or 1),
        shop_today=today_shop(),
        pin_set=bool((getattr(s, "operator_pin_hash", None) or "").strip()),
        allow_lan=bool(int(getattr(s, "allow_lan", 0) or 0)),
        credit_days=int(getattr(s, "credit_days", 30) or 0),
    )


def po_out_with_settings(db, po: PurchaseOrder) -> PurchaseOrderOut:
    return po_out(po, get_settings(db))


def restock_out(row: Restock) -> dict:
    supplier = row.supplier
    total = sum(money_qty(ln.quantity, ln.unit_cost_cents) for ln in row.lines)
    return {
        "id": row.id,
        "number": row.number,
        "status": row.status,
        "note": row.note or "",
        "supplier_id": row.supplier_id,
        "supplier_name": supplier.name if supplier else "",
        "supplier_phone": supplier.phone if supplier else "",
        "received_at": row.received_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "total_cost_cents": total,
        "lines": [
            {
                "id": ln.id,
                "item_id": ln.item_id,
                "sku": ln.sku,
                "name": ln.name,
                "name_id": ln.name_id or ln.name,
                "quantity": from_store(ln.quantity),
                "unit_cost_cents": ln.unit_cost_cents,
                "line_total_cents": money_qty(ln.quantity, ln.unit_cost_cents),
            }
            for ln in row.lines
        ],
    }


def damage_out(row: DamageNote) -> dict:
    return {
        "id": row.id,
        "number": row.number,
        "reason": row.reason,
        "created_at": row.created_at,
        "cogs_cents": row.cogs_cents,
        "lines": [
            {
                "id": ln.id,
                "item_id": ln.item_id,
                "sku": ln.sku,
                "name": ln.name,
                "name_id": ln.name_id or ln.name,
                "quantity": from_store(ln.quantity),
                "cogs_cents": ln.cogs_cents,
            }
            for ln in row.lines
        ],
    }


def supplier_return_out(row: SupplierReturn) -> dict:
    supplier = row.supplier
    return {
        "id": row.id,
        "number": row.number,
        "reason": row.reason,
        "created_at": row.created_at,
        "cogs_cents": row.cogs_cents,
        "supplier_id": row.supplier_id,
        "supplier_name": supplier.name if supplier else "",
        "supplier_phone": supplier.phone if supplier else "",
        "lines": [
            {
                "id": ln.id,
                "item_id": ln.item_id,
                "sku": ln.sku,
                "name": ln.name,
                "name_id": ln.name_id or ln.name,
                "quantity": from_store(ln.quantity),
                "cogs_cents": ln.cogs_cents,
            }
            for ln in row.lines
        ],
    }
