# Inventory Manager

A one-stop shop on **SQLite**: shoppers create a **purchase order**, **place** it, **inventory is adjusted**, and an **invoice is raised**. Operators keep the catalog and stock. Use it from a **phone**, **MacBook**, or **Windows** PC — one database, many screens.

This repository is in the planning stage. The full build plan is in [`docs/PLAN.md`](docs/PLAN.md).

## What it will do

**Shoppers**

- Browse the catalog and add lines to a draft purchase order
- Place the order (all-or-nothing against available stock)
- Get an invoice immediately; print or save it
- See their order and invoice history

**Operators**

- Maintain items, sell prices, and locations
- Receive stock and run counts
- See every purchase order and invoice; mark invoices paid
- Place an order at the counter on behalf of a walk-in shopper
- Back up the single `data/inventory.db` file

Placing an order is one transaction: stock out + invoice. Draft purchase orders do not touch inventory.

## How devices will share data

A small local server (FastAPI) owns the SQLite file:

- Operator on the computer running the app: `http://localhost:8000`
- Shoppers on a phone on the same Wi‑Fi: `http://<lan-ip>:8000/shop`

Native App Store / Play Store apps are not required for v1.

## Status

| Phase | Description | Status |
| --- | --- | --- |
| Plan | Architecture, shopper flow, schema, API, UI | Current |
| Phase 0 | Repo skeleton, health API, PWA shell | Not started |
| Phase 1 | SQLite schema and stock engine | Not started |
| Phase 2 | Catalog APIs | Not started |
| Phase 3 | Checkout: place order, stock out, raise invoice | Not started |
| Phase 4 | Shopper UI | Not started |
| Phase 5 | Operator UI, orders/invoices, PWA | Not started |
| Phase 6 | LAN bind opt-in, operator PIN, backups | Not started |

See [docs/PLAN.md](docs/PLAN.md) for data model, place-order sequence, API, screens, testing, and success criteria.
