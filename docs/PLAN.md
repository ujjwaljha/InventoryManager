# Inventory Manager — Implementation Plan

A one-stop shop: shoppers create a purchase order, place it, stock comes off the shelf, and an invoice is raised. Operators keep the catalog and inventory. One SQLite file, usable from a phone, a MacBook, and a Windows PC.

This document is the build plan. It is written so implementation can proceed without re-deciding architecture.

---

## 1. Problem and outcome

A shop needs **selling** and **stock** in the same place. Shoppers (or staff taking an order at the counter) build a purchase order, place it, and get a bill. The moment the order is placed, on-hand quantity must fall so the next shopper cannot buy stock that is gone.

**Outcome:** on any device’s browser:

| Who | What they can do |
| --- | --- |
| **Shopper** | Browse the catalog, create a purchase order (draft), place the order, receive an invoice, reprint that invoice |
| **Operator** | Maintain items and stock, receive goods, see all orders and invoices, optionally place an order on behalf of a walk-in customer |

**Core rule:** placing an order is one database transaction that (1) rejects the order if any line exceeds available quantity, (2) writes stock-out movements, (3) marks the purchase order **placed**, and (4) **raises an invoice**. Draft purchase orders do not touch inventory.

**Out of scope for v1:** card payments / payment gateways, tax jurisdictions beyond a single shop tax rate, App Store listings, public internet hosting without extra hardening, supplier purchase orders (shop restocking from vendors), multi-company tenancy.

> **Naming.** In this product a **purchase order** is the shopper’s order to buy from *this* shop (draft → placed). It is not a vendor PO used to restock from a supplier. Vendor POs are v2.

---

## 2. Shopper journey (the product spine)

```text
Browse catalog → add lines to a draft purchase order
        → review PO (quantities, prices, total)
        → Place order
        → [atomic] check stock → stock out → raise invoice
        → show invoice (print / save / share)
```

1. **Create purchase order** — shopper (or operator at the counter) starts a draft PO, adds SKUs and quantities. Available stock is shown; lines may be edited or removed. Nothing is reserved yet.
2. **Place order** — confirmation screen with totals. On success the PO is immutable except for cancel (v1: operator-only, restores stock and voids the invoice).
3. **Inventory adjusted** — each line becomes a `stock_movements` row with `kind = 'out'` and `reason` pointing at the PO number. `items.quantity` drops in the same transaction.
4. **Raise invoice** — invoice number is issued (e.g. `INV-2026-0001`), line prices are snapshotted, shopper sees a printable invoice immediately. Operators can open the same invoice later from the invoice list.

If two shoppers race for the last unit, the first commit wins; the second placement returns which lines are short so they can edit the draft and try again.

---

## 3. Product principles

1. **Place order is the only moment that sells stock.** Draft POs are wish-lists. Invoices are the bill for a placed PO. No invoice without a placed order; no stock drop without a placed order.
2. **One database, many screens.** SQLite lives with a small local server. Phones and desktops are clients, not separate databases.
3. **Browser first.** iPhone, Android, macOS, and Windows all have a capable browser. A responsive PWA covers all three without three native codebases.
4. **Two modes, one app.** Shopper UI is a storefront. Operator UI is inventory + all orders + all invoices. Same SQLite file.
5. **Money as integer sen (1/100 rupiah).** Unit sell price and invoice totals never use floating-point. The shop currency is **Indonesian Rupiah (IDR)**; the UI shows `Rp` with no decimals (for example `Rp 78.000`).
6. **Phone-usable checkout.** Large steppers, sticky place-order bar, invoice that prints from the phone browser.
7. **Desktop-usable operations.** Catalog tables, order/invoice registers, CSV, backup.
8. **Two cultures.** The UI is English and Indonesian (Bahasa Indonesia). Default locale is Indonesian. Catalog, purchase-order, and invoice lines store English and Indonesian names.

---

## 4. Recommended architecture

```text
  Shopper phone / laptop              Operator Mac / Windows / phone
  (Safari/Chrome PWA — Shop)          (Chrome/Safari/Edge — Operator)
              \                                /
               \                              /
                +----------------------------+
                         HTTP on LAN
                    FastAPI (Python)
                    SQLAlchemy + SQLite
                    data/inventory.db
```

### Why this stack

