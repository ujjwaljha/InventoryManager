from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Item, Location, ShopSettings, Shopper
from app.services.stock import apply_movement, backfill_opening_lots
from app.timeutil import utcnow


def idr(rupiah: int) -> int:
    """Store whole rupiah as integer sen (1/100), matching the cents fields."""
    return rupiah * 100


SEED_CATEGORIES = [
    ("Cement & concrete", "Semen & beton"),
    ("Steel", "Besi"),
    ("Wood", "Kayu"),
    ("Paint", "Cat"),
    ("Plumbing", "Pipa & plumbing"),
    ("Electrical", "Listrik"),
    ("Hardware", "Perkakas"),
    ("Roofing", "Atap"),
    ("Flooring", "Lantai"),
]
SEED_LOCATIONS = [
    ("Yard", "Halaman"),
    ("Warehouse", "Gudang"),
    ("Front counter", "Etalase"),
]

# sku, name_en, name_id, category, location, qty, reorder, cost_idr, price_idr, unit, desc_en, desc_id
SEED_ITEMS = [
    (
        "CEM-50",
        "Portland cement 50 kg",
        "Semen Portland 50 kg",
        "Cement & concrete",
        "Warehouse",
        48,
        10,
        52000,
        65000,
        "bag",
        "One sack of grey Portland cement.",
        "Satu sak semen Portland abu-abu.",
    ),
    (
        "SND-M3",
        "River sand (m³)",
        "Pasir sungai (m³)",
        "Cement & concrete",
        "Yard",
        20,
        4,
        280000,
        350000,
        "m3",
        "Bulk river sand sold by the cubic metre.",
        "Pasir sungai curah per meter kubik.",
    ),
    (
        "RBR-10",
        "Rebar 10 mm (stick)",
        "Besi beton 10 mm (batang)",
        "Steel",
        "Yard",
        80,
        20,
        28000,
        35000,
        "stick",
        "Deformed steel bar 10 millimetres.",
        "Besi beton ulir 10 milimeter.",
    ),
    (
        "RBR-12",
        "Rebar 12 mm (stick)",
        "Besi beton 12 mm (batang)",
        "Steel",
        "Yard",
        60,
        16,
        42000,
        52000,
        "stick",
        "Deformed steel bar 12 millimetres.",
        "Besi beton ulir 12 milimeter.",
    ),
    (
        "WD-2X4",
        "Meranti 2x4 timber 4 m",
        "Kayu meranti 2x4 4 m",
        "Wood",
        "Warehouse",
        36,
        8,
        38000,
        48000,
        "pcs",
        "Rough meranti stud.",
        "Kayu meranti kasar.",
    ),
    (
        "PNT-5L",
        "Interior wall paint 5 L",
        "Cat tembok interior 5 L",
        "Paint",
        "Front counter",
        24,
        6,
        85000,
        110000,
        "pail",
        "White interior emulsion.",
        "Cat emulsi interior putih.",
    ),
    (
        "PVC-4",
        "PVC pipe 4 in × 4 m",
        "Pipa PVC 4 in × 4 m",
        "Plumbing",
        "Warehouse",
        40,
        10,
        45000,
        58000,
        "pcs",
        "AW PVC pipe for waste water.",
        "Pipa PVC AW untuk air kotor.",
    ),
    (
        "NAL-1",
        "Wire nails 1 kg",
        "Paku duri 1 kg",
        "Hardware",
        "Front counter",
        50,
        12,
        14000,
        18000,
        "kg",
        "Mixed common nails.",
        "Paku campuran.",
    ),
    (
        "WIR-2.5",
        "NYM cable 2×2.5 mm (m)",
        "Kabel NYM 2×2.5 mm (m)",
        "Electrical",
        "Front counter",
        200,
        40,
        6500,
        8500,
        "m",
        "Sold by the metre.",
        "Dijual per meter.",
    ),
    (
        "TLE-30",
        "Ceramic tile 30×30 (box)",
        "Keramik 30×30 (dus)",
        "Flooring",
        "Warehouse",
        30,
        8,
        72000,
        95000,
        "box",
        "Glazed floor tile, 11 pieces per box.",
        "Keramik lantai mengkilap, 11 pcs per dus.",
    ),
    (
        "ROF-ZN",
        "Zinc roof sheet 0.3 mm",
        "Seng atap 0.3 mm",
        "Roofing",
        "Yard",
        25,
        6,
        48000,
        62000,
        "sheet",
        "Corrugated galvanised sheet.",
        "Seng gelombang galvanis.",
    ),
    (
        "HAM-1",
        "Claw hammer 16 oz",
        "Palu cakar 16 oz",
        "Hardware",
        "Front counter",
        14,
        4,
        35000,
        48000,
        "pcs",
        "Steel head with wooden handle.",
        "Kepala baja gagang kayu.",
    ),
]


def seed_if_empty(db: Session) -> None:
    settings = db.get(ShopSettings, 1)
    if settings is None:
        db.add(
            ShopSettings(
                id=1,
                name="Toko Bangunan Makmur",
                address="Jl. Magelang Km. 5, Yogyakarta",
                phone="+62 274-555-2210",
                tax_rate_bps=0,
                currency_symbol="Rp",
                currency_code="IDR",
                invoice_prefix="INV",
                next_invoice_seq=1,
                po_prefix="PO",
                next_po_seq=1,
                restock_prefix="RST",
                next_restock_seq=1,
                damage_prefix="DMG",
                next_damage_seq=1,
                return_prefix="RTN",
                next_return_seq=1,
            )
        )
        db.flush()
    else:
        settings.currency_symbol = "Rp"
        settings.currency_code = "IDR"
        if settings.name in ("The Corner Shop", "Corner Shop", "My Shop"):
            settings.name = "Toko Bangunan Makmur"
            settings.address = "Jl. Magelang Km. 5, Yogyakarta"
            settings.phone = "+62 274-555-2210"

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
            item = Item(
                sku=sku,
                name=name,
                name_id=name_id,
                description=desc,
                description_id=desc_id,
                category_id=cats[cat].id,
                location_id=locs[loc].id,
                quantity=0,
                unit=unit,
                reorder_point=reorder,
                unit_cost_cents=idr(cost),
                unit_price_cents=idr(price),
                notes="",
                archived=0,
                created_at=now,
                updated_at=now,
            )
            db.add(item)
            db.flush()
            if qty > 0:
                apply_movement(
                    db,
                    item_id=item.id,
                    kind="in",
                    quantity=qty,
                    reason="Opening stock",
                    purpose="opening",
                    unit_cost_cents=idr(cost),
                )

    if db.scalar(select(func.count()).select_from(Shopper)) == 0:
        now = utcnow()
        db.add(Shopper(name="Siti Aminah", phone="081234567890", email="siti@example.com", created_at=now))
        db.add(Shopper(name="Budi Santoso", phone="081298765432", email="", created_at=now))

    backfill_opening_lots(db)
    db.commit()
