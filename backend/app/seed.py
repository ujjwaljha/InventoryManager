from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Item, Location, ShopSettings, Shopper
from app.timeutil import utcnow


def idr(rupiah: int) -> int:
    """Store whole rupiah as integer sen (1/100), matching the cents fields."""
    return rupiah * 100


SEED_CATEGORIES = [
    ("Staples", "Sembako"),
    ("Oils", "Minyak"),
    ("Snacks", "Makanan ringan"),
    ("Household", "Rumah tangga"),
    ("Dairy", "Susu"),
]
SEED_LOCATIONS = [
    ("Front shelf", "Rak depan"),
    ("Back store", "Gudang"),
    ("Cooler", "Kulkas"),
]

# sku, name_en, name_id, category, location, qty, reorder, cost_idr, price_idr, unit, desc_en, desc_id
SEED_ITEMS = [
    (
        "ATA-5KG",
        "Ramos Super Rice 5 kg",
        "Beras Ramos Super 5 kg",
        "Staples",
        "Back store",
        24,
        6,
        72000,
        78000,
        "kg",
        "Premium white rice.",
        "Beras putih premium.",
    ),
    (
        "RCE-1KG",
        "Pandan Wangi Rice 1 kg",
        "Beras Pandan Wangi 1 kg",
        "Staples",
        "Back store",
        40,
        10,
        14000,
        16500,
        "kg",
        "Fragrant rice.",
        "Beras wangi.",
    ),
    (
        "SLT-1KG",
        "Refina Table Salt 1 kg",
        "Garam Dapur Refina 1 kg",
        "Staples",
        "Front shelf",
        50,
        12,
        6000,
        8000,
        "kg",
        "Iodized table salt.",
        "Garam beryodium.",
    ),
    (
        "SGR-1KG",
        "Gulaku Sugar 1 kg",
        "Gula Pasir Gulaku 1 kg",
        "Staples",
        "Front shelf",
        30,
        8,
        14500,
        17500,
        "kg",
        "Granulated sugar.",
        "Gula pasir.",
    ),
    (
        "OIL-1L",
        "Tropical Cooking Oil 1 L",
        "Minyak Goreng Tropical 1 L",
        "Oils",
        "Back store",
        18,
        5,
        15500,
        18000,
        "L",
        "Palm cooking oil.",
        "Minyak goreng sawit.",
    ),
    (
        "MUS-500",
        "Bango Sweet Soy 550 ml",
        "Kecap Manis Bango 550 ml",
        "Oils",
        "Front shelf",
        16,
        4,
        14000,
        18500,
        "btl",
        "Sweet soy sauce.",
        "Kecap manis.",
    ),
    (
        "PGL-250",
        "Indomie Goreng (pack)",
        "Indomie Goreng (bungkus)",
        "Snacks",
        "Front shelf",
        60,
        15,
        2800,
        3500,
        "pack",
        "Instant fried noodles.",
        "Mi instan goreng.",
    ),
    (
        "NMO-200",
        "Chitato Snack 68 g",
        "Chitato 68 g",
        "Snacks",
        "Front shelf",
        22,
        6,
        8500,
        11000,
        "pack",
        "Potato chips.",
        "Keripik kentang.",
    ),
    (
        "TEA-250",
        "Sariwangi Tea Bags 25s",
        "Teh Celup Sariwangi 25s",
        "Staples",
        "Front shelf",
        20,
        5,
        9500,
        12000,
        "pack",
        "Black tea bags.",
        "Teh hitam celup.",
    ),
    (
        "SOAP-4",
        "Lifebuoy Soap pack of 4",
        "Sabun Mandi Lifebuoy isi 4",
        "Household",
        "Front shelf",
        14,
        4,
        13500,
        16000,
        "pack",
        "Bath soap.",
        "Sabun mandi.",
    ),
    (
        "DTRG-1",
        "Rinso Detergent 800 g",
        "Deterjen Rinso 800 g",
        "Household",
        "Back store",
        12,
        3,
        18500,
        23000,
        "pack",
        "Laundry powder.",
        "Deterjen bubuk.",
    ),
    (
        "MLK-1L",
        "Ultra Milk 1 L",
        "Susu Ultra Milk 1 L",
        "Dairy",
        "Cooler",
        28,
        8,
        15500,
        18500,
        "ctn",
        "UHT milk.",
        "Susu UHT.",
    ),
]


