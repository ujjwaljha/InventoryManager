# Inventory Manager — Implementation Plan

A cross-device inventory application backed by SQLite, usable from a phone, a MacBook, and a Windows PC, with one shared stock record.

This document is the build plan. It is written so implementation can proceed without re-deciding architecture.

---

## 1. Problem and outcome

Inventory is typically checked on a phone (shelf, garage, warehouse) and maintained on a laptop. Those devices must see the **same** quantities, SKUs, and history.

**Outcome:** a single operator (or a small household/shop team on one LAN) can:

- Browse, search, and edit items from any device’s browser
- Receive stock, pick stock, and record adjustments
- See low-stock warnings
- Keep all data in one SQLite file that is easy to back up

**Out of scope for v1:** multi-company tenancy, barcode hardware SDKs, accounting/ERP sync, public internet hosting without extra hardening, native App Store / Play Store listings.

---

## 2. Product principles

1. **One database, many screens.** SQLite lives with a small local server. Phones and desktops are clients, not separate databases.
2. **Browser first.** iPhone, Android, macOS, and Windows all already have a capable browser. A responsive Progressive Web App (PWA) covers all three without three native codebases.
3. **SQLite as the system of record.** One file (`data/inventory.db`). Copy the file = backup. No Postgres/MySQL to operate.
4. **Phone-usable in one hand.** Large tap targets, search-first home screen, stock in/out in two taps.
5. **Desktop-usable for bulk work.** Table views, keyboard shortcuts, CSV import/export.

---

## 3. Recommended architecture

```text
  iPhone / Android                 MacBook                    Windows
  (Safari/Chrome PWA)              (Chrome/Safari/Edge)       (Edge/Chrome)
              \                          |                          /
               \                         |                         /
                +------------------------+------------------------+
                                     HTTPS or HTTP
                              (LAN IP, localhost, or Tailscale)
                                     |
                              FastAPI (Python)
                              SQLAlchemy + SQLite
                              data/inventory.db
```

### Why this stack

| Choice | Reason |
| --- | --- |
| **Python + FastAPI** | Simple SQLite story, typed APIs, easy to run on Mac and Windows. |
| **SQLAlchemy 2.x + Alembic** | Explicit schema, migrations, portable SQL. |
| **SQLite WAL mode** | Safe concurrent reads while one writer applies stock moves. |
| **React + Vite PWA** | One UI for phone and desktop; “Add to Home Screen” on iOS/Android; works offline for cached UI (data still needs the server). |
| **Not Flutter / Electron for v1** | Native kits excel at offline-per-device apps. Shared inventory needs a server anyway; a PWA avoids App Store friction and a second desktop runtime. |

### How devices reach the app

| Situation | How to open it |
| --- | --- |
| Same machine as the server (Mac/Windows) | `http://localhost:8000` |
| Phone on the same Wi‑Fi | `http://<lan-ip>:8000` (shown on the server’s status page) |
| Away from home (later) | Tailscale, Cloudflare Tunnel, or a VPS — still SQLite, plus HTTPS and auth |

v1 assumes **LAN or localhost**. Remote access is a later phase, not a blocker.

### Alternatives considered (not v1)

- **Per-device SQLite (Flutter `sqflite`, Capacitor, Tauri-only):** three copies of stock unless a sync protocol is added. Sync is harder than a small server.
- **SQLite in the browser (`sql.js` / OPFS):** data stays on that one browser profile; phones and laptops diverge.
- **Hosted Postgres:** overkill for a personal/shop inventory file; loses the “copy one file to back up” property.

---

## 4. v1 capabilities

### Must have

- Item catalog: SKU, name, description, category, location, quantity on hand, unit, reorder point, unit cost, notes
- Create / edit / archive items (archive, do not hard-delete if movements exist)
- Stock **in**, **out**, and **adjust** (set-to-count) with reason and timestamp
- Movement history per item and a global recent-activity list
- Search by name, SKU, notes
- Filter by category, location, low stock
- Dashboard: total SKUs, units on hand, low-stock count
- CSV export of items; CSV import of new items (no silent quantity overwrite)
- SQLite file download as backup
- Responsive layout: phone list + desktop table
- PWA install prompt / manifest (icon, standalone display)

### Nice to have in v1 if time remains

- Optional PIN / password on the server (LAN is not a security boundary)
- Camera barcode scan on phone (SKU lookup via Barcode Detection API + fallback library)
- Dark theme following OS preference

### Explicitly later (v2+)

- Multi-user roles and audit login
- Purchase orders and suppliers as first-class workflows
- Image attachments
- Native desktop wrapper (Tauri) for a dock/taskbar icon
- Replication / cloud sync of the SQLite file

---

## 5. Data model (SQLite)

