from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.operator import DEMO_PASSWORD, DEMO_USERNAME
from helpers import login


def test_login_required_for_shop_and_office(tmp_path: Path):
    app = create_app(f"sqlite:///{tmp_path / 'auth.db'}")
    locked = TestClient(app)
    assert locked.get("/api/health").status_code == 200
    status = locked.get("/api/operator/status")
    assert status.status_code == 200
    body = status.json()
    assert body["required"] is True
    assert body["logged_in"] is False
    assert body["setup_needed"] is False
    assert locked.get("/api/backup").status_code == 401
    assert locked.get("/api/dashboard").status_code == 401
    assert locked.get("/api/shop/catalog").status_code == 401
    assert locked.get("/api/shop/customers").status_code == 401
    assert locked.get("/api/shoppers").status_code == 401
    assert locked.get("/api/settings").status_code == 401
    assert locked.get("/api/sales-agents").status_code == 401
    wrong = locked.post("/api/operator/login", json={"username": DEMO_USERNAME, "password": "nope"})
    assert wrong.status_code == 401
    ok = login(locked)
    assert ok["user"]["username"] == DEMO_USERNAME
    assert locked.get("/api/backup").status_code == 200
    assert locked.get("/api/shop/catalog").status_code == 200
    agents = locked.get("/api/sales-agents")
    assert agents.status_code == 200
    names = {row["display_name"] for row in agents.json()}
    assert names == {"Andi", "Rina"}
    locked.post("/api/operator/logout")
    assert locked.get("/api/backup").status_code == 401
    assert locked.get("/api/shop/catalog").status_code == 401


def test_inactive_user_cannot_login(tmp_path: Path):
    app = create_app(f"sqlite:///{tmp_path / 'inactive.db'}")
    client = TestClient(app)
    login(client)
    created = client.post(
        "/api/users",
        json={"username": "sari", "password": "makmur", "display_name": "Sari", "is_sales_agent": True},
    )
    assert created.status_code == 200, created.text
    uid = created.json()["id"]
    assert client.patch(f"/api/users/{uid}", json={"is_active": False}).status_code == 200
    locked = TestClient(app)
    denied = locked.post("/api/operator/login", json={"username": "sari", "password": "makmur"})
    assert denied.status_code == 401
    still = locked.post("/api/operator/login", json={"username": DEMO_USERNAME, "password": DEMO_PASSWORD})
    assert still.status_code == 200


def test_cannot_deactivate_last_active_user(tmp_path: Path):
    app = create_app(f"sqlite:///{tmp_path / 'last-user.db'}")
    client = TestClient(app)
    login(client)
    users = client.get("/api/users").json()
    for row in users:
        if row["username"] != DEMO_USERNAME:
            assert client.patch(f"/api/users/{row['id']}", json={"is_active": False}).status_code == 200
    admin = next(row for row in client.get("/api/users").json() if row["username"] == DEMO_USERNAME)
    blocked = client.patch(f"/api/users/{admin['id']}", json={"is_active": False})
    assert blocked.status_code == 400, blocked.text
    assert client.get("/api/items").status_code == 200


def test_staff_can_add_sales_agent(tmp_path: Path):
    app = create_app(f"sqlite:///{tmp_path / 'staff.db'}")
    client = TestClient(app)
    login(client)
    created = client.post(
        "/api/users",
        json={
            "username": "budi",
            "password": "makmur",
            "display_name": "Budi",
            "is_sales_agent": True,
        },
    )
    assert created.status_code == 200, created.text
    uid = created.json()["id"]
    agents = {row["display_name"] for row in client.get("/api/sales-agents").json()}
    assert "Budi" in agents
    hidden = client.patch(f"/api/users/{uid}", json={"is_active": False})
    assert hidden.status_code == 200, hidden.text
    agents = {row["display_name"] for row in client.get("/api/sales-agents").json()}
    assert "Budi" not in agents


def test_setup_when_no_users(tmp_path: Path):
    from sqlalchemy import delete

    from app.models import User

    app = create_app(f"sqlite:///{tmp_path / 'setup.db'}")
    client = TestClient(app)
    with client.app.state.SessionLocal() as db:
        db.execute(delete(User))
        db.commit()
    status = client.get("/api/operator/status").json()
    assert status["setup_needed"] is True
    blocked = client.post("/api/operator/login", json={"username": "admin", "password": "makmur"})
    assert blocked.status_code == 401
    setup = client.post(
        "/api/operator/setup",
        json={"username": "owner", "password": "secret", "display_name": "Owner"},
    )
    assert setup.status_code == 200, setup.text
    assert setup.json()["user"]["username"] == "owner"
    assert client.get("/api/items").status_code == 200
    again = client.post("/api/operator/setup", json={"username": "two", "password": "secret"})
    assert again.status_code == 400


def test_lan_blocks_remote_until_enabled(tmp_path: Path):
    from unittest.mock import patch

    app = create_app(f"sqlite:///{tmp_path / 'lan.db'}")
    client = TestClient(app)
    login(client)
    assert client.get("/api/settings").json()["allow_lan"] is False

    with patch("app.operator.client_is_local", return_value=False):
        blocked = client.get("/api/dashboard")
        assert blocked.status_code == 403
        blocked_shop = client.get("/api/shop/catalog")
        assert blocked_shop.status_code == 403
    on = client.patch("/api/settings", json={"allow_lan": True})
    assert on.status_code == 200, on.text
    assert on.json()["allow_lan"] is True
    with patch("app.operator.client_is_local", return_value=False):
        assert client.get("/api/dashboard").status_code == 200
        assert client.get("/api/shop/catalog").status_code == 200
