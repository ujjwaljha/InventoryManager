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
    name: Mapped[str] = mapped_column(Text, default="The Corner Shop")
    address: Mapped[str] = mapped_column(Text, default="")
    phone: Mapped[str] = mapped_column(Text, default="")
    tax_rate_bps: Mapped[int] = mapped_column(Integer, default=0)
    currency_symbol: Mapped[str] = mapped_column(Text, default="₹")
    invoice_prefix: Mapped[str] = mapped_column(Text, default="INV")
    next_invoice_seq: Mapped[int] = mapped_column(Integer, default=1)
    po_prefix: Mapped[str] = mapped_column(Text, default="PO")
    next_po_seq: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (CheckConstraint("id = 1", name="ck_settings_singleton"),)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    items: Mapped[list[Item]] = relationship(back_populates="category")


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    items: Mapped[list[Item]] = relationship(back_populates="location")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
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


class Shopper(Base):
    __tablename__ = "shoppers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    purchase_orders: Mapped[list[PurchaseOrder]] = relationship(back_populates="shopper")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="shopper")


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
    shop_name: Mapped[str] = mapped_column(Text, nullable=False)
    shop_address: Mapped[str] = mapped_column(Text, nullable=False)
    shop_phone: Mapped[str] = mapped_column(Text, nullable=False)
    currency_symbol: Mapped[str] = mapped_column(Text, default="₹")
    issued_at: Mapped[str] = mapped_column(Text, nullable=False)
    paid_at: Mapped[str | None] = mapped_column(Text)
    voided_at: Mapped[str | None] = mapped_column(Text)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="invoice")
    shopper: Mapped[Shopper] = relationship(back_populates="invoices")
    lines: Mapped[list[InvoiceLine]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLine.id",
    )

    __table_args__ = (
        CheckConstraint("status IN ('issued', 'paid', 'void')", name="ck_inv_status"),
        Index("idx_invoices_shopper", "shopper_id", "issued_at"),
        Index("idx_invoices_status", "status", "issued_at"),
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
    )
    sku: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_cents: Mapped[int] = mapped_column(Integer, nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="lines")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="")
    purchase_order_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_orders.id"))
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"))
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    item: Mapped[Item] = relationship(back_populates="movements")
    purchase_order: Mapped[PurchaseOrder | None] = relationship(back_populates="movements")

    __table_args__ = (
        CheckConstraint("kind IN ('in', 'out', 'adjust')", name="ck_mov_kind"),
        CheckConstraint("quantity_after >= 0", name="ck_mov_after"),
        Index("idx_movements_item", "item_id", "created_at"),
        Index("idx_movements_created", "created_at"),
        Index("idx_movements_po", "purchase_order_id"),
    )
