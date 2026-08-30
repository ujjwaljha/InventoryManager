# Inventory Manager

A one-stop shop on **SQLite**: shoppers create a **purchase order**, **place** it, **inventory is adjusted**, and an **invoice is raised**. Operators keep the catalog and stock. Use it from a **phone**, **MacBook**, or **Windows** PC — one database, many screens.

## For the shop (Mac or Windows)

Non-technical staff: see **[Start here.txt](Start%20here.txt)**.

**Packaged app (no Python):** GitHub Actions builds `Warung Pojok.exe` (Windows) and `Warung Pojok.app` (Mac). Download the zip from the **Build shop apps** workflow artifacts, unzip, double-click. Leave the window open.

**From source:** install [Python 3](https://www.python.org/downloads/) once (Windows: tick **Add python.exe to PATH**), then double-click **`Start Warung Pojok.command`** (Mac) or **`Start Warung Pojok.bat`** (Windows).

**Wi‑Fi:** phones on the same network scan the QR on the till. That is live sync — one computer is the shop.

**Bluetooth / AirDrop / USB:** Save a copy, send the file, then Open a copy on the other computer (replaces that computer’s data). Not live two-way Bluetooth.

### Build the .exe / .app yourself

```bash
python3 -m pip install -r requirements-build.txt
cd frontend && npm install && npm run build && cd ..
python3 -m PyInstaller --noconfirm --clean warung.spec
```

Windows output: `dist/Warung Pojok/Warung Pojok.exe`  
Mac: `dist/Warung Pojok.app`

## Run (developers)

You need Python 3.12+ and Node 20+.

```bash
chmod +x scripts/run.sh
./scripts/run.sh
```

Then open:

- Operator till: [http://localhost:8000](http://localhost:8000)
- Shop floor: [http://localhost:8000/shop](http://localhost:8000/shop)
- Phone on the same Wi‑Fi: `http://<lan-ip>:8000/shop` (the address is also under Operator → Settings)

The first start creates `data/inventory.db` and seeds a sample Indonesian grocery catalog.

The shop and till support **English** and **Indonesian** (switch **EN | ID** in the header; default is Indonesian). Money is **Indonesian Rupiah (IDR)**, shown as `Rp` with no decimals (for example `Rp 78.000`).

### Development (API + Vite)

```bash
python3 -m pip install -r requirements.txt
cd backend && python3 -m uvicorn app.main:create_app --factory --reload --host 0.0.0.0 --port 8000
```

```bash
cd frontend && npm install && npm run dev
```

Vite is at `http://localhost:5173` and proxies `/api` to port 8000.

### Tests

```bash
python3 -m pip install -r requirements.txt
cd backend && python3 -m pytest
```

## What it does

**Shoppers** (`/shop`)

- Browse the catalog and add lines to a draft purchase order
- Place the order (all-or-nothing against available stock)
- Get an invoice immediately; print or save it

**Operators** (`/`)

- Maintain items, sell prices, and locations
- Receive stock and run counts (sales must go through Place order)
- See every purchase order and invoice; mark invoices paid or cancel (restores stock)
- Export items CSV and download the SQLite file

Placing an order is one transaction: stock out + invoice. Draft purchase orders do not touch inventory.

## Status

| Phase | Description | Status |
| --- | --- | --- |
| Plan | Architecture, shopper flow, schema, API, UI | Done — [docs/PLAN.md](docs/PLAN.md) |
| Phase 0 | Repo skeleton, health API, PWA shell | Done |
| Phase 1 | SQLite schema and stock engine | Done |
| Phase 2 | Catalog APIs | Done |
| Phase 3 | Checkout: place order, stock out, raise invoice | Done |
| Phase 4 | Shopper UI | Done |
| Phase 5 | Operator UI, orders/invoices, PWA manifest | Done |
| Phase 6 | LAN bind opt-in, operator PIN | Later (server binds `0.0.0.0` for phone access) |
