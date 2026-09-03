export type Item = {
  id: number;
  sku: string;
  name: string;
  name_id?: string;
  description: string;
  description_id?: string;
  category_id: number | null;
  category_name: string | null;
  category_name_id?: string | null;
  location_id: number | null;
  location_name: string | null;
  location_name_id?: string | null;
  quantity: number;
  available?: number;
  reserved?: number;
  unit: string;
  reorder_point: number;
  unit_cost_cents: number;
  unit_price_cents: number;
  notes: string;
  archived: boolean;
  created_at: string;
  updated_at: string;
  low_stock: boolean;
  fifo_cogs_cents?: number;
  inventory_value_cents?: number;
};

export type Shopper = {
  id: number;
  name: string;
  phone: string;
  email: string;
};

export type PoLine = {
  id: number;
  item_id: number;
  sku: string;
  name: string;
  name_id?: string;
  quantity: number;
  unit?: string;
  unit_price_cents: number;
  line_total_cents: number;
  available: number | null;
};

export type InvoiceLine = {
  id: number;
  sku: string;
  name: string;
  name_id?: string;
  quantity: number;
  unit?: string;
  unit_price_cents: number;
  line_total_cents: number;
  cogs_cents?: number;
};

export type Invoice = {
  id: number;
  number: string;
  purchase_order_id: number;
  purchase_order_number: string;
  shopper_id: number;
  shopper_name: string;
  shopper_phone: string;
  status: string;
  subtotal_cents: number;
  tax_bps: number;
  tax_cents: number;
  total_cents: number;
  shop_name: string;
  shop_address: string;
  shop_phone: string;
  currency_symbol: string;
  currency_code?: string;
  salesperson_name?: string;
  cogs_cents?: number;
  issued_at: string;
  paid_at: string | null;
  age_days?: number;
  voided_at: string | null;
  due_date?: string | null;
  overdue_days?: number;
  amount_paid_cents?: number;
  balance_cents?: number;
  lines: InvoiceLine[];
};

export type PurchaseOrder = {
  id: number;
  number: string;
  shopper_id: number;
  shopper_name: string;
  shopper_phone: string;
  status: string;
  note: string;
  placed_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
  subtotal_cents: number;
  tax_bps: number;
  tax_cents: number;
  total_cents: number;
  currency_symbol: string;
  currency_code?: string;
  lines: PoLine[];
  invoice: Invoice | null;
};

export type Movement = {
  id: number;
  item_id: number;
  item_sku: string | null;
  item_name: string | null;
  item_name_id?: string | null;
  kind: string;
  purpose?: string;
  quantity_delta: number;
  quantity_after: number;
  reason: string;
  cogs_cents?: number;
  unit_cost_cents?: number;
  purchase_order_id: number | null;
  invoice_id: number | null;
  restock_id?: number | null;
  damage_id?: number | null;
  supplier_return_id?: number | null;
  created_at: string;
};

export type Dashboard = {
  sku_count: number;
  units_on_hand: number;
  units_reserved?: number;
  low_stock_count: number;
  draft_po_count: number;
  today_order_count: number;
  today_sales_cents: number;
  unpaid_count?: number;
  unpaid_cents?: number;
  promises_due_count?: number;
  currency_symbol: string;
  currency_code?: string;
  shop_name: string;
  low_stock_items: Item[];
  recent_movements: Movement[];
};

export type Settings = {
  name: string;
  address: string;
  phone: string;
  tax_rate_bps: number;
  currency_symbol: string;
  currency_code?: string;
  invoice_prefix: string;
  po_prefix: string;
  next_invoice_seq: number;
  next_po_seq: number;
  restock_prefix?: string;
  next_restock_seq?: number;
  damage_prefix?: string;
  next_damage_seq?: number;
  return_prefix?: string;
  next_return_seq?: number;
  shop_today?: string;
  pin_set?: boolean;
  allow_lan?: boolean;
  credit_days?: number;
};

export type Shortage = {
  item_id: number;
  sku: string;
  name: string;
  name_id?: string;
  requested: number;
  available: number;
};

export type Category = { id: number; name: string; name_id?: string };

export type Location = { id: number; name: string; name_id?: string };

export type CsvImportResult = {
  created: number;
  updated: number;
  error_count: number;
  errors: { line: number; sku: string; error: string }[];
};