| Choice | Reason |
| --- | --- |
| **Python + FastAPI** | Simple SQLite story, typed APIs, one process for shop + operator. |
| **SQLAlchemy 2.x + Alembic** | Explicit schema, migrations. |
| **SQLite WAL + `BEGIN IMMEDIATE`** | Placement is a short exclusive write: stock check + movements + invoice. |
| **React + Vite PWA** | One UI; “Add to Home Screen”; shopper and operator routes. |
| **Not per-device SQLite** | Shoppers and the till must share live quantity. |

### How devices reach the app

| Situation | How to open it |
| --- | --- |
| Same machine as the server | `http://localhost:8000` (operator) and `/shop` (storefront) |
| Phone on the same Wi‑Fi | `http://<lan-ip>:8000/shop` |
| Away from home (later) | Tailscale, Cloudflare Tunnel, or a VPS — plus HTTPS and auth |

v1 assumes **LAN or localhost**.

### Alternatives considered (not v1)

- **Per-device SQLite:** stock would diverge between till and phones.
- **Browser-only SQLite (`sql.js`):** each shopper would have a private catalog.
- **Stripe/Razorpay checkout:** out of scope until invoicing works without a gateway (pay in person / pay later).

---

## 5. Roles and access (v1)

| Role | Access | Auth |
| --- | --- | --- |
| **Shopper** | Catalog, own draft PO, place order, own invoices | Identify by name + phone (created or reused). Session cookie. No password required on trusted LAN. |
| **Operator** | Full catalog CRUD, stock in/adjust, all POs, all invoices, backup, shop settings | Shared operator PIN (optional but recommended). |

Walk-in counter: operator starts a PO, assigns or types the shopper, places the order, invoice prints at the till.

---

## 6. v1 capabilities

### Shopper must-haves

- Browse sellable items (not archived, quantity displayed)
- Search and filter by category
- Create **one active draft purchase order** per shopper (cart)
- Add / change quantity / remove lines; live line total and PO total
- Place order (confirm name, phone, optional note)
- On place: stock adjusted and **invoice raised** in one step
- Order confirmation + invoice screen (print, download PDF or print-to-PDF)
- List of my placed orders and invoices

### Operator must-haves

- Item catalog: SKU, name, description, category, location, **sell price**, cost, quantity, unit, reorder point, notes
- Create / edit / archive items
- Stock **in** (receiving) and **adjust** (count); manual stock **out** only for waste/shrinkage, not for sales
- Sales **must** go through place-order so an invoice exists
- Dashboard: SKUs, units on hand, low stock, open drafts, today’s sales (invoice totals), today’s orders
- All purchase orders (draft / placed / cancelled)
- All invoices (issued / paid / void); mark paid; reprint
- Place order on behalf of a shopper
- CSV export/import of items (prices and catalog, not silent quantity overwrite)
- SQLite backup download
- Shop settings: name, address, phone, tax rate, invoice prefix (currency is fixed to Indonesian Rupiah)
- Responsive layout + PWA

### Nice to have in v1 if time remains

- Camera barcode scan to add a line on phone
- Dark theme following OS preference
- Share invoice via Web Share API
- QR code of the shop LAN URL at the till

### Explicitly later (v2+)

- Payment gateways
- Email/SMS invoice delivery
- Partial fulfillment / backorders (v1: all-or-nothing placement)
- Supplier purchase orders and goods-received notes
- Multi-user operator logins and permissions
- Native desktop wrapper (Tauri)
- Image attachments on items

---

## 7. Data model (SQLite)

