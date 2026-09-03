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
    assert daily["cash_cents"] + daily["credit_cents"] == daily["revenue_cents"]
    assert any(p["name"] == "Dewi" for p in daily["salespeople"])
    assert any(c["phone"] == "081399900001" for c in daily["customers"])
    cats = client.get("/api/reports/categories").json()
    names = {c["name"] for c in cats["categories"]}
    assert "Paint" in names
    assert "Hardware" in names
    stock = client.get("/api/reports/stock").json()
    assert stock["inventory_value_cents"] > 0
    cem = next(i for i in stock["items"] if i["sku"] == "CEM-50")
    assert cem["category_name"] == "Cement & concrete"


def test_sales_report_splits_cash_and_credit(client: TestClient):
    nails = _item(client, "NAL-1")
    cash_sale = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Dewi",
            "customer_name": "Bu Sari",
            "customer_phone": "081399900010",
            "lines": [{"item_id": nails["id"], "quantity": 1}],
            "paid": True,
        },
    )
    credit_sale = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Dewi",
            "customer_name": "Pak Darma",
            "customer_phone": "081399900011",
            "lines": [{"item_id": nails["id"], "quantity": 1}],
            "paid": False,
        },
    )
    assert cash_sale.status_code == 200, cash_sale.text
    assert credit_sale.status_code == 200, credit_sale.text
    daily = client.get("/api/reports/daily").json()
    cash_total = cash_sale.json()["total_cents"]
    credit_total = credit_sale.json()["total_cents"]
    assert daily["cash_cents"] == cash_total
    assert daily["credit_cents"] == credit_total
    assert daily["paid_count"] == 1
    assert daily["unpaid_count"] == 1
    assert daily["revenue_cents"] == cash_total + credit_total
    pnl = client.get(
        "/api/reports/pnl",
        params={"date_from": daily["date_from"], "date_to": daily["date_to"]},
    ).json()
    assert pnl["cash_cents"] == daily["cash_cents"]
    assert pnl["credit_cents"] == daily["credit_cents"]
    assert daily["collected_cents"] == cash_total
    assert daily["collected_count"] == 1


def test_collected_follows_paid_at_not_issue_day(client: TestClient):
    from datetime import date, timedelta

    from app.models import Invoice
    from app.timeutil import shop_day_bounds, today_shop

    nails = _item(client, "NAL-1")
    sale = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Dewi",
            "customer_name": "Bu Rina",
            "customer_phone": "081399900012",
            "lines": [{"item_id": nails["id"], "quantity": 1}],
            "paid": True,
        },
    )
    assert sale.status_code == 200, sale.text
    total = sale.json()["total_cents"]
    yesterday = (date.fromisoformat(today_shop()) - timedelta(days=1)).isoformat()
    start, _ = shop_day_bounds(yesterday)
    db = client.app.state.SessionLocal()
    try:
        inv = db.get(Invoice, sale.json()["id"])
        assert inv is not None
        inv.issued_at = start
        db.commit()
    finally:
        db.close()
    today = client.get("/api/reports/daily").json()
    assert today["collected_cents"] == total
    assert today["revenue_cents"] == 0
    prior = client.get("/api/reports/daily", params={"date": yesterday}).json()
    assert prior["revenue_cents"] == total
    assert prior["cash_cents"] == total
    assert prior["collected_cents"] == 0


def test_credit_aging_uses_shop_day(client: TestClient):
    from datetime import date, timedelta

    from app.models import Invoice
    from app.timeutil import shop_day_bounds, today_shop

    nails = _item(client, "NAL-1")
    sale = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Dewi",
            "customer_name": "Pak Umar",
            "customer_phone": "081399900020",
            "lines": [{"item_id": nails["id"], "quantity": 1}],
            "paid": False,
        },
    )
    assert sale.status_code == 200, sale.text
    total = sale.json()["total_cents"]
    target = (date.fromisoformat(today_shop()) - timedelta(days=45)).isoformat()
    start, _ = shop_day_bounds(target)
    db = client.app.state.SessionLocal()
    try:
        inv = db.get(Invoice, sale.json()["id"])
        assert inv is not None
        inv.issued_at = start
        inv.due_date = target
        db.commit()
    finally:
        db.close()
    credit = client.get("/api/credit").json()
    assert credit["aging_cents"]["d31_60"] == total
    cust = next(c for c in credit["customers"] if c["shopper_phone"] == "081399900020")
    assert cust["aging_cents"]["d31_60"] == total
    row = next(i for i in credit["invoices"] if i["id"] == sale.json()["id"])
    assert row["age_days"] == 45
    assert row["overdue_days"] == 45
    assert row["due_date"] == target


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


