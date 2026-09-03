from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.operator import DEMO_PASSWORD, DEMO_USERNAME


def login(client: TestClient, username: str = DEMO_USERNAME, password: str = DEMO_PASSWORD):
    res = client.post("/api/operator/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()


def make_client(tmp_path: Path, name: str = "test.db") -> TestClient:
    app = create_app(f"sqlite:///{tmp_path / name}")
    client = TestClient(app)
    login(client)
    return client
