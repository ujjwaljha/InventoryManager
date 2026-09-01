from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db = tmp_path / "test.db"
    app = create_app(f"sqlite:///{db}")
    return TestClient(app)


def test_health(client: TestClient):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_shop_timezone_is_wib():
    from datetime import datetime, timezone

    from app.timeutil import SHOP_TZ

    noon_utc = datetime(2026, 6, 1, 5, 0, tzinfo=timezone.utc)
    local = noon_utc.astimezone(SHOP_TZ)
    assert local.hour == 12
    assert local.utcoffset().total_seconds() == 7 * 3600


def test_stock_in_out_adjust(client: TestClient):
    items = client.get("/api/items").json()
    item = next(i for i in items if i["sku"] == "NAL-1")
    start = item["quantity"]
    res = client.post(f"/api/items/{item['id']}/movements", json={"kind": "in", "quantity": 5, "reason": "Delivery"})
    assert res.status_code == 200
    assert res.json()["quantity_after"] == start + 5
    res = client.post(f"/api/items/{item['id']}/movements", json={"kind": "out", "quantity": 2, "reason": "Breakage"})
    assert res.status_code == 200
    assert res.json()["quantity_after"] == start + 3
    res = client.post(f"/api/items/{item['id']}/movements", json={"kind": "adjust", "quantity": 7, "reason": "Count"})
    assert res.status_code == 200
    assert res.json()["quantity_after"] == 7


def test_stock_out_rejects_negative(client: TestClient):
    items = client.get("/api/items").json()
    item = next(i for i in items if i["sku"] == "NAL-1")
    res = client.post(
        f"/api/items/{item['id']}/movements",
        json={"kind": "out", "quantity": item["quantity"] + 10, "reason": "Too much"},
    )
    assert res.status_code == 409


def test_place_order_adjusts_stock_and_raises_invoice(client: TestClient):
    items = client.get("/api/shop/catalog").json()
    atta = next(i for i in items if i["sku"] == "CEM-50")
    oil = next(i for i in items if i["sku"] == "PNT-5L")
    atta_qty = atta["quantity"]
    oil_qty = oil["quantity"]

    session = client.post("/api/shop/session", json={"name": "Test Buyer", "phone": "9000000001"})
    assert session.status_code == 200

    client.post("/api/shop/po/lines", json={"item_id": atta["id"], "quantity": 2})
    po = client.post("/api/shop/po/lines", json={"item_id": oil["id"], "quantity": 1}).json()
    assert po["status"] == "draft"
    assert len(po["lines"]) == 2

    placed = client.post("/api/shop/po/place", json={"note": "Please pack well"})
    assert placed.status_code == 200, placed.text
    body = placed.json()
    assert body["status"] == "placed"
    assert body["invoice"] is not None
    assert body["invoice"]["status"] == "paid"
    assert body["invoice"]["number"].startswith("INV-")
    expected = 2 * atta["unit_price_cents"] + 1 * oil["unit_price_cents"]
    assert body["invoice"]["subtotal_cents"] == expected
    assert body["invoice"]["total_cents"] == expected

    catalog = {i["sku"]: i for i in client.get("/api/shop/catalog").json()}
    assert catalog["CEM-50"]["quantity"] == atta_qty - 2
    assert catalog["PNT-5L"]["quantity"] == oil_qty - 1

    moves = client.get(f"/api/items/{atta['id']}/movements").json()
    assert any(m["kind"] == "out" and m["quantity_delta"] == -2 and m["invoice_id"] for m in moves)