Conventions: integer primary keys, UTC ISO-8601 text timestamps, `CHECK` constraints for stock math, foreign keys enabled (`PRAGMA foreign_keys = ON`).

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

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
  id              INTEGER PRIMARY KEY,
  sku             TEXT NOT NULL UNIQUE COLLATE NOCASE,
  name            TEXT NOT NULL,
  description     TEXT NOT NULL DEFAULT '',
  category_id     INTEGER REFERENCES categories(id) ON DELETE SET NULL,
  location_id     INTEGER REFERENCES locations(id) ON DELETE SET NULL,
  quantity        INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
  unit            TEXT NOT NULL DEFAULT 'ea',
  reorder_point   INTEGER NOT NULL DEFAULT 0 CHECK (reorder_point >= 0),
  unit_cost_cents INTEGER NOT NULL DEFAULT 0 CHECK (unit_cost_cents >= 0),
  notes           TEXT NOT NULL DEFAULT '',
  archived        INTEGER NOT NULL DEFAULT 0 CHECK (archived IN (0, 1)),
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_items_name ON items(name);
CREATE INDEX idx_items_category ON items(category_id);
CREATE INDEX idx_items_location ON items(location_id);
CREATE INDEX idx_items_low_stock ON items(quantity, reorder_point)
  WHERE archived = 0;

