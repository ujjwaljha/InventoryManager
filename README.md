# Inventory Manager

A cross-device inventory app backed by **SQLite**, usable from a **phone**, **MacBook**, or **Windows** PC. One database, many screens.

This repository is in the planning stage. The full build plan is in [`docs/PLAN.md`](docs/PLAN.md).

## What it will do

- Track items (SKU, location, quantity, reorder point)
- Record stock in, stock out, and physical counts
- Show low-stock warnings and movement history
- Work in the browser on iOS, Android, macOS, and Windows (PWA)
- Store everything in a single `data/inventory.db` file you can copy to back up

## How devices will share data

A small local server (FastAPI) owns the SQLite file. Phones and laptops open the same web UI:

- On the computer running the app: `http://localhost:8000`
- On a phone on the same Wi‑Fi: `http://<lan-ip>:8000`

Native App Store / Play Store apps are not required for v1.

## Status

| Phase | Description | Status |
| --- | --- | --- |
| Plan | Architecture, schema, API, UI, phased delivery | Current |
| Phase 0 | Repo skeleton, health API, PWA shell | Not started |
| Phase 1 | SQLite schema and stock engine | Not started |
| Phase 2 | Item and catalog APIs | Not started |
| Phase 3 | Desktop UI | Not started |
| Phase 4 | Phone UI and PWA | Not started |
| Phase 5 | LAN bind opt-in, optional PIN, backups | Not started |

See [docs/PLAN.md](docs/PLAN.md) for data model, API, screens, testing, and success criteria.