def test_place_rejects_shortage_and_does_not_write_invoice(client: TestClient):
    items = client.get("/api/shop/catalog").json()
    atta = next(i for i in items if i["sku"] == "CEM-50")
    client.post("/api/shop/session", json={"name": "Hungry", "phone": "9000000002"})
    res = client.post("/api/shop/po/lines", json={"item_id": atta["id"], "quantity": atta["quantity"] + 5})
    assert res.status_code == 409
    held = client.post("/api/shop/po/lines", json={"item_id": atta["id"], "quantity": atta["quantity"]})
    assert held.status_code == 200, held.text
    shrink = client.post(
        f"/api/items/{atta['id']}/movements",
        json={"kind": "out", "quantity": 1, "reason": "Shrink"},
    )
    assert shrink.status_code == 409, shrink.text
    from app.models import Item
    from app.qty import to_store

    db = client.app.state.SessionLocal()
    row = db.get(Item, atta["id"])
    assert row is not None
    row.quantity -= to_store(1)
    db.commit()
    db.close()
    placed = client.post("/api/shop/po/place", json={"note": ""})
    assert placed.status_code == 409
    detail = placed.json()["detail"]
    assert detail["shortages"]
    invoices = client.get("/api/shop/invoices").json()
    assert invoices == []
    leftover = next(i for i in client.get("/api/shop/catalog").json() if i["id"] == atta["id"])
    assert leftover["quantity"] == atta["quantity"] - 1


def test_empty_po_cannot_place(client: TestClient):
    client.post("/api/shop/session", json={"name": "Empty", "phone": "9000000003"})
    client.get("/api/shop/po")
    res = client.post("/api/shop/po/place", json={"note": ""})
    assert res.status_code == 400