CREATE TABLE stock_movements (
  id            INTEGER PRIMARY KEY,
  item_id       INTEGER NOT NULL REFERENCES items(id),
  kind          TEXT NOT NULL CHECK (kind IN ('in', 'out', 'adjust')),
  quantity_delta INTEGER NOT NULL,
  quantity_after INTEGER NOT NULL CHECK (quantity_after >= 0),
  reason        TEXT NOT NULL DEFAULT '',
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_movements_item ON stock_movements(item_id, created_at DESC);
CREATE INDEX idx_movements_created ON stock_movements(created_at DESC);
```

### Stock rules (enforced in a single DB transaction)

| Kind | Meaning | Quantity change |
| --- | --- | --- |
| `in` | Received / returned to stock | `quantity += n` (`n > 0`) |
| `out` | Sold / used / picked | `quantity -= n` (`n > 0`); reject if result would be negative |
| `adjust` | Physical count | set `quantity` to `n` (`n >= 0`); store `delta = n - old` |

Never update `items.quantity` without inserting a matching `stock_movements` row in the same transaction.

Money is stored as **integer cents** to avoid floating-point drift.

---

## 6. HTTP API (v1)

Base URL: `/api`. JSON request/response. Errors: `{ "detail": "..." }` with 4xx/5xx.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness + DB path + LAN bind hint |
| `GET` | `/api/dashboard` | SKU count, units, low-stock count, recent movements |
| `GET` | `/api/items` | List; query: `q`, `category_id`, `location_id`, `low_stock`, `include_archived` |
| `POST` | `/api/items` | Create item (quantity 0 unless an initial `adjust` is sent in the same request) |
| `GET` | `/api/items/{id}` | Detail + last N movements |
| `PATCH` | `/api/items/{id}` | Metadata only (not quantity) |
| `POST` | `/api/items/{id}/archive` | Soft-archive |
| `POST` | `/api/items/{id}/movements` | `{ kind, quantity, reason }` |
| `GET` | `/api/items/{id}/movements` | Paged history |
| `GET` | `/api/movements` | Global feed |
| `GET`/`POST` | `/api/categories` | List / create |
| `GET`/`POST` | `/api/locations` | List / create |
| `GET` | `/api/export/items.csv` | CSV download |
| `POST` | `/api/import/items.csv` | Multipart upload; report row errors |
| `GET` | `/api/backup` | Download `inventory.db` |

FastAPI serves the built React `dist/` as static files in production so one process is enough on Mac/Windows.

---

## 7. User interface

### Navigation

- **Phone:** bottom bar — Home, Items, Activity, More (categories, backup, about)
- **Desktop (≥768px):** left sidebar + full-width table

### Screens

1. **Home / dashboard** — search field focused on phone; low-stock list; last 10 movements
2. **Items** — virtualized list (phone cards) / sortable table (desktop)
3. **Item detail** — qty prominent; `+ In` / `− Out` / `Count` actions; metadata form; history
4. **New item** — SKU, name, category, location, reorder point
5. **Activity** — chronological movements
6. **Settings / More** — LAN URL to share with phone, backup download, CSV import/export, optional PIN

### Mobile interaction notes

- Stock buttons are full-width; numeric stepper with large hit area
- Confirm destructive out-of-stock attempts with the remaining quantity shown
- `viewport-fit=cover` and safe-area padding for notched phones
- Avoid hover-only affordances

---

## 8. Project layout

```text
InventoryManager/
  docs/PLAN.md                 # this file
  backend/
    app/
      main.py                  # FastAPI app, static mount
      db.py                    # engine, session, PRAGMAs
      models.py
      schemas.py
      routers/
        items.py
        movements.py
        catalog.py
        dashboard.py
        io.py
      services/
        stock.py               # transactional quantity + movement
    alembic/
    tests/
    pyproject.toml
  frontend/
    src/
      pages/
      components/
      api.ts
    public/manifest.webmanifest
    vite.config.ts
  data/                        # gitignored; inventory.db lives here
  README.md
```

Run in development: Vite on `:5173` proxying `/api` to FastAPI on `:8000`.  
Run in production: `uvicorn` on `:8000` serving API + `frontend/dist`.

---

## 9. Implementation phases

Each phase should be mergeable on its own, with tests, before the next starts.

### Phase 0 — Repository skeleton

- Python package, Vite React+TS app, `.gitignore` for `data/`, `node_modules/`, `.venv/`
- README: how to run on Mac and Windows; how a phone on Wi‑Fi opens the LAN URL
- `POST /api/health` and a blank PWA shell

**Done when:** `uvicorn` starts, health JSON returns, frontend loads.

### Phase 1 — Schema and stock engine

- Alembic initial migration for the SQL above
- `stock.apply_movement()` with tests: in, out, adjust, reject negative, archive rules
- Seed 8–12 sample items so the UI is not empty

**Done when:** pytest covers stock math; DB file created in `data/`.

### Phase 2 — Item and catalog APIs

- CRUD-ish item endpoints, categories, locations, dashboard, movement feed
- CSV export; import with per-row errors
- Backup download

**Done when:** API tests pass without the UI.

### Phase 3 — Desktop UI

- Dashboard, items table, item detail, new item, activity
- Stock in/out/adjust dialogs
- Low-stock highlighting

**Done when:** a laptop browser can manage inventory end to end.

### Phase 4 — Phone UI and PWA

- Responsive breakpoints, bottom nav, large stock controls
- Web app manifest, service worker for shell caching, Apple touch icons
- Status page shows the LAN URL (and QR code) so a phone can join

**Done when:** Chrome device-mode (390×844) and a real phone on LAN can receive stock.

### Phase 5 — Hardening

- Bind to `0.0.0.0` only when the user opts in (“Allow phones on this network”)
- Optional shared PIN (HTTP header or session cookie)
- WAL checkpoint on backup download so the file is consistent
- Basic rate limit on mutating routes if PIN is enabled

**Done when:** default bind is localhost-only; LAN mode is explicit.

---

## 10. Testing and verification

### Automated

- **Backend:** pytest + httpx `TestClient`; SQLite in a temp file per test
- **Stock service:** table-driven cases for in/out/adjust/reject
- **Import:** CSV with bad SKUs and duplicate rows
- **Frontend:** Vitest for helpers; Playwright smoke: create item → stock in → low stock appears

### Manual (required before calling the app “cross-device”)

1. Mac or Windows: start server, create an item, stock in 10
2. Phone on same Wi‑Fi: open LAN URL, confirm quantity 10, stock out 2
3. Laptop: confirm quantity 8 and a movement row
4. Download backup; copy `inventory.db`; restart; data still present
5. Narrow viewport (or real phone): bottom nav usable, stock buttons tappable

---

## 11. Operations

| Topic | Approach |
| --- | --- |
| **Install** | Python 3.12+, Node 20+; `python -m venv`, `pip install`, `npm install`, `npm run build`, `uvicorn` |
| **Windows** | Same commands in PowerShell; if port 8000 is blocked, document `8000` firewall inbound for LAN |
| **Backup** | Copy `data/inventory.db` (and `-wal`/`-shm` if present) or use `/api/backup` |
| **Restore** | Stop server, replace `data/inventory.db`, start server |
| **Updates** | Alembic `upgrade head` on start (or a `manage.py migrate` step) |

SQLite is not a good fit for many concurrent writers over the internet. This design assumes **one writer at a time** (typical for a shop/home). WAL allows many readers.

---

## 12. Security (honest for a LAN app)

v1 is a **trusted-network** tool:

- Do not expose port 8000 to the public internet in v1
- Optional PIN stops casual access on shared Wi‑Fi
- No secrets in the repo; DB file stays in gitignored `data/`
- When remote access is added: HTTPS, a real password, and bind restrictions

---

## 13. Success criteria

The plan is complete when implementation delivers all of the following:

1. One SQLite file holds items, quantities, and movement history
2. The same inventory is visible from a phone browser and a Mac or Windows browser
3. Stock in/out cannot desync `items.quantity` from the sum of movements
4. A non-technical user can start the app, open it on a phone via LAN, and back up the database
5. README documents Mac, Windows, and phone access in under one page

---

## 14. Suggested first implementation slice

When building starts, implement **Phase 0 + Phase 1 + a minimal items list UI** (not the full PWA) so there is a clickable demo: seed data, change quantity, reload on a second browser tab and see the same number.

That slice already proves the architecture: SQLite + local API + any device with a browser.
