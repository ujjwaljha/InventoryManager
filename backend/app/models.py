from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ShopSettings(Base):
    __tablename__ = "shop_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, default="Toko Bangunan Makmur")
    address: Mapped[str] = mapped_column(Text, default="")
    phone: Mapped[str] = mapped_column(Text, default="")
    tax_rate_bps: Mapped[int] = mapped_column(Integer, default=0)
    currency_symbol: Mapped[str] = mapped_column(Text, default="Rp")
    currency_code: Mapped[str] = mapped_column(Text, default="IDR")
    invoice_prefix: Mapped[str] = mapped_column(Text, default="INV")
    next_invoice_seq: Mapped[int] = mapped_column(Integer, default=1)
    po_prefix: Mapped[str] = mapped_column(Text, default="PO")
    next_po_seq: Mapped[int] = mapped_column(Integer, default=1)
    restock_prefix: Mapped[str] = mapped_column(Text, default="RST")
    next_restock_seq: Mapped[int] = mapped_column(Integer, default=1)
    damage_prefix: Mapped[str] = mapped_column(Text, default="DMG")
    next_damage_seq: Mapped[int] = mapped_column(Integer, default=1)
    return_prefix: Mapped[str] = mapped_column(Text, default="RTN")
    next_return_seq: Mapped[int] = mapped_column(Integer, default=1)
    operator_pin_hash: Mapped[str] = mapped_column(Text, default="")
    operator_pin_salt: Mapped[str] = mapped_column(Text, default="")
    allow_lan: Mapped[int] = mapped_column(Integer, default=0)
    credit_days: Mapped[int] = mapped_column(Integer, default=30)

    __table_args__ = (CheckConstraint("id = 1", name="ck_settings_singleton"),)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name_id: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    items: Mapped[list[Item]] = relationship(back_populates="category")


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name_id: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    items: Mapped[list[Item]] = relationship(back_populates="location")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_id: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    description_id: Mapped[str] = mapped_column(Text, default="")
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit: Mapped[str] = mapped_column(Text, default="ea")
    reorder_point: Mapped[int] = mapped_column(Integer, default=0)
    unit_cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    unit_price_cents: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    category: Mapped[Category | None] = relationship(back_populates="items")
    location: Mapped[Location | None] = relationship(back_populates="items")
    movements: Mapped[list[StockMovement]] = relationship(back_populates="item")
    lots: Mapped[list[StockLot]] = relationship(back_populates="item")

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_item_qty"),
        CheckConstraint("reorder_point >= 0", name="ck_item_reorder"),
        CheckConstraint("unit_cost_cents >= 0", name="ck_item_cost"),
        CheckConstraint("unit_price_cents >= 0", name="ck_item_price"),
        CheckConstraint("archived IN (0, 1)", name="ck_item_archived"),
        Index("idx_items_name", "name"),
        Index("idx_items_category", "category_id"),
        Index("idx_items_location", "location_id"),
    )


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    restocks: Mapped[list[Restock]] = relationship(back_populates="supplier")
    returns: Mapped[list[SupplierReturn]] = relationship(back_populates="supplier")