def test_restock_can_remove_draft_line(client: TestClient):
    nails = _item(client, "NAL-1")
    restock = client.post("/api/restocks", json={"supplier_name": "CV Baja"}).json()
    added = client.post(
        f"/api/restocks/{restock['id']}/lines",
        json={"item_id": nails["id"], "quantity": 4, "unit_cost_cents": 1000},
    )
    assert added.status_code == 200, added.text
    assert len(added.json()["lines"]) == 1
    deleted = client.delete(f"/api/restocks/{restock['id']}/lines/{nails['id']}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["lines"] == []


def test_ledger_filters_by_purpose_and_date(client: TestClient):
    cement = _item(client, "CEM-50")
    dmg = client.post(
        "/api/damage",
        json={"reason": "Wet bags", "lines": [{"item_id": cement["id"], "quantity": 1}]},
    )
    assert dmg.status_code == 200, dmg.text
    today = client.get("/api/settings").json()["shop_today"]
    rows = client.get(
        "/api/reports/ledger",
        params={"purpose": "damage", "date_from": today, "date_to": today},
    ).json()
    assert rows
    assert all(row["purpose"] == "damage" for row in rows)
    empty = client.get(
        "/api/reports/ledger",
        params={"date_from": "2000-01-01", "date_to": "2000-01-01"},
    ).json()
    assert empty == []


def test_pnl_subtracts_damage_and_supplier_return(client: TestClient):
    cement = _item(client, "CEM-50")
    cost = cement["fifo_cogs_cents"]
    dmg = client.post(
        "/api/damage",
        json={"reason": "Torn bags", "lines": [{"item_id": cement["id"], "quantity": 2}]},
    )
    assert dmg.status_code == 200, dmg.text
    ret = client.post(
        "/api/supplier-returns",
        json={
            "reason": "Wrong grade",
            "supplier_name": "Semen Gresik",
            "lines": [{"item_id": cement["id"], "quantity": 1}],
        },
    )
    assert ret.status_code == 200, ret.text
    daily = client.get("/api/reports/daily").json()
    assert daily["damage_cents"] == 2 * cost
    assert daily["supplier_return_cents"] == cost
    assert daily["writeoff_cents"] == 3 * cost
    assert daily["adjusted_profit_cents"] == daily["profit_cents"] - daily["writeoff_cents"]
    cement_row = next(r for r in daily["items"] if r["sku"] == "CEM-50")
    assert cement_row["writeoff_cents"] == 3 * cost
    assert cement_row["adjusted_profit_cents"] == cement_row["profit_cents"] - cement_row["writeoff_cents"]
    cat = next(c for c in daily["categories"] if c.get("writeoff_cents") == 3 * cost)
    assert cat["adjusted_profit_cents"] == cat["profit_cents"] - cat["writeoff_cents"]


def test_import_items_csv_creates_and_updates(client: TestClient):
    nails = _item(client, "NAL-1")
    old_qty = nails["quantity"]
    csv_text = (
        "sku,name,name_id,description,description_id,category,location,quantity,unit,"
        "reorder_point,unit_cost_cents,unit_price_cents,archived\n"
        f"NAL-1,Nails 1in,Paku 1in,Imported,Diimpor,Hardware,Rak A,99,pcs,4,{nails['unit_cost_cents']},1234500,0\n"
        "NEW-CSV,New Bit,Mata bor baru,,,Hardware,Rak B,3,pcs,1,50000,90000,0\n"
    )
    res = client.post(
        "/api/import/items.csv",
        files={"file": ("items.csv", csv_text, "text/csv")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["created"] == 1
    assert body["updated"] == 1
    assert body["error_count"] == 0
    updated = _item(client, "NAL-1")
    assert updated["name"] == "Nails 1in"
    assert updated["unit_price_cents"] == 1234500
    assert updated["quantity"] == old_qty
    assert updated["location_name"] == "Rak A"
    created = _item(client, "NEW-CSV")
    assert created["quantity"] == 3
    assert created["location_name"] == "Rak B"
    assert created["category_name"] == "Hardware"


def test_partial_payment_reduces_credit_and_collects(client: TestClient):
    nails = _item(client, "NAL-1")
    sale = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Dewi",
            "customer_name": "Pak Cicil",
            "customer_phone": "081399900030",
            "lines": [{"item_id": nails["id"], "quantity": 2}],
            "paid": False,
        },
    )
    assert sale.status_code == 200, sale.text
    inv = sale.json()
    half = inv["total_cents"] // 2
    paid = client.post(f"/api/invoices/{inv['id']}/pay", json={"amount_cents": half})
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "issued"
    assert paid.json()["amount_paid_cents"] == half
    assert paid.json()["balance_cents"] == inv["total_cents"] - half
    credit = client.get("/api/credit").json()
    row = next(i for i in credit["invoices"] if i["id"] == inv["id"])
    assert row["balance_cents"] == inv["total_cents"] - half
    cust = next(c for c in credit["customers"] if c["shopper_phone"] == "081399900030")
    assert cust["unpaid_cents"] == inv["total_cents"] - half
    daily = client.get("/api/reports/daily").json()
    assert daily["collected_cents"] == half
    rest = client.post(f"/api/invoices/{inv['id']}/pay", json={"amount_cents": inv["total_cents"] - half})
    assert rest.status_code == 200
    assert rest.json()["status"] == "paid"
    assert rest.json()["balance_cents"] == 0


def test_till_sale_keeps_open_shop_draft(client: TestClient):
    nails = _item(client, "NAL-1")
    start_qty = nails["quantity"]
    start_avail = nails["available"]
    client.post("/api/shop/session", json={"name": "Pak Joko", "phone": "081399900031"})
    held = client.post("/api/shop/po/lines", json={"item_id": nails["id"], "quantity": 2})
    assert held.status_code == 200, held.text
    after_hold = next(i for i in client.get("/api/items").json() if i["id"] == nails["id"])
    assert after_hold["available"] == start_avail - 2
    sale = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Andi",
            "customer_name": "Pak Joko",
            "customer_phone": "081399900031",
            "lines": [{"item_id": nails["id"], "quantity": 1}],
            "paid": True,
        },
    )
    assert sale.status_code == 200, sale.text
    leftover = next(i for i in client.get("/api/items").json() if i["id"] == nails["id"])
    assert leftover["quantity"] == start_qty - 1
    assert leftover["reserved"] == 2
    assert leftover["available"] == leftover["quantity"] - 2
    po = client.get("/api/shop/po").json()
    assert len(po["lines"]) == 1
    assert po["lines"][0]["quantity"] == 2