def test_cancel_restores_stock_and_voids_invoice(client: TestClient):
    items = client.get("/api/shop/catalog").json()
    salt = next(i for i in items if i["sku"] == "NAL-1")
    start = salt["quantity"]
    client.post("/api/shop/session", json={"name": "Cancel Me", "phone": "9000000004"})
    client.post("/api/shop/po/lines", json={"item_id": salt["id"], "quantity": 4})
    placed = client.post("/api/shop/po/place", json={"note": "", "paid": False}).json()
    assert next(i for i in client.get("/api/items").json() if i["id"] == salt["id"])["quantity"] == start - 4
    cancelled = client.post(f"/api/orders/{placed['id']}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()
    assert body["status"] == "cancelled"
    assert body["invoice"]["status"] == "void"
    assert next(i for i in client.get("/api/items").json() if i["id"] == salt["id"])["quantity"] == start


def test_second_place_fails_when_stock_gone(client: TestClient):
    items = client.get("/api/shop/catalog").json()
    tea = next(i for i in items if i["sku"] == "PVC-4")
    # first shopper buys all
    client.post("/api/shop/session", json={"name": "A", "phone": "9000000011"})
    client.post("/api/shop/po/lines", json={"item_id": tea["id"], "quantity": tea["quantity"]})
    first = client.post("/api/shop/po/place", json={"note": ""})
    assert first.status_code == 200
    # second shopper
    client.post("/api/shop/session", json={"name": "B", "phone": "9000000012"})
    add = client.post("/api/shop/po/lines", json={"item_id": tea["id"], "quantity": 1})
    assert add.status_code == 409


def test_mark_paid(client: TestClient):
    items = client.get("/api/shop/catalog").json()
    soap = next(i for i in items if i["sku"] == "HAM-1")
    client.post("/api/shop/session", json={"name": "Payer", "phone": "9000000013"})
    client.post("/api/shop/po/lines", json={"item_id": soap["id"], "quantity": 1})
    placed = client.post("/api/shop/po/place", json={"note": "", "paid": False}).json()
    inv_id = placed["invoice"]["id"]
    res = client.post(f"/api/invoices/{inv_id}/mark-paid")
    assert res.status_code == 200
    assert res.json()["status"] == "paid"
    cancel = client.post(f"/api/orders/{placed['id']}/cancel")
    assert cancel.status_code == 400
    unpaid = client.post(f"/api/invoices/{inv_id}/unpay")
    assert unpaid.status_code == 200, unpaid.text
    assert unpaid.json()["status"] == "issued"
    assert unpaid.json()["paid_at"] is None
    credit = client.get("/api/credit").json()
    assert any(row["id"] == inv_id for row in credit["invoices"])
    cancelled = client.post(f"/api/orders/{placed['id']}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"


def test_indonesian_rupiah_and_bilingual_catalog(client: TestClient):
    settings = client.get("/api/settings").json()
    assert settings["currency_symbol"] == "Rp"
    assert settings["currency_code"] == "IDR"
    assert settings["shop_today"]
    health = client.get("/api/health").json()
    assert health["currency_code"] == "IDR"
    items = client.get("/api/shop/catalog").json()
    rice = next(i for i in items if i["sku"] == "CEM-50")
    assert rice["name_id"]
    assert rice["name_id"] != rice["name"]
    assert rice["unit_price_cents"] == 65000 * 100
    assert rice["category_name_id"]
    invoice = client.post("/api/shop/session", json={"name": "Sari", "phone": "081200000099"})
    assert invoice.status_code == 200
    client.post("/api/shop/po/lines", json={"item_id": rice["id"], "quantity": 1})
    placed = client.post("/api/shop/po/place", json={"note": ""}).json()
    assert placed["invoice"]["currency_symbol"] == "Rp"
    assert placed["invoice"]["currency_code"] == "IDR"
    assert placed["invoice"]["lines"][0]["name_id"]
    locked = client.patch("/api/settings", json={"currency_symbol": "$", "currency_code": "USD"}).json()
    assert locked["currency_symbol"] == "Rp"
    assert locked["currency_code"] == "IDR"


def test_fractional_sand_sale(client: TestClient):
    items = client.get("/api/shop/catalog").json()
    sand = next(i for i in items if i["sku"] == "SND-M3")
    start = sand["quantity"]
    assert start >= 0.5
    session = client.post("/api/shop/session", json={"name": "Tukang Budi", "phone": "081355500001"})
    assert session.status_code == 200
    added = client.post("/api/shop/po/lines", json={"item_id": sand["id"], "quantity": 0.5})
    assert added.status_code == 200, added.text
    line = added.json()["lines"][0]
    assert line["quantity"] == 0.5
    assert line["line_total_cents"] == int(0.5 * sand["unit_price_cents"])
    placed = client.post("/api/shop/po/place", json={"note": "Setengah kubik"})
    assert placed.status_code == 200, placed.text
    leftover = next(i for i in client.get("/api/shop/catalog").json() if i["sku"] == "SND-M3")
    assert leftover["quantity"] == start - 0.5
    assert placed.json()["invoice"]["lines"][0]["unit"] == "m3"


def test_shop_add_increments_existing_line(client: TestClient):
    items = client.get("/api/shop/catalog").json()
    nails = next(i for i in items if i["sku"] == "NAL-1")
    client.post("/api/shop/session", json={"name": "Bu Ani", "phone": "081366600002"})
    first = client.post(
        "/api/shop/po/lines",
        json={"item_id": nails["id"], "quantity": 1, "increment": True},
    )
    second = client.post(
        "/api/shop/po/lines",
        json={"item_id": nails["id"], "quantity": 1, "increment": True},
    )
    assert second.status_code == 200, second.text
    line = second.json()["lines"][0]
    assert line["quantity"] == first.json()["lines"][0]["quantity"] + 1
    assert line["quantity"] == 2


def test_credit_lists_issued_and_till_can_mark_paid(client: TestClient):
    nails = next(i for i in client.get("/api/items").json() if i["sku"] == "NAL-1")
    unpaid = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Andi",
            "customer_name": "Pak Darma",
            "customer_phone": "081377700003",
            "lines": [{"item_id": nails["id"], "quantity": 1}],
            "paid": False,
        },
    )
    assert unpaid.status_code == 200, unpaid.text
    assert unpaid.json()["status"] == "issued"
    paid = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Andi",
            "customer_name": "Bu Sari",
            "customer_phone": "081377700004",
            "lines": [{"item_id": nails["id"], "quantity": 1}],
            "paid": True,
        },
    )
    assert paid.json()["status"] == "paid"
    credit = client.get("/api/credit").json()
    assert credit["invoice_count"] >= 1
    phones = {c["shopper_phone"] for c in credit["customers"]}
    assert "081377700003" in phones
    assert "081377700004" not in phones
    dash = client.get("/api/dashboard").json()
    assert dash["unpaid_count"] >= 1
    assert dash["unpaid_cents"] >= unpaid.json()["total_cents"]
    assert "aging_cents" in credit
    buckets = credit["aging_cents"]
    assert buckets["d0_30"] + buckets["d31_60"] + buckets["d61_90"] + buckets["d90_plus"] == credit["unpaid_cents"]


