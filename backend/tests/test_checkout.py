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


def test_stock_in_out_adjust(client: TestClient):
    items = client.get("/api/items").json()
    item = next(i for i in items if i["sku"] == "SLT-1KG")
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
    item = next(i for i in items if i["sku"] == "SLT-1KG")
    res = client.post(
        f"/api/items/{item['id']}/movements",
        json={"kind": "out", "quantity": item["quantity"] + 10, "reason": "Too much"},
    )
    assert res.status_code == 409


def test_place_order_adjusts_stock_and_raises_invoice(client: TestClient):
    items = client.get("/api/shop/catalog").json()
    atta = next(i for i in items if i["sku"] == "ATA-5KG")
    oil = next(i for i in items if i["sku"] == "OIL-1L")
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
    assert body["invoice"]["status"] == "issued"
    assert body["invoice"]["number"].startswith("INV-")
    expected = 2 * atta["unit_price_cents"] + 1 * oil["unit_price_cents"]
    assert body["invoice"]["subtotal_cents"] == expected
    assert body["invoice"]["total_cents"] == expected

    catalog = {i["sku"]: i for i in client.get("/api/shop/catalog").json()}
    assert catalog["ATA-5KG"]["quantity"] == atta_qty - 2
    assert catalog["OIL-1L"]["quantity"] == oil_qty - 1

    moves = client.get(f"/api/items/{atta['id']}/movements").json()
    assert any(m["kind"] == "out" and m["quantity_delta"] == -2 and m["invoice_id"] for m in moves)


def test_place_rejects_shortage_and_does_not_write_invoice(client: TestClient):
    items = client.get("/api/shop/catalog").json()
    atta = next(i for i in items if i["sku"] == "ATA-5KG")
    client.post("/api/shop/session", json={"name": "Hungry", "phone": "9000000002"})
    res = client.post("/api/shop/po/lines", json={"item_id": atta["id"], "quantity": atta["quantity"] + 5})
    assert res.status_code == 409
    client.post("/api/shop/po/lines", json={"item_id": atta["id"], "quantity": atta["quantity"]})
    # deplete via operator shrink so placement fails
    client.post(
        f"/api/items/{atta['id']}/movements",
        json={"kind": "out", "quantity": 1, "reason": "Shrink"},
    )
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
    salt = next(i for i in items if i["sku"] == "SLT-1KG")
    start = salt["quantity"]
    client.post("/api/shop/session", json={"name": "Cancel Me", "phone": "9000000004"})
    client.post("/api/shop/po/lines", json={"item_id": salt["id"], "quantity": 4})
    placed = client.post("/api/shop/po/place", json={"note": ""}).json()
    assert next(i for i in client.get("/api/items").json() if i["id"] == salt["id"])["quantity"] == start - 4
    cancelled = client.post(f"/api/orders/{placed['id']}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()
    assert body["status"] == "cancelled"
    assert body["invoice"]["status"] == "void"
    assert next(i for i in client.get("/api/items").json() if i["id"] == salt["id"])["quantity"] == start


def test_second_place_fails_when_stock_gone(client: TestClient):
    items = client.get("/api/shop/catalog").json()
    tea = next(i for i in items if i["sku"] == "TEA-250")
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
    soap = next(i for i in items if i["sku"] == "SOAP-4")
    client.post("/api/shop/session", json={"name": "Payer", "phone": "9000000013"})
    client.post("/api/shop/po/lines", json={"item_id": soap["id"], "quantity": 1})
    placed = client.post("/api/shop/po/place", json={"note": ""}).json()
    inv_id = placed["invoice"]["id"]
    res = client.post(f"/api/invoices/{inv_id}/mark-paid")
    assert res.status_code == 200
    assert res.json()["status"] == "paid"
    cancel = client.post(f"/api/orders/{placed['id']}/cancel")
    assert cancel.status_code == 400


def test_indonesian_rupiah_and_bilingual_catalog(client: TestClient):
    settings = client.get("/api/settings").json()
    assert settings["currency_symbol"] == "Rp"
    assert settings["currency_code"] == "IDR"
    health = client.get("/api/health").json()
    assert health["currency_code"] == "IDR"
    items = client.get("/api/shop/catalog").json()
    rice = next(i for i in items if i["sku"] == "ATA-5KG")
    assert rice["name_id"]
    assert rice["name_id"] != rice["name"]
    assert rice["unit_price_cents"] == 78000 * 100
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