export type Supplier = { id: number; name: string; phone: string; notes?: string };

export type RestockLine = {
  id: number;
  item_id: number;
  sku: string;
  name: string;
  name_id?: string;
  quantity: number;
  unit_cost_cents: number;
  line_total_cents: number;
};

export type Restock = {
  id: number;
  number: string;
  status: string;
  note: string;
  supplier_id: number | null;
  supplier_name: string;
  supplier_phone: string;
  received_at: string | null;
  created_at: string;
  updated_at: string;
  total_cost_cents: number;
  lines: RestockLine[];
};

export type DamageNote = {
  id: number;
  number: string;
  reason: string;
  created_at: string;
  cogs_cents: number;
  lines: { id: number; item_id: number; sku: string; name: string; name_id?: string; quantity: number; cogs_cents: number }[];
};

export type SupplierReturn = {
  id: number;
  number: string;
  reason: string;
  created_at: string;
  cogs_cents: number;
  supplier_id: number | null;
  supplier_name: string;
  supplier_phone: string;
  lines: { id: number; item_id: number; sku: string; name: string; name_id?: string; quantity: number; cogs_cents: number }[];
};

export type StockLot = {
  id: number;
  received_at: string;
  unit_cost_cents: number;
  qty_original: number;
  qty_remaining: number;
  source: string;
  restock_id: number | null;
};

export type ReportItem = {
  sku: string;
  name: string;
  name_id?: string;
  category_id: number | null;
  category_name: string;
  category_name_id?: string;
  quantity: number;
  revenue_cents: number;
  cogs_cents: number;
  profit_cents: number;
  margin_bps: number;
  writeoff_cents?: number;
  adjusted_profit_cents?: number;
  adjusted_margin_bps?: number;
};

export type ReportPerson = {
  name?: string;
  phone?: string;
  shopper_id?: number;
  receipt_count: number;
  revenue_cents: number;
  cogs_cents: number;
  collected_cents?: number;
  profit_cents: number;
  margin_bps: number;
};

export type ReportCategory = {
  category_id: number | null;
  name: string;
  name_id?: string;
  quantity: number;
  revenue_cents: number;
  cogs_cents: number;
  profit_cents: number;
  margin_bps: number;
  writeoff_cents?: number;
  adjusted_profit_cents?: number;
  adjusted_margin_bps?: number;
};

export type SalesReport = {
  date_from: string;
  date_to: string;
  currency_symbol: string;
  receipt_count: number;
  paid_count?: number;
  unpaid_count?: number;
  revenue_cents: number;
  subtotal_cents?: number;
  tax_cents?: number;
  tax_bps?: number;
  cash_cents?: number;
  credit_cents?: number;
  collected_cents?: number;
  collected_count?: number;
  cogs_cents: number;
  profit_cents: number;
  margin_bps: number;
  damage_cents?: number;
  supplier_return_cents?: number;
  writeoff_cents?: number;
  adjusted_profit_cents?: number;
  adjusted_margin_bps?: number;
  voided_cents?: number;
  voided_count?: number;
  receipts: Invoice[];
  items: ReportItem[];
  categories: ReportCategory[];
  salespeople?: ReportPerson[];
    customers?: ReportPerson[];
    shopper_id?: number | null;
    shopper?: { id: number; name: string; phone: string; email?: string } | null;
};

export type AgingBuckets = {
  d0_30: number;
  d31_60: number;
  d61_90: number;
  d90_plus: number;
};

export type CreditNote = {
  id: number;
  body: string;
  invoice_id?: number | null;
  promised_date?: string | null;
  created_at: string;
};

export type CreditCustomer = {
  shopper_id: number;
  shopper_name: string;
  shopper_phone: string;
  invoice_count: number;
  unpaid_cents: number;
  oldest_issued_at: string;
  aging_cents?: AgingBuckets;
  notes?: CreditNote[];
};

export type CreditReport = {
  currency_symbol: string;
  invoice_count: number;
  unpaid_cents: number;
  aging_cents?: AgingBuckets;
  customers: CreditCustomer[];
  invoices: Invoice[];
  promises_due_count?: number;
};

export type StockReport = {
  currency_symbol: string;
  sku_count: number;
  units_on_hand: number;
  inventory_value_cents: number;
  items: Item[];
};
