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


class ShopperPatch(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None


class CategoryIn(BaseModel):
    name: str = Field(min_length=1)
    name_id: str = ""


class CategoryOut(BaseModel):
    id: int
    name: str


class LocationIn(BaseModel):
    name: str = Field(min_length=1)
    name_id: str = ""


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
    quantity: float = Field(default=0, ge=0)
    unit: str = "ea"
    reorder_point: float = Field(default=0, ge=0)
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
    reorder_point: float | None = Field(default=None, ge=0)
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
    quantity: float
    available: float | None = None
    reserved: float = 0
    unit: str
    reorder_point: float
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
    quantity: float = Field(ge=0)
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
    quantity_delta: float
    quantity_after: float
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
    quantity: float = Field(gt=0)
    increment: bool = False


class PoLineOut(BaseModel):
    id: int
    item_id: int
    sku: str
    name: str
    name_id: str = ""
    quantity: float
    unit: str = "ea"
    unit_price_cents: int
    line_total_cents: int
    available: float | None = None


class PlaceIn(BaseModel):
    note: str = ""
    salesperson_name: str = ""
    paid: bool = True


class InvoiceLineOut(BaseModel):
    id: int
    sku: str
    name: str
    name_id: str = ""
    quantity: float
    unit: str = "ea"
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
    due_date: str | None = None
    amount_paid_cents: int = 0
    balance_cents: int = 0
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
    restock_prefix: str | None = None
    damage_prefix: str | None = None
    return_prefix: str | None = None
    credit_days: int | None = Field(default=None, ge=0, le=365)
    allow_lan: bool | None = None


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
    shop_today: str = ""
    pin_set: bool = False
    allow_lan: bool = False
    credit_days: int = 30


class PaymentIn(BaseModel):
    amount_cents: int = Field(gt=0)
    note: str = ""


class InvoiceDueIn(BaseModel):
    due_date: str = Field(min_length=8)


class CreditNoteIn(BaseModel):
    shopper_id: int
    invoice_id: int | None = None
    body: str = Field(min_length=1, max_length=500)
    promised_date: str | None = None


class Shortage(BaseModel):
    item_id: int
    sku: str
    name: str
    name_id: str = ""
    requested: float
    available: float


class DashboardOut(BaseModel):
    sku_count: int
    units_on_hand: float
    units_reserved: float = 0
    low_stock_count: int
    draft_po_count: int
    today_order_count: int
    today_sales_cents: int
    currency_symbol: str
    currency_code: str = "IDR"
    shop_name: str
    unpaid_count: int = 0
    unpaid_cents: int = 0
    promises_due_count: int = 0
    low_stock_items: list[ItemOut]
    recent_movements: list[MovementOut]


class SupplierIn(BaseModel):
    name: str = Field(min_length=1)
    phone: str = ""
    notes: str = ""


class RestockLineIn(BaseModel):
    item_id: int
    quantity: float = Field(gt=0)
    unit_cost_cents: int = Field(ge=0)


class RestockCreateIn(BaseModel):
    supplier_id: int | None = None
    supplier_name: str | None = None
    supplier_phone: str = ""
    note: str = ""


class OfficeLineIn(BaseModel):
    item_id: int
    quantity: float = Field(gt=0)


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
    salesperson_name: str = ""
    customer_name: str = Field(min_length=1)
    customer_phone: str = Field(min_length=6)
    note: str = ""
    paid: bool = False
    lines: list[OfficeLineIn]


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class SetupIn(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=4, max_length=128)
    display_name: str = ""


class UserCreateIn(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=4, max_length=128)
    display_name: str = ""
    is_sales_agent: bool = False


class UserPatchIn(BaseModel):
    display_name: str | None = None
    password: str | None = Field(default=None, min_length=4, max_length=128)
    is_sales_agent: bool | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    is_sales_agent: bool
    is_active: bool