class Shopper(Base):
    __tablename__ = "shoppers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    purchase_orders: Mapped[list[PurchaseOrder]] = relationship(back_populates="shopper")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="shopper")
    credit_notes: Mapped[list["CreditNote"]] = relationship(back_populates="shopper")


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    shopper_id: Mapped[int] = mapped_column(ForeignKey("shoppers.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    note: Mapped[str] = mapped_column(Text, default="")
    placed_at: Mapped[str | None] = mapped_column(Text)
    cancelled_at: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    shopper: Mapped[Shopper] = relationship(back_populates="purchase_orders")
    lines: Mapped[list[PurchaseOrderLine]] = relationship(
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderLine.id",
    )
    invoice: Mapped[Invoice | None] = relationship(back_populates="purchase_order")
    movements: Mapped[list[StockMovement]] = relationship(back_populates="purchase_order")

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'placed', 'cancelled')", name="ck_po_status"),
        Index("idx_po_shopper", "shopper_id", "status"),
        Index("idx_po_status", "status", "created_at"),
    )


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_id: Mapped[str] = mapped_column(Text, default="")
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="lines")
    item: Mapped[Item] = relationship()

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_pol_qty"),
        CheckConstraint("unit_price_cents >= 0", name="ck_pol_price"),
        UniqueConstraint("purchase_order_id", "item_id", name="uq_po_item"),
    )


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id"), nullable=False, unique=True
    )
    shopper_id: Mapped[int] = mapped_column(ForeignKey("shoppers.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="issued")
    subtotal_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    tax_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    cogs_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shop_name: Mapped[str] = mapped_column(Text, nullable=False)
    shop_address: Mapped[str] = mapped_column(Text, nullable=False)
    shop_phone: Mapped[str] = mapped_column(Text, nullable=False)
    currency_symbol: Mapped[str] = mapped_column(Text, default="Rp")
    salesperson_name: Mapped[str] = mapped_column(Text, default="")
    issued_at: Mapped[str] = mapped_column(Text, nullable=False)
    paid_at: Mapped[str | None] = mapped_column(Text)
    voided_at: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[str | None] = mapped_column(Text)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="invoice")
    shopper: Mapped[Shopper] = relationship(back_populates="invoices")
    lines: Mapped[list[InvoiceLine]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLine.id",
    )
    payments: Mapped[list[InvoicePayment]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoicePayment.id",
    )

    __table_args__ = (
        CheckConstraint("status IN ('issued', 'paid', 'void')", name="ck_inv_status"),
        Index("idx_invoices_shopper", "shopper_id", "issued_at"),
        Index("idx_invoices_status", "status", "issued_at"),
        Index("idx_invoices_number", "number"),
    )


class InvoicePayment(Base):
    __tablename__ = "invoice_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="payments")

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_pay_amount"),
        Index("idx_payments_invoice", "invoice_id", "created_at"),
        Index("idx_payments_created", "created_at"),
    )


class CreditNote(Base):
    __tablename__ = "credit_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shopper_id: Mapped[int] = mapped_column(ForeignKey("shoppers.id", ondelete="CASCADE"), nullable=False)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    promised_date: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    shopper: Mapped[Shopper] = relationship(back_populates="credit_notes")
    invoice: Mapped["Invoice"] = relationship()

    __table_args__ = (Index("idx_credit_notes_shopper", "shopper_id", "created_at"),)


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_id: Mapped[str] = mapped_column(Text, default="")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(Text, default="ea")
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    cogs_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    invoice: Mapped[Invoice] = relationship(back_populates="lines")


class Restock(Base):
    __tablename__ = "restocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"))
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    note: Mapped[str] = mapped_column(Text, default="")
    received_at: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    supplier: Mapped[Supplier | None] = relationship(back_populates="restocks")
    lines: Mapped[list[RestockLine]] = relationship(
        back_populates="restock",
        cascade="all, delete-orphan",
        order_by="RestockLine.id",
    )
    movements: Mapped[list[StockMovement]] = relationship(back_populates="restock")

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'received')", name="ck_restock_status"),
        Index("idx_restocks_status", "status", "created_at"),
    )


class RestockLine(Base):
    __tablename__ = "restock_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    restock_id: Mapped[int] = mapped_column(ForeignKey("restocks.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_id: Mapped[str] = mapped_column(Text, default="")
    unit_cost_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    restock: Mapped[Restock] = relationship(back_populates="lines")
    item: Mapped[Item] = relationship()

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_rst_qty"),
        CheckConstraint("unit_cost_cents >= 0", name="ck_rst_cost"),
        UniqueConstraint("restock_id", "item_id", name="uq_restock_item"),
    )


class DamageNote(Base):
    __tablename__ = "damage_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    cogs_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    lines: Mapped[list[DamageLine]] = relationship(
        back_populates="damage",
        cascade="all, delete-orphan",
        order_by="DamageLine.id",
    )
    movements: Mapped[list[StockMovement]] = relationship(back_populates="damage")


