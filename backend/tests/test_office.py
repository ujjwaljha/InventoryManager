from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db = tmp_path / "office.db"
    app = create_app(f"sqlite:///{db}")
    return TestClient(app)


def _item(client: TestClient, sku: str) -> dict:
    return next(i for i in client.get("/api/items").json() if i["sku"] == sku)


def test_opening_lots_match_on_hand(client: TestClient):
    nails = _item(client, "NAL-1")
    lots = client.get(f"/api/items/{nails['id']}/lots").json()
    remaining = sum(lot["qty_remaining"] for lot in lots)
    assert remaining == nails["quantity"]
    assert nails["fifo_cogs_cents"] == nails["unit_cost_cents"]
    assert nails["inventory_value_cents"] == nails["fifo_cogs_cents"] * nails["quantity"]


def test_fifo_restock_then_sale_uses_oldest_cost(client: TestClient):
    nails = _item(client, "NAL-1")
    start_qty = nails["quantity"]
    first_cost = nails["unit_cost_cents"]
    later_cost = 25000 * 100
    sell = nails["unit_price_cents"]

    restock = client.post(
        "/api/restocks",
        json={"supplier_name": "CV Baja Jaya", "supplier_phone": "0274555001"},
    ).json()
    add = client.post(
        f"/api/restocks/{restock['id']}/lines",
        json={"item_id": nails["id"], "quantity": 10, "unit_cost_cents": later_cost},
    )
    assert add.status_code == 200, add.text
    received = client.post(f"/api/restocks/{restock['id']}/receive")
    assert received.status_code == 200, received.text
    after = _item(client, "NAL-1")
    assert after["quantity"] == start_qty + 10
    assert after["unit_cost_cents"] == later_cost

    sale_qty = start_qty + 2
    sale = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Andi",
            "customer_name": "Pak Joko",
            "customer_phone": "081300000111",
            "lines": [{"item_id": nails["id"], "quantity": sale_qty}],
        },
    )
    assert sale.status_code == 200, sale.text
    body = sale.json()
    assert body["salesperson_name"] == "Andi"
    assert body["shopper_name"] == "Pak Joko"
    assert body["shopper_phone"] == "081300000111"
    expected_cogs = start_qty * first_cost + 2 * later_cost
    assert body["cogs_cents"] == expected_cogs
    assert body["lines"][0]["cogs_cents"] == expected_cogs
    assert body["subtotal_cents"] == sale_qty * sell
    leftover = _item(client, "NAL-1")
    assert leftover["quantity"] == 8
    assert leftover["fifo_cogs_cents"] == later_cost


def test_receipt_search_by_number_and_phone(client: TestClient):
    nails = _item(client, "NAL-1")
    sale = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Rina",
            "customer_name": "Bu Ani",
            "customer_phone": "081355512345",
            "lines": [{"item_id": nails["id"], "quantity": 1}],
        },
    ).json()
    number = sale["number"]
    by_number = client.get("/api/receipts", params={"q": number}).json()
    assert any(r["number"] == number for r in by_number)
    by_phone = client.get("/api/invoices", params={"q": "081355512345"}).json()
    assert any(r["number"] == number for r in by_phone)
    by_partial = client.get("/api/receipts", params={"q": "555123"}).json()
    assert any(r["number"] == number for r in by_partial)


def test_damage_and_supplier_return_update_stock_and_ledger(client: TestClient):
    cement = _item(client, "CEM-50")
    start = cement["quantity"]
    dmg = client.post(
        "/api/damage",
        json={
            "reason": "Broken bags from forklift",
            "lines": [{"item_id": cement["id"], "quantity": 3}],
        },
    )
    assert dmg.status_code == 200, dmg.text
    assert _item(client, "CEM-50")["quantity"] == start - 3
    assert dmg.json()["cogs_cents"] == 3 * cement["fifo_cogs_cents"]

    ret = client.post(
        "/api/supplier-returns",
        json={
            "reason": "Wrong grade delivered",
            "supplier_name": "Semen Gresik",
            "lines": [{"item_id": cement["id"], "quantity": 2}],
        },
    )
    assert ret.status_code == 200, ret.text
    assert _item(client, "CEM-50")["quantity"] == start - 5
    ledger = client.get("/api/reports/ledger", params={"item_id": cement["id"]}).json()
    purposes = {row["purpose"] for row in ledger}
    assert "damage" in purposes
    assert "supplier_return" in purposes


def test_daily_and_item_pnl_and_category(client: TestClient):
    paint = _item(client, "PNT-5L")
    hammer = _item(client, "HAM-1")
    sale = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Dewi",
            "customer_name": "Pak Hasan",
            "customer_phone": "081399900001",
            "lines": [
                {"item_id": paint["id"], "quantity": 2},
                {"item_id": hammer["id"], "quantity": 1},
            ],
        },
    )
    assert sale.status_code == 200, sale.text
    daily = client.get("/api/reports/daily").json()
    assert daily["receipt_count"] >= 1
    assert daily["revenue_cents"] >= sale.json()["total_cents"]
    assert daily["cogs_cents"] > 0
    assert daily["profit_cents"] == daily["revenue_cents"] - daily["cogs_cents"]
    paint_row = next(r for r in daily["items"] if r["sku"] == "PNT-5L")
    assert paint_row["quantity"] == 2
    assert paint_row["margin_bps"] > 0
    cats = client.get("/api/reports/categories").json()
    names = {c["name"] for c in cats["categories"]}
    assert "Paint" in names
    assert "Hardware" in names
    stock = client.get("/api/reports/stock").json()
    assert stock["inventory_value_cents"] > 0
    cem = next(i for i in stock["items"] if i["sku"] == "CEM-50")
    assert cem["category_name"] == "Cement & concrete"


def test_cancel_restores_original_fifo_layers(client: TestClient):
    rebar = _item(client, "RBR-10")
    start = rebar["quantity"]
    first_cost = rebar["fifo_cogs_cents"]
    later = 40000 * 100
    rst = client.post("/api/restocks", json={"supplier_name": "PT Besi"}).json()
    client.post(
        f"/api/restocks/{rst['id']}/lines",
        json={"item_id": rebar["id"], "quantity": 5, "unit_cost_cents": later},
    )
    client.post(f"/api/restocks/{rst['id']}/receive")
    sale = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Andi",
            "customer_name": "Cancel FIFO",
            "customer_phone": "081300000222",
            "lines": [{"item_id": rebar["id"], "quantity": start + 1}],
        },
    ).json()
    cancelled = client.post(f"/api/orders/{sale['purchase_order_id']}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    restored = _item(client, "RBR-10")
    assert restored["quantity"] == start + 5
    lots = client.get(f"/api/items/{rebar['id']}/lots").json()
    remaining = {lot["unit_cost_cents"]: lot["qty_remaining"] for lot in lots if lot["qty_remaining"]}
    assert remaining[first_cost] == start
    assert remaining[later] == 5