Conventions: integer primary keys, UTC ISO-8601 text timestamps, money in integer cents, `PRAGMA foreign_keys = ON`.

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE shop_settings (
  id                INTEGER PRIMARY KEY CHECK (id = 1),
  name              TEXT NOT NULL DEFAULT 'My Shop',
  address           TEXT NOT NULL DEFAULT '',
  phone             TEXT NOT NULL DEFAULT '',
  tax_rate_bps      INTEGER NOT NULL DEFAULT 0 CHECK (tax_rate_bps >= 0), -- 0 = no tax; 1800 = 18.00%
  invoice_prefix    TEXT NOT NULL DEFAULT 'INV',
  next_invoice_seq  INTEGER NOT NULL DEFAULT 1,
  po_prefix         TEXT NOT NULL DEFAULT 'PO',
  next_po_seq       INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE categories (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE COLLATE NOCASE,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE locations (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL UNIQUE COLLATE NOCASE,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE items (
  id                INTEGER PRIMARY KEY,
  sku               TEXT NOT NULL UNIQUE COLLATE NOCASE,
  name              TEXT NOT NULL,
  description       TEXT NOT NULL DEFAULT '',
  category_id       INTEGER REFERENCES categories(id) ON DELETE SET NULL,
  location_id       INTEGER REFERENCES locations(id) ON DELETE SET NULL,
  quantity          INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
  unit              TEXT NOT NULL DEFAULT 'ea',
  reorder_point     INTEGER NOT NULL DEFAULT 0 CHECK (reorder_point >= 0),
  unit_cost_cents   INTEGER NOT NULL DEFAULT 0 CHECK (unit_cost_cents >= 0),
  unit_price_cents  INTEGER NOT NULL DEFAULT 0 CHECK (unit_price_cents >= 0), -- sell price
  notes             TEXT NOT NULL DEFAULT '',
  archived          INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
  created_at        TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_items_name ON items(name);
CREATE INDEX idx_items_category ON items(category_id);
CREATE INDEX idx_items_location ON items(location_id);
CREATE INDEX idx_items_low_stock ON items(quantity, reorder_point)
  WHERE archived = 0;

CREATE TABLE shoppers (
  id            INTEGER PRIMARY KEY,
  name          TEXT NOT NULL,
  phone         TEXT NOT NULL,
  email         TEXT NOT NULL DEFAULT '',
  created_at    TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE (phone)
);

CREATE TABLE purchase_orders (
  id              INTEGER PRIMARY KEY,
  number          TEXT NOT NULL UNIQUE,           -- PO-0001, assigned when created
  shopper_id      INTEGER NOT NULL REFERENCES shoppers(id),
  status          TEXT NOT NULL CHECK (status IN ('draft', 'placed', 'cancelled')),
  note            TEXT NOT NULL DEFAULT '',
  placed_at       TEXT,
  cancelled_at    TEXT,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_po_shopper ON purchase_orders(shopper_id, status);
CREATE INDEX idx_po_status ON purchase_orders(status, created_at DESC);

CREATE TABLE purchase_order_lines (
  id                  INTEGER PRIMARY KEY,
  purchase_order_id   INTEGER NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
  item_id             INTEGER NOT NULL REFERENCES items(id),
  quantity            INTEGER NOT NULL CHECK (quantity > 0),
  -- Snapshot copied from item at add-to-PO time; frozen again at place
  sku                 TEXT NOT NULL,
  name                TEXT NOT NULL,
  unit_price_cents    INTEGER NOT NULL CHECK (unit_price_cents >= 0),
  UNIQUE (purchase_order_id, item_id)
);

CREATE TABLE invoices (
  id                  INTEGER PRIMARY KEY,
  number              TEXT NOT NULL UNIQUE,       -- INV-2026-0001
  purchase_order_id   INTEGER NOT NULL UNIQUE REFERENCES purchase_orders(id),
  shopper_id          INTEGER NOT NULL REFERENCES shoppers(id),
  status              TEXT NOT NULL CHECK (status IN ('issued', 'paid', 'void')),
  subtotal_cents      INTEGER NOT NULL,
  tax_bps             INTEGER NOT NULL,
  tax_cents           INTEGER NOT NULL,
  total_cents         INTEGER NOT NULL,
  shop_name           TEXT NOT NULL,              -- snapshot of letterhead
  shop_address        TEXT NOT NULL,
  shop_phone          TEXT NOT NULL,
  issued_at           TEXT NOT NULL DEFAULT (datetime('now')),
  paid_at             TEXT,
  voided_at           TEXT
);

CREATE INDEX idx_invoices_shopper ON invoices(shopper_id, issued_at DESC);
CREATE INDEX idx_invoices_status ON invoices(status, issued_at DESC);

CREATE TABLE invoice_lines (
  id              INTEGER PRIMARY KEY,
  invoice_id      INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  sku             TEXT NOT NULL,
  name            TEXT NOT NULL,
  quantity        INTEGER NOT NULL,
  unit_price_cents INTEGER NOT NULL,
  line_total_cents INTEGER NOT NULL
);

CREATE TABLE stock_movements (
  id               INTEGER PRIMARY KEY,
  item_id          INTEGER NOT NULL REFERENCES items(id),
  kind             TEXT NOT NULL CHECK (kind IN ('in', 'out', 'adjust')),
  quantity_delta   INTEGER NOT NULL,
  quantity_after   INTEGER NOT NULL CHECK (quantity_after >= 0),
  reason           TEXT NOT NULL DEFAULT '',
  purchase_order_id INTEGER REFERENCES purchase_orders(id),
  invoice_id       INTEGER REFERENCES invoices(id),
  created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_movements_item ON stock_movements(item_id, created_at DESC);
CREATE INDEX idx_movements_created ON stock_movements(created_at DESC);
CREATE INDEX idx_movements_po ON stock_movements(purchase_order_id);
```

### Purchase-order and invoice rules

| Event | PO status | Inventory | Invoice |
| --- | --- | --- | --- |
| Create PO / add lines | `draft` | unchanged | none |
| **Place order** | `placed` | stock out per line | **raised** (`issued`) |
| Operator cancel | `cancelled` | stock in (reversal of the outs) | `void` |
| Mark paid | `placed` | unchanged | `paid` |

- A shopper has **at most one `draft` PO** at a time. Placing it starts a new empty draft on the next add-to-cart.
- Draft lines may use current `unit_price_cents`. At **place** time, prices are snapshotted onto lines (and onto invoice lines) so later catalog price changes do not rewrite old invoices.
- Placement is **all-or-nothing**: if any line’s quantity `>` `items.quantity`, nothing is sold and the PO stays `draft`.
- Invoice totals: `line_total = qty * unit_price`; `subtotal = sum(lines)`; `tax = round(subtotal * tax_bps / 10000)`; `total = subtotal + tax`.
- Invoice and PO numbers are allocated from `shop_settings` in the same transaction as place (invoice seq) or create (PO seq) to avoid duplicates.

### Stock rules (single transaction)

| Kind | Meaning | Quantity change |
| --- | --- | --- |
| `in` | Received from supplier, or cancel-reversal | `quantity += n` (`n > 0`) |
| `out` | Sale on place-order, or shrinkage | `quantity -= n` (`n > 0`); reject if negative |
| `adjust` | Physical count | set to `n`; store `delta = n - old` |

Never update `items.quantity` without a matching `stock_movements` row. Sales outs always set `purchase_order_id` and `invoice_id`.

---

## 8. Place-order transaction (exact sequence)

Service: `orders.place(po_id)` using `BEGIN IMMEDIATE`:

1. Load PO as `draft` with lines; abort if empty.
2. For each line, load item row (locked by the write transaction). If archived or `quantity < line.quantity`, collect a shortage and abort with `409`.
3. Refresh each line’s `sku`, `name`, `unit_price_cents` from the item (final snapshot).
4. For each line: `stock.apply_movement(kind='out', n=line.quantity, po_id=...)`.
5. Set PO `status='placed'`, `placed_at=now`.
6. Allocate `invoices.number` from `shop_settings.next_invoice_seq`, increment seq.
7. Insert `invoices` (`issued`) + `invoice_lines`; stamp letterhead from settings.
8. Update the new stock movements with `invoice_id`.
9. Commit. Return PO + invoice.

Cancel is the inverse: stock `in` for each original out quantity, PO `cancelled`, invoice `void`. Allowed only from `placed` + invoice `issued` (not if `paid`, unless operator explicitly unpays first — v1: cannot cancel paid invoices).

---

## 9. HTTP API (v1)

Base URL: `/api`. JSON. Errors: `{ "detail": "..." }` or, on place shortage, `{ "detail": "...", "shortages": [{ "item_id", "sku", "requested", "available" }] }`.

### Shop (shopper session)

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/shop/session` | Upsert shopper by phone; set session cookie |
| `GET` | `/api/shop/catalog` | Sellable items; `q`, `category_id` |
| `GET` | `/api/shop/po` | Current draft PO (create empty if none) |
| `POST` | `/api/shop/po/lines` | `{ item_id, quantity }` add or replace line |
| `DELETE` | `/api/shop/po/lines/{item_id}` | Remove line |
| `POST` | `/api/shop/po/place` | Place draft → stock out → raise invoice |
| `GET` | `/api/shop/orders` | My placed/cancelled POs |
| `GET` | `/api/shop/invoices` | My invoices |
| `GET` | `/api/shop/invoices/{id}` | Invoice detail for print |

### Operator

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness + DB path + LAN bind hint |
| `GET` | `/api/dashboard` | Stock KPIs + today’s orders/sales |
| `GET`/`POST` | `/api/items` | List / create |
| `GET`/`PATCH` | `/api/items/{id}` | Detail / metadata (not quantity) |
| `POST` | `/api/items/{id}/archive` | Soft-archive |
| `POST` | `/api/items/{id}/movements` | `{ kind: in\|adjust\|out, quantity, reason }` — `out` only for non-sale shrinkage |
| `GET` | `/api/items/{id}/movements` | History |
| `GET` | `/api/movements` | Global feed |
| `GET`/`POST` | `/api/categories` | List / create |
| `GET`/`POST` | `/api/locations` | List / create |
| `GET` | `/api/orders` | All POs; filter status |
| `POST` | `/api/orders` | Create draft for a shopper (counter) |
| `POST` | `/api/orders/{id}/place` | Same engine as shop place |
| `POST` | `/api/orders/{id}/cancel` | Restore stock, void invoice |
| `GET` | `/api/invoices` | Register |
| `GET` | `/api/invoices/{id}` | Detail |
| `POST` | `/api/invoices/{id}/mark-paid` | `issued` → `paid` |
| `GET` | `/api/invoices/{id}.html` | Printable invoice |
| `GET`/`PATCH` | `/api/settings` | Shop letterhead and tax |
| `GET` | `/api/export/items.csv` | CSV download |
| `POST` | `/api/import/items.csv` | Multipart; per-row errors |
| `GET` | `/api/backup` | Download `inventory.db` |

FastAPI serves `frontend/dist/` in production so one process is enough.

---

## 10. User interface

### Shopper (`/shop`)

**Phone:** bottom bar — Shop, Order (badge = draft line count), Invoices, Me  
**Desktop:** top bar + catalog grid

1. **Shop** — search, category chips, cards with price and “in stock”
2. **Item** — description, stepper, Add to purchase order
3. **Purchase order** — lines, qty edit, remove, subtotal/tax/total, **Place order**
4. **Place confirm** — shopper name/phone, note; submit
5. **Invoice** — letterhead, PO number, lines, totals, Issued; Print
6. **My invoices / orders** — history

Sold-out items stay visible but cannot be added (or max stepper = 0).

### Operator (`/` or `/operator`)

**Phone:** bottom bar — Home, Items, Orders, Invoices, More  
**Desktop:** left sidebar

1. **Home** — low stock, today’s orders, today’s invoice total, recent movements
2. **Items** — table/cards, receive stock, edit price
3. **Item detail** — qty, In / Count / Shrink, history, linked invoices
4. **Orders** — drafts and placed POs; open a draft and place at the counter
5. **Invoices** — issued/paid/void; mark paid; print
6. **Invoice print layout** — A4 / thermal-friendly simple table; works on phone
7. **More** — categories, locations, settings, LAN URL + QR, CSV, backup, PIN

### Invoice document (raised invoice)

Must show: shop name/address/phone, invoice number, date, shopper name/phone, PO number, line table (SKU, name, qty, unit price, line total), subtotal, tax, **total due**, status (Issued / Paid / Void). Print CSS: hide chrome, page break after.

---

## 11. Project layout

```text
InventoryManager/
  docs/PLAN.md
  backend/
    app/
      main.py
      db.py
      models.py
      schemas.py
      routers/
        shop.py              # shopper catalog, PO, place, invoices
        items.py
        movements.py
        orders.py            # operator PO list / counter place / cancel
        invoices.py
        catalog.py
        dashboard.py
        settings.py
        io.py
      services/
        stock.py             # transactional quantity + movement
        checkout.py          # place order: stock + raise invoice
    alembic/
    tests/
      test_stock.py
      test_checkout.py       # place, shortage, cancel, invoice totals
    pyproject.toml
  frontend/
    src/
      shop/                  # storefront routes
      operator/
      api.ts
    public/manifest.webmanifest
  data/                      # gitignored
  README.md
```

Dev: Vite `:5173` proxies `/api` to FastAPI `:8000`.  
Prod: `uvicorn` `:8000` serves API + `frontend/dist`.

---

## 12. Implementation phases

Each phase should be mergeable on its own, with tests, before the next starts.

### Phase 0 — Repository skeleton

- Python package, Vite React+TS app, `.gitignore` for `data/`, `node_modules/`, `.venv/`
- README: Mac, Windows, phone on Wi‑Fi; `/shop` vs operator
- `GET /api/health` and a blank PWA shell with Shop / Operator links

**Done when:** `uvicorn` starts, health JSON returns, frontend loads.

### Phase 1 — Schema and stock engine

- Alembic migration for the SQL above (including shoppers, POs, invoices)
- `stock.apply_movement()` tests: in, out, adjust, reject negative
- Seed shop settings, bilingual categories, 8–12 Indonesian grocery items with IDR sell prices and stock, 2 sample shoppers

**Done when:** pytest covers stock math; DB file created in `data/`.

### Phase 2 — Catalog APIs (operator)

- Item, category, location, dashboard, movement feed, CSV, backup, settings
- Sell price on items

**Done when:** API tests pass without the UI.

### Phase 3 — Checkout engine (the one-stop-shop core)

- Draft PO lines; **place** = stock out + raise invoice; shortage `409`; cancel restores stock and voids invoice; mark paid
- Invoice number allocation
- Tests: happy path quantities and invoice totals; concurrent-style sequential race (second place fails); cannot place empty PO; cannot cancel paid invoice

**Done when:** placing a PO in tests drops stock by line qty and creates an `issued` invoice whose total matches the lines.

### Phase 4 — Shopper UI

- Catalog, draft PO, place order, invoice view/print, my invoices
- Phone layout for checkout

**Done when:** a shopper can add two items, place, see invoice, and an operator catalog view shows reduced quantity.

### Phase 5 — Operator UI and PWA

- Items, receive stock, orders register, invoices register, settings, LAN QR
- Counter flow: create PO for a shopper and place
- PWA manifest and shell cache

**Done when:** Chrome 390×844 and a laptop can complete shopper checkout and operator reprint of the invoice.

### Phase 6 — Hardening

- Bind `0.0.0.0` only when “Allow phones on this network” is on
- Operator PIN; shopper session cookie
- WAL checkpoint on backup
- Default: sales cannot use raw stock-out (operator shrinkage is a separate reason)

**Done when:** default bind is localhost-only; LAN mode is explicit.

---

## 13. Testing and verification

### Automated

- **Stock:** table-driven in/out/adjust/reject
- **Checkout:** place deducts stock and raises invoice; shortage leaves draft + unchanged qty; cancel reverses; invoice tax math; unique invoice numbers
- **Import:** CSV with bad SKUs
- **Playwright smoke:** add to PO → place → invoice number visible → item qty decreased

### Manual (required)

1. Operator on Mac/Windows: stock in 10 of SKU A, price set
2. Shopper on phone: add 3 of A to PO, place order
3. Phone shows invoice; quantity on operator screen is 7; movement reason cites the PO
4. Second shopper tries to buy 8 of A → shortage, stock stays 7
5. Print invoice from phone; mark paid on laptop; backup download still contains the invoice
6. Narrow viewport: Place order button reachable; invoice readable

---

## 14. Operations

| Topic | Approach |
| --- | --- |
| **Install** | Python 3.12+, Node 20+; venv, pip, npm, build, uvicorn |
| **Windows** | Same in PowerShell; firewall inbound 8000 if phones should connect |
| **Backup** | `/api/backup` or copy `data/inventory.db` (and `-wal`/`-shm`) |
| **Restore** | Stop server, replace DB file, start |
| **Updates** | Alembic `upgrade head` on start |

SQLite assumes **few concurrent writers**. Placement transactions are short. WAL allows many catalog readers.

---

## 15. Security (honest for a LAN shop)

v1 is a **trusted-network** shop:

- Do not expose port 8000 to the public internet in v1
- Operator PIN protects catalog edits, receiving, cancel, backup
- Shopper session is identity (name/phone), not a bank-grade login
- When remote access is added: HTTPS, real passwords, bind restrictions

---

## 16. Success criteria

Implementation is complete for this plan when:

1. A shopper can create a purchase order and place it from a phone or a computer
2. Placing the order decreases on-hand quantity for every line in one transaction
3. Placing the order **raises an invoice** with a stable number, snapshotted prices, and a printable view
4. Insufficient stock blocks placement and does not change inventory or create an invoice
5. Operator can receive stock, see all orders/invoices, and mark invoices paid
6. Phone, Mac, and Windows browsers share the same SQLite file
7. README documents shop vs operator URLs, Mac/Windows start, and phone-on-LAN access

---

## 17. Suggested first implementation slice

**Phase 0 + Phase 1 + Phase 3 API** (checkout tests) plus a thin UI: catalog list, draft PO, Place order, invoice page.

That slice already proves the business: shopper places an order, stock moves, invoice exists — on any device with a browser.