def seed_if_empty(db: Session) -> None:
    settings = db.get(ShopSettings, 1)
    if settings is None:
        db.add(
            ShopSettings(
                id=1,
                name="Warung Pojok",
                address="Jl. Malioboro No. 12, Yogyakarta",
                phone="+62 274-555-0142",
                tax_rate_bps=0,
                currency_symbol="Rp",
                currency_code="IDR",
                invoice_prefix="INV",
                next_invoice_seq=1,
                po_prefix="PO",
                next_po_seq=1,
            )
        )
        db.flush()
    else:
        settings.currency_symbol = "Rp"
        settings.currency_code = "IDR"
        if settings.name in ("The Corner Shop", "Corner Shop", "My Shop"):
            settings.name = "Warung Pojok"
            settings.address = "Jl. Malioboro No. 12, Yogyakarta"
            settings.phone = "+62 274-555-0142"

    if db.scalar(select(func.count()).select_from(Category)) == 0:
        now = utcnow()
        cats = {}
        for en, idn in SEED_CATEGORIES:
            cats[en] = Category(name=en, name_id=idn, created_at=now)
            db.add(cats[en])
        locs = {}
        for en, idn in SEED_LOCATIONS:
            locs[en] = Location(name=en, name_id=idn, created_at=now)
            db.add(locs[en])
        db.flush()
        for row in SEED_ITEMS:
            sku, name, name_id, cat, loc, qty, reorder, cost, price, unit, desc, desc_id = row
            db.add(
                Item(
                    sku=sku,
                    name=name,
                    name_id=name_id,
                    description=desc,
                    description_id=desc_id,
                    category_id=cats[cat].id,
                    location_id=locs[loc].id,
                    quantity=qty,
                    unit=unit,
                    reorder_point=reorder,
                    unit_cost_cents=idr(cost),
                    unit_price_cents=idr(price),
                    notes="",
                    archived=0,
                    created_at=now,
                    updated_at=now,
                )
            )

    if db.scalar(select(func.count()).select_from(Shopper)) == 0:
        now = utcnow()
        db.add(Shopper(name="Siti Aminah", phone="081234567890", email="siti@example.com", created_at=now))
        db.add(Shopper(name="Budi Santoso", phone="081298765432", email="", created_at=now))

    _backfill_bilingual_idr(db)
    db.commit()


def _backfill_bilingual_idr(db: Session) -> None:
    """Fill Indonesian names and IDR prices on an older (empty name_id) catalog."""
    cat_id = {en: idn for en, idn in SEED_CATEGORIES}
    for cat in db.scalars(select(Category)):
        if not (cat.name_id or "").strip() and cat.name in cat_id:
            cat.name_id = cat_id[cat.name]
    loc_id = {en: idn for en, idn in SEED_LOCATIONS}
    for loc in db.scalars(select(Location)):
        if not (loc.name_id or "").strip() and loc.name in loc_id:
            loc.name_id = loc_id[loc.name]

    seed_by_sku = {row[0]: row for row in SEED_ITEMS}
    for item in db.scalars(select(Item)):
        row = seed_by_sku.get(item.sku)
        if row is None:
            continue
        _sku, name, name_id, _cat, _loc, _qty, _reorder, cost, price, _unit, desc, desc_id = row
        if (item.name_id or "").strip():
            continue
        item.name = name
        item.name_id = name_id
        item.description = desc
        item.description_id = desc_id
        item.unit_cost_cents = idr(cost)
        item.unit_price_cents = idr(price)