def test_invoice_gets_due_date_from_credit_days(client: TestClient):
    from datetime import date, timedelta

    from app.timeutil import today_shop

    nails = _item(client, "NAL-1")
    settings = client.patch("/api/settings", json={"credit_days": 14}).json()
    assert settings["credit_days"] == 14
    sale = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Dewi",
            "customer_name": "Bu Tempo",
            "customer_phone": "081399900040",
            "lines": [{"item_id": nails["id"], "quantity": 1}],
            "paid": False,
        },
    )
    assert sale.status_code == 200, sale.text
    expected = (date.fromisoformat(today_shop()) + timedelta(days=14)).isoformat()
    assert sale.json()["due_date"] == expected
    moved = client.patch(f"/api/invoices/{sale.json()['id']}/due", json={"due_date": today_shop()})
    assert moved.status_code == 200
    assert moved.json()["due_date"] == today_shop()
    credit = client.get("/api/credit").json()
    row = next(i for i in credit["invoices"] if i["id"] == sale.json()["id"])
    assert row["overdue_days"] == 0


def test_category_and_location_can_rename_and_delete(client: TestClient):
    cat = client.post("/api/categories", json={"name": "Temp Cat", "name_id": "Kat Sementara"})
    assert cat.status_code == 200, cat.text
    renamed = client.patch(f"/api/categories/{cat.json()['id']}", json={"name": "Temp Cat 2", "name_id": "Kat 2"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Temp Cat 2"
    loc = client.post("/api/locations", json={"name": "Temp Rak"})
    assert loc.status_code == 200, loc.text
    gone = client.delete(f"/api/locations/{loc.json()['id']}")
    assert gone.status_code == 200
    names = {c["name"] for c in client.get("/api/locations").json()}
    assert "Temp Rak" not in names
    client.delete(f"/api/categories/{cat.json()['id']}")
    assert "Temp Cat 2" not in {c["name"] for c in client.get("/api/categories").json()}


def test_settings_prefixes_change_next_invoice(client: TestClient):
    nails = _item(client, "NAL-1")
    patched = client.patch("/api/settings", json={"invoice_prefix": "TB", "po_prefix": "PS"}).json()
    assert patched["invoice_prefix"] == "TB"
    assert patched["po_prefix"] == "PS"
    sale = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Dewi",
            "customer_name": "Prefix",
            "customer_phone": "081399900041",
            "lines": [{"item_id": nails["id"], "quantity": 1}],
            "paid": True,
        },
    )
    assert sale.status_code == 200, sale.text
    assert sale.json()["number"].startswith("TB-")


