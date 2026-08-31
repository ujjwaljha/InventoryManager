from __future__ import annotations

from pydantic import BaseModel, Field


class SessionIn(BaseModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=6)
    email: str = ""


class ShopperOut(BaseModel):
    id: int
    name: str
    phone: str
    email: str


class CategoryIn(BaseModel):
    name: str = Field(min_length=1)
    name_id: str = ""


class CategoryOut(BaseModel):
    id: int
    name: str


class LocationIn(BaseModel):
    name: str = Field(min_length=1)


class LocationOut(BaseModel):
    id: int
    name: str


class ItemIn(BaseModel):
    sku: str = Field(min_length=1)
    name: str = Field(min_length=1)
    name_id: str = ""
    description: str = ""
    description_id: str = ""
    category_id: int | None = None
    location_id: int | None = None
    quantity: int = Field(default=0, ge=0)
    unit: str = "ea"
    reorder_point: int = Field(default=0, ge=0)
    unit_cost_cents: int = Field(default=0, ge=0)
    unit_price_cents: int = Field(default=0, ge=0)
    notes: str = ""


class ItemPatch(BaseModel):
    sku: str | None = None
    name: str | None = None
    name_id: str | None = None
    description: str | None = None
    description_id: str | None = None
    category_id: int | None = None
    location_id: int | None = None
    unit: str | None = None
    reorder_point: int | None = Field(default=None, ge=0)
    unit_cost_cents: int | None = Field(default=None, ge=0)
    unit_price_cents: int | None = Field(default=None, ge=0)
    notes: str | None = None


class ItemOut(BaseModel):
    id: int
    sku: str
    name: str
    name_id: str = ""
    description: str
    description_id: str = ""
    category_id: int | None
    category_name: str | None
    category_name_id: str | None = None
    location_id: int | None
    location_name: str | None
    location_name_id: str | None = None
    quantity: int
    unit: str
    reorder_point: int
    unit_cost_cents: int
    fifo_cogs_cents: int = 0
    inventory_value_cents: int = 0
    unit_price_cents: int
    notes: str
    archived: bool
    created_at: str
    updated_at: str
    low_stock: bool


class MovementIn(BaseModel):
    kind: str
    quantity: int = Field(ge=0)
    reason: str = ""
    purpose: str = ""
    unit_cost_cents: int | None = Field(default=None, ge=0)


class MovementOut(BaseModel):
    id: int
    item_id: int
    item_sku: str | None = None
    item_name: str | None = None
    item_name_id: str | None = None
    kind: str
    purpose: str = ""
    quantity_delta: int
    quantity_after: int
    reason: str
    cogs_cents: int = 0
    unit_cost_cents: int = 0
    purchase_order_id: int | None
    invoice_id: int | None
    restock_id: int | None = None
    damage_id: int | None = None
    supplier_return_id: int | None = None
    created_at: str


class PoLineIn(BaseModel):
    item_id: int
    quantity: int = Field(gt=0)


class PoLineOut(BaseModel):
    id: int
    item_id: int
    sku: str
    name: str
    name_id: str = ""
    quantity: int
    unit_price_cents: int
    line_total_cents: int
    available: int | None = None


class PlaceIn(BaseModel):
    note: str = ""
    salesperson_name: str = ""


class InvoiceLineOut(BaseModel):
    id: int
    sku: str
    name: str
    name_id: str = ""
    quantity: int
    unit_price_cents: int
    line_total_cents: int
    cogs_cents: int = 0


class InvoiceOut(BaseModel):
    id: int
    number: str
    purchase_order_id: int
    purchase_order_number: str
    shopper_id: int
    shopper_name: str
    shopper_phone: str
    status: str
    subtotal_cents: int
    tax_bps: int
    tax_cents: int
    total_cents: int
    shop_name: str
    shop_address: str
    shop_phone: str
    currency_symbol: str
    currency_code: str = "IDR"
    salesperson_name: str = ""
    cogs_cents: int = 0
    issued_at: str
    paid_at: str | None
    voided_at: str | None
    lines: list[InvoiceLineOut]


class PurchaseOrderOut(BaseModel):
    id: int
    number: str
    shopper_id: int
    shopper_name: str
    shopper_phone: str
    status: str
    note: str
    placed_at: str | None
    cancelled_at: str | None
    created_at: str
    updated_at: str
    subtotal_cents: int
    tax_bps: int
    tax_cents: int
    total_cents: int
    currency_symbol: str
    currency_code: str = "IDR"
    lines: list[PoLineOut]
    invoice: InvoiceOut | None = None


class CounterOrderIn(BaseModel):
    shopper_id: int | None = None
    name: str | None = None
    phone: str | None = None
    email: str = ""


class SettingsIn(BaseModel):
    name: str | None = None
    address: str | None = None
    phone: str | None = None
    tax_rate_bps: int | None = Field(default=None, ge=0)
    currency_symbol: str | None = None
    currency_code: str | None = None
    invoice_prefix: str | None = None
    po_prefix: str | None = None


class SettingsOut(BaseModel):
    name: str
    address: str
    phone: str
    tax_rate_bps: int
    currency_symbol: str
    currency_code: str = "IDR"
    invoice_prefix: str
    po_prefix: str
    next_invoice_seq: int
    next_po_seq: int
    restock_prefix: str = "RST"
    next_restock_seq: int = 1
    damage_prefix: str = "DMG"
    next_damage_seq: int = 1
    return_prefix: str = "RTN"
    next_return_seq: int = 1


class Shortage(BaseModel):
    item_id: int
    sku: str
    name: str
    name_id: str = ""
    requested: int
    available: int


class DashboardOut(BaseModel):
    sku_count: int
    units_on_hand: int
    low_stock_count: int
    draft_po_count: int
    today_order_count: int
    today_sales_cents: int
    currency_symbol: str
    currency_code: str = "IDR"
    shop_name: str
    low_stock_items: list[ItemOut]
    recent_movements: list[MovementOut]


class SupplierIn(BaseModel):
    name: str = Field(min_length=1)
    phone: str = ""
    notes: str = ""


class RestockLineIn(BaseModel):
    item_id: int
    quantity: int = Field(gt=0)
    unit_cost_cents: int = Field(ge=0)


class RestockCreateIn(BaseModel):
    supplier_id: int | None = None
    supplier_name: str | None = None
    supplier_phone: str = ""
    note: str = ""


class OfficeLineIn(BaseModel):
    item_id: int
    quantity: int = Field(gt=0)


class DamageIn(BaseModel):
    reason: str = Field(min_length=1)
    lines: list[OfficeLineIn]


class SupplierReturnIn(BaseModel):
    reason: str = Field(min_length=1)
    supplier_id: int | None = None
    supplier_name: str | None = None
    supplier_phone: str = ""
    lines: list[OfficeLineIn]


class TillSaleIn(BaseModel):
    salesperson_name: str = Field(min_length=1)
    customer_name: str = Field(min_length=1)
    customer_phone: str = Field(min_length=6)
    note: str = ""
    lines: list[OfficeLineIn]