class DamageLine(Base):
    __tablename__ = "damage_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    damage_id: Mapped[int] = mapped_column(ForeignKey("damage_notes.id", ondelete="CASCADE"), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_id: Mapped[str] = mapped_column(Text, default="")
    cogs_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    damage: Mapped[DamageNote] = relationship(back_populates="lines")
    item: Mapped[Item] = relationship()


class SupplierReturn(Base):
    __tablename__ = "supplier_returns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    cogs_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    supplier: Mapped[Supplier | None] = relationship(back_populates="returns")
    lines: Mapped[list[SupplierReturnLine]] = relationship(
        back_populates="supplier_return",
        cascade="all, delete-orphan",
        order_by="SupplierReturnLine.id",
    )
    movements: Mapped[list[StockMovement]] = relationship(back_populates="supplier_return")


class SupplierReturnLine(Base):
    __tablename__ = "supplier_return_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_return_id: Mapped[int] = mapped_column(
        ForeignKey("supplier_returns.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    name_id: Mapped[str] = mapped_column(Text, default="")
    cogs_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    supplier_return: Mapped[SupplierReturn] = relationship(back_populates="lines")
    item: Mapped[Item] = relationship()


class StockLot(Base):
    """One inbound layer of stock. Outbound sales/damage/returns consume oldest first (FIFO)."""

    __tablename__ = "stock_lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    received_at: Mapped[str] = mapped_column(Text, nullable=False)
    unit_cost_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_original: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="opening")
    restock_id: Mapped[int | None] = mapped_column(ForeignKey("restocks.id"))
    movement_id: Mapped[int | None] = mapped_column(ForeignKey("stock_movements.id"))

    item: Mapped[Item] = relationship(back_populates="lots")
    consumptions: Mapped[list[LotConsumption]] = relationship(back_populates="lot")

    __table_args__ = (
        CheckConstraint("qty_original > 0", name="ck_lot_orig"),
        CheckConstraint("qty_remaining >= 0", name="ck_lot_rem"),
        CheckConstraint("unit_cost_cents >= 0", name="ck_lot_cost"),
        Index("idx_lots_item", "item_id", "received_at", "id"),
        Index("idx_lots_item_remaining", "item_id", "qty_remaining"),
    )


class LotConsumption(Base):
    __tablename__ = "lot_consumptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("stock_lots.id"), nullable=False)
    movement_id: Mapped[int] = mapped_column(ForeignKey("stock_movements.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    lot: Mapped[StockLot] = relationship(back_populates="consumptions")
    movement: Mapped[StockMovement] = relationship(back_populates="consumptions")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_cons_qty"),
        Index("idx_cons_movement", "movement_id"),
        Index("idx_cons_lot", "lot_id"),
    )


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="")
    purpose: Mapped[str] = mapped_column(Text, default="")
    cogs_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_cost_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"))
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"))
    restock_id: Mapped[int | None] = mapped_column(ForeignKey("restocks.id"))
    damage_id: Mapped[int | None] = mapped_column(ForeignKey("damage_notes.id"))
    supplier_return_id: Mapped[int | None] = mapped_column(ForeignKey("supplier_returns.id"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    item: Mapped[Item] = relationship(back_populates="movements")
    purchase_order: Mapped[PurchaseOrder | None] = relationship(back_populates="movements")
    restock: Mapped[Restock | None] = relationship(back_populates="movements")
    damage: Mapped[DamageNote | None] = relationship(back_populates="movements")
    supplier_return: Mapped[SupplierReturn | None] = relationship(back_populates="movements")
    consumptions: Mapped[list[LotConsumption]] = relationship(back_populates="movement")

    __table_args__ = (
        CheckConstraint("kind IN ('in', 'out', 'adjust')", name="ck_mov_kind"),
        CheckConstraint("quantity_after >= 0", name="ck_mov_after"),
        Index("idx_movements_item", "item_id", "created_at"),
        Index("idx_movements_created", "created_at"),
        Index("idx_movements_po", "purchase_order_id"),
        Index("idx_movements_purpose", "purpose", "created_at"),
    )