def test_damage_cannot_take_draft_held_stock(client: TestClient):
    nails = _item(client, "NAL-1")
    client.post("/api/shop/session", json={"name": "Hold", "phone": "081399900050"})
    held = client.post("/api/shop/po/lines", json={"item_id": nails["id"], "quantity": nails["available"]})
    assert held.status_code == 200, held.text
    blocked = client.post(
        "/api/damage",
        json={"reason": "Took the reserved bag", "lines": [{"item_id": nails["id"], "quantity": 1}]},
    )
    assert blocked.status_code == 409, blocked.text
    leftover = _item(client, "NAL-1")
    assert leftover["quantity"] == nails["quantity"]
    assert leftover["available"] == 0
    assert leftover["reserved"] == nails["available"]
    dash = client.get("/api/dashboard").json()
    assert dash["units_reserved"] == nails["available"]
    shop = TestClient(client.app)
    shop.post("/api/shop/session", json={"name": "Hold", "phone": "081399900050"})
    orders = shop.get("/api/shop/orders")
    assert orders.status_code == 200
    assert orders.json() == []


def test_pnl_includes_tax(client: TestClient):
    nails = _item(client, "NAL-1")
    client.patch("/api/settings", json={"tax_rate_bps": 1100})
    sale = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Dewi",
            "customer_name": "Bu Pajak",
            "customer_phone": "081399900051",
            "lines": [{"item_id": nails["id"], "quantity": 2}],
            "paid": True,
        },
    )
    assert sale.status_code == 200, sale.text
    assert sale.json()["tax_cents"] > 0
    daily = client.get("/api/reports/daily").json()
    assert daily["tax_cents"] == sale.json()["tax_cents"]
    assert daily["subtotal_cents"] == sale.json()["subtotal_cents"]
    assert daily["tax_bps"] == 1100


def test_category_merge_moves_items(client: TestClient):
    nails = _item(client, "NAL-1")
    src = client.post("/api/categories", json={"name": "Merge From"}).json()
    dest = client.post("/api/categories", json={"name": "Merge Into"}).json()
    patched = client.patch(f"/api/items/{nails['id']}", json={"category_id": src["id"]})
    assert patched.status_code == 200, patched.text
    gone = client.delete(f"/api/categories/{src['id']}", params={"into_id": dest["id"]})
    assert gone.status_code == 200, gone.text
    item = client.get(f"/api/items/{nails['id']}").json()
    assert item["category_id"] == dest["id"]
    names = {c["name"] for c in client.get("/api/categories").json()}
    assert "Merge From" not in names
    assert "Merge Into" in names


def test_credit_follow_up_note(client: TestClient):
    nails = _item(client, "NAL-1")
    sale = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Andi",
            "customer_name": "Pak Bon",
            "customer_phone": "081399900060",
            "lines": [{"item_id": nails["id"], "quantity": 1}],
            "paid": False,
        },
    )
    assert sale.status_code == 200, sale.text
    from app.timeutil import today_shop

    note = client.post(
        "/api/credit/notes",
        json={"shopper_id": sale.json()["shopper_id"], "body": "Telpon, janji Jumat", "promised_date": today_shop()},
    )
    assert note.status_code == 200, note.text
    assert note.json()["promised_date"] == today_shop()
    credit = client.get("/api/credit").json()
    cust = next(c for c in credit["customers"] if c["shopper_id"] == sale.json()["shopper_id"])
    saved = next(n for n in cust["notes"] if n["body"] == "Telpon, janji Jumat")
    assert saved["promised_date"] == today_shop()
    assert credit["promises_due_count"] >= 1
    dash = client.get("/api/dashboard").json()
    assert dash["promises_due_count"] >= 1


