from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_pin_locks_backup_not_shop(tmp_path: Path):
    app = create_app(f"sqlite:///{tmp_path / 'pin.db'}")
    client = TestClient(app)
    assert client.get("/api/backup").status_code == 200
    assert client.get("/api/shop/catalog").status_code == 200
    set_pin = client.post("/api/operator/pin", json={"pin": "1234"})
    assert set_pin.status_code == 200, set_pin.text
    locked = TestClient(app)
    assert locked.get("/api/backup").status_code == 401
    assert locked.get("/api/dashboard").status_code == 401
    assert locked.get("/api/shop/catalog").status_code == 200
    assert locked.get("/api/shop/customers").status_code == 200
    assert locked.get("/api/shoppers").status_code == 401
    assert locked.get("/api/settings").status_code == 200
    assert locked.get("/api/health").status_code == 200
    wrong = locked.post("/api/operator/unlock", json={"pin": "0000"})
    assert wrong.status_code == 401
    ok = locked.post("/api/operator/unlock", json={"pin": "1234"})
    assert ok.status_code == 200, ok.text
    assert locked.get("/api/backup").status_code == 200
    locked.post("/api/operator/lock")
    assert locked.get("/api/backup").status_code == 401


def test_lan_blocks_remote_until_enabled(tmp_path: Path):
    app = create_app(f"sqlite:///{tmp_path / 'lan.db'}")
    client = TestClient(app)
    assert client.get("/api/settings").json()["allow_lan"] is False
    from unittest.mock import patch

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