def test_lan_qr(client: TestClient):
    res = client.get("/api/lan/qr")
    assert res.status_code == 200
    assert b"<svg" in res.content.lower()


def test_backup_restore_roundtrip(client: TestClient):
    blob = client.get("/api/backup").content
    assert blob.startswith(b"SQLite format 3")
    bad = client.post("/api/backup/restore", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert bad.status_code == 400
    name = client.get("/api/settings").json()["name"]
    ok = client.post("/api/backup/restore", files={"file": ("inventory.db", blob, "application/octet-stream")})
    assert ok.status_code == 200, ok.text
    assert client.get("/api/settings").json()["name"] == name
    assert client.get("/api/shop/catalog").status_code == 200


def test_shop_place_can_mark_paid(client: TestClient):
    nails = next(i for i in client.get("/api/shop/catalog").json() if i["sku"] == "NAL-1")
    client.post("/api/shop/session", json={"name": "Bu Lestari", "phone": "081388800021"})
    client.post("/api/shop/po/lines", json={"item_id": nails["id"], "quantity": 1})
    placed = client.post("/api/shop/po/place", json={"note": "", "paid": True})
    assert placed.status_code == 200, placed.text
    assert placed.json()["invoice"]["status"] == "paid"
    credit = client.get("/api/credit").json()
    phones = {c["shopper_phone"] for c in credit["customers"]}
    assert "081388800021" not in phones


def test_draft_holds_stock_from_other_shoppers(client: TestClient):
    tea = next(i for i in client.get("/api/shop/catalog").json() if i["sku"] == "PVC-4")
    client.post("/api/shop/session", json={"name": "A", "phone": "9000000041"})
    held = client.post("/api/shop/po/lines", json={"item_id": tea["id"], "quantity": tea["quantity"]})
    assert held.status_code == 200, held.text
    catalog = next(i for i in client.get("/api/shop/catalog").json() if i["id"] == tea["id"])
    assert catalog["available"] == 0
    client.post("/api/shop/session", json={"name": "B", "phone": "9000000042"})
    blocked = client.post("/api/shop/po/lines", json={"item_id": tea["id"], "quantity": 1})
    assert blocked.status_code == 409


def test_logout_abandons_draft_and_frees_stock(client: TestClient):
    nails = next(i for i in client.get("/api/shop/catalog").json() if i["sku"] == "NAL-1")
    start = nails["available"]
    client.post("/api/shop/session", json={"name": "Hold", "phone": "9000000043"})
    client.post("/api/shop/po/lines", json={"item_id": nails["id"], "quantity": 3})
    after_hold = next(i for i in client.get("/api/shop/catalog").json() if i["id"] == nails["id"])
    assert after_hold["available"] == start - 3
    client.post("/api/shop/logout")
    freed = next(i for i in client.get("/api/shop/catalog").json() if i["id"] == nails["id"])
    assert freed["available"] == start
    client.post("/api/shop/session", json={"name": "Hold", "phone": "9000000043"})
    po = client.get("/api/shop/po").json()
    assert po["lines"] == []


def test_logout_keep_cart_restores_lines(client: TestClient):
    nails = next(i for i in client.get("/api/shop/catalog").json() if i["sku"] == "NAL-1")
    start = nails["available"]
    client.post("/api/shop/session", json={"name": "Keep", "phone": "9000000047"})
    client.post("/api/shop/po/lines", json={"item_id": nails["id"], "quantity": 2})
    client.post("/api/shop/logout?keep_cart=true")
    held = next(i for i in client.get("/api/shop/catalog").json() if i["id"] == nails["id"])
    assert held["available"] == start - 2
    client.post("/api/shop/session", json={"name": "Keep", "phone": "9000000047"})
    po = client.get("/api/shop/po").json()
    assert len(po["lines"]) == 1
    assert po["lines"][0]["quantity"] == 2
    emptied = client.post("/api/shop/po/abandon")
    assert emptied.status_code == 200, emptied.text
    assert emptied.json()["lines"] == []
    freed = next(i for i in client.get("/api/shop/catalog").json() if i["id"] == nails["id"])
    assert freed["available"] == start


def test_shop_invoice_mark_paid_and_cancel(client: TestClient):
    nails = next(i for i in client.get("/api/shop/catalog").json() if i["sku"] == "NAL-1")
    start = nails["quantity"]
    client.post("/api/shop/session", json={"name": "Shop Inv", "phone": "9000000044"})
    client.post("/api/shop/po/lines", json={"item_id": nails["id"], "quantity": 1})
    placed = client.post("/api/shop/po/place", json={"note": "", "paid": False}).json()
    inv_id = placed["invoice"]["id"]
    paid = client.post(f"/api/shop/invoices/{inv_id}/mark-paid")
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    blocked = client.post(f"/api/shop/invoices/{inv_id}/cancel")
    assert blocked.status_code == 400
    other = TestClient(client.app)
    other.post("/api/shop/session", json={"name": "Other", "phone": "9000000045"})
    stolen = other.post(f"/api/shop/invoices/{inv_id}/unpay")
    assert stolen.status_code == 404
    unpaid = client.post(f"/api/shop/invoices/{inv_id}/unpay")
    assert unpaid.status_code == 200, unpaid.text
    assert unpaid.json()["status"] == "issued"
    cancelled = client.post(f"/api/shop/invoices/{inv_id}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "void"
    leftover = next(i for i in client.get("/api/items").json() if i["id"] == nails["id"])
    assert leftover["quantity"] == start


def test_shop_orders_lists_placed_po(client: TestClient):
    nails = next(i for i in client.get("/api/shop/catalog").json() if i["sku"] == "NAL-1")
    client.post("/api/shop/session", json={"name": "Orders", "phone": "9000000046"})
    client.post("/api/shop/po/lines", json={"item_id": nails["id"], "quantity": 1})
    placed = client.post("/api/shop/po/place", json={"note": "", "paid": True})
    assert placed.status_code == 200, placed.text
    orders = client.get("/api/shop/orders")
    assert orders.status_code == 200
    assert any(row["id"] == placed.json()["id"] for row in orders.json())


def test_shop_po_survives_second_open_draft(client: TestClient):
    nails = next(i for i in client.get("/api/shop/catalog").json() if i["sku"] == "NAL-1")
    client.post("/api/shop/session", json={"name": "Pak Joko", "phone": "081388800022"})
    added = client.post("/api/shop/po/lines", json={"item_id": nails["id"], "quantity": 2})
    assert added.status_code == 200
    shopper_id = added.json()["shopper_id"]
    from app.services import checkout as chk

    db = client.app.state.SessionLocal()
    try:
        extra = chk.create_fresh_draft(db, shopper_id)
        extra.note = "orphan till draft"
        db.commit()
    finally:
        db.close()
    po = client.get("/api/shop/po")
    assert po.status_code == 200, po.text
    body = po.json()
    assert body["status"] == "draft"
    assert len(body["lines"]) == 1
    assert body["lines"][0]["quantity"] == 2