def test_people_report_includes_collected(client: TestClient):
    nails = _item(client, "NAL-1")
    sale = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Rina",
            "customer_name": "Bu Lunas",
            "customer_phone": "081399900061",
            "lines": [{"item_id": nails["id"], "quantity": 1}],
            "paid": True,
        },
    )
    assert sale.status_code == 200, sale.text
    daily = client.get("/api/reports/daily").json()
    rina = next(p for p in daily["salespeople"] if p["name"] == "Rina")
    assert rina["collected_cents"] == sale.json()["total_cents"]
    cust = next(c for c in daily["customers"] if c["phone"] == "081399900061")
    assert cust["collected_cents"] == sale.json()["total_cents"]


def test_returning_customer_reuse_and_report_filter(client: TestClient):
    nails = _item(client, "NAL-1")
    cement = _item(client, "CEM-50")
    first = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Andi",
            "customer_name": "Pak Joko",
            "customer_phone": "081300000222",
            "lines": [{"item_id": nails["id"], "quantity": 1}],
            "paid": True,
        },
    )
    second = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Andi",
            "customer_name": "Joko Wijaya",
            "customer_phone": "081300000222",
            "lines": [{"item_id": nails["id"], "quantity": 1}],
            "paid": True,
        },
    )
    other = client.post(
        "/api/sales",
        json={
            "salesperson_name": "Rina",
            "customer_name": "Bu Sari",
            "customer_phone": "081300000333",
            "lines": [{"item_id": cement["id"], "quantity": 1}],
            "paid": True,
        },
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert other.status_code == 200, other.text
    assert first.json()["shopper_id"] == second.json()["shopper_id"]
    assert other.json()["shopper_id"] != first.json()["shopper_id"]

    shoppers = client.get("/api/shoppers").json()
    joko = next(s for s in shoppers if s["phone"] == "081300000222")
    sari = next(s for s in shoppers if s["phone"] == "081300000333")
    assert joko["name"] == "Joko Wijaya"
    assert joko["id"] == first.json()["shopper_id"]
    assert sari["id"] == other.json()["shopper_id"]

    by_name = client.get("/api/shoppers", params={"q": "joko"}).json()
    assert any(s["id"] == joko["id"] for s in by_name)
    by_phone = client.get("/api/shoppers", params={"q": "000222"}).json()
    assert any(s["id"] == joko["id"] for s in by_phone)
    shop_list = client.get("/api/shop/customers", params={"q": "081300000222"}).json()
    assert any(s["id"] == joko["id"] for s in shop_list)

    dmg = client.post(
        "/api/damage",
        json={"reason": "Broken bags", "lines": [{"item_id": cement["id"], "quantity": 1}]},
    )
    assert dmg.status_code == 200, dmg.text

    shopwide = client.get("/api/reports/pnl").json()
    assert shopwide["writeoff_cents"] > 0
    assert shopwide["revenue_cents"] == first.json()["total_cents"] + second.json()["total_cents"] + other.json()["total_cents"]

    pnl = client.get("/api/reports/pnl", params={"shopper_id": joko["id"]}).json()
    assert pnl["shopper_id"] == joko["id"]
    assert pnl["shopper"]["name"] == "Joko Wijaya"
    assert pnl["shopper"]["phone"] == "081300000222"
    assert len(pnl["receipts"]) == 2
    assert all(r["shopper_id"] == joko["id"] for r in pnl["receipts"])
    assert pnl["revenue_cents"] == first.json()["total_cents"] + second.json()["total_cents"]
    assert pnl["writeoff_cents"] == 0
    assert pnl["collected_cents"] == pnl["revenue_cents"]

    cats = client.get("/api/reports/categories", params={"shopper_id": joko["id"]}).json()
    assert cats["revenue_cents"] == pnl["revenue_cents"]
    daily = client.get("/api/reports/daily", params={"shopper_id": joko["id"]}).json()
    assert daily["revenue_cents"] == pnl["revenue_cents"]
    sari_pnl = client.get("/api/reports/pnl", params={"shopper_id": sari["id"]}).json()
    assert sari_pnl["revenue_cents"] == other.json()["total_cents"]
    assert sari_pnl["writeoff_cents"] == 0

