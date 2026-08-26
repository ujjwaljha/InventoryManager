from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Item, Location, ShopSettings, Shopper
from app.timeutil import utcnow


SEED_CATEGORIES = ["Staples", "Oils", "Snacks", "Household", "Dairy"]
SEED_LOCATIONS = ["Front shelf", "Back store", "Cooler"]

SEED_ITEMS = [
    # sku, name, category, location, qty, reorder, cost_cents, price_cents, unit, description
    ("ATA-5KG", "Aashirvaad Atta 5 kg", "Staples", "Back store", 24, 6, 24500, 28900, "bag", "Whole wheat flour."),
    ("RCE-1KG", "India Gate Rice 1 kg", "Staples", "Back store", 40, 10, 7800, 9900, "bag", "Basmati rice."),
    ("SLT-1KG", "Tata Salt 1 kg", "Staples", "Front shelf", 50, 12, 1800, 2800, "pack", "Iodized salt."),
    ("SGR-1KG", "Madhur Sugar 1 kg", "Staples", "Front shelf", 30, 8, 4200, 5500, "pack", "Refined sugar."),
    ("OIL-1L", "Fortune Sunflower Oil 1 L", "Oils", "Back store", 18, 5, 13500, 16800, "btl", "Refined sunflower oil."),
    ("MUS-500", "Kissan Mustard Oil 500 ml", "Oils", "Back store", 16, 4, 9800, 12500, "btl", "Kachi ghani mustard oil."),
    ("PGL-250", "Parle-G 250 g", "Snacks", "Front shelf", 60, 15, 1500, 2500, "pack", "Glucose biscuits."),
    ("NMO-200", "Haldiram Namkeen 200 g", "Snacks", "Front shelf", 22, 6, 4200, 6500, "pack", "Mixture namkeen."),
    ("TEA-250", "Tata Tea Gold 250 g", "Staples", "Front shelf", 20, 5, 11000, 14500, "pack", "Leaf tea."),
    ("SOAP-4", "Lifebuoy Soap pack of 4", "Household", "Front shelf", 14, 4, 7200, 9900, "pack", "Bath soap."),
    ("DTRG-1", "Surf Excel 1 kg", "Household", "Back store", 12, 3, 15500, 19900, "pack", "Detergent powder."),
    ("MLK-1L", "Amul Taaza 1 L", "Dairy", "Cooler", 28, 8, 5600, 6800, "ctn", "Toned milk tetra pack."),
]


def seed_if_empty(db: Session) -> None:
    settings = db.get(ShopSettings, 1)
    if settings is None:
        db.add(
            ShopSettings(
                id=1,
                name="The Corner Shop",
                address="12 Market Lane, Ward 4",
                phone="022-555-0142",
                tax_rate_bps=0,
                currency_symbol="₹",
                invoice_prefix="INV",
                next_invoice_seq=1,
                po_prefix="PO",
                next_po_seq=1,
            )
        )
        db.flush()

    if db.scalar(select(func.count()).select_from(Category)) == 0:
        now = utcnow()
        cats = {n: Category(name=n, created_at=now) for n in SEED_CATEGORIES}
        for c in cats.values():
            db.add(c)
        locs = {n: Location(name=n, created_at=now) for n in SEED_LOCATIONS}
        for loc in locs.values():
            db.add(loc)
        db.flush()
        for row in SEED_ITEMS:
            sku, name, cat, loc, qty, reorder, cost, price, unit, desc = row
            db.add(
                Item(
                    sku=sku,
                    name=name,
                    description=desc,
                    category_id=cats[cat].id,
                    location_id=locs[loc].id,
                    quantity=qty,
                    unit=unit,
                    reorder_point=reorder,
                    unit_cost_cents=cost,
                    unit_price_cents=price,
                    notes="",
                    archived=0,
                    created_at=now,
                    updated_at=now,
                )
            )

    if db.scalar(select(func.count()).select_from(Shopper)) == 0:
        now = utcnow()
        db.add(Shopper(name="Priya Sharma", phone="9876500001", email="priya@example.com", created_at=now))
        db.add(Shopper(name="Rahul Mehta", phone="9876500002", email="", created_at=now))

    db.commit()
