import pytest
from fastapi.testclient import TestClient
from main import app as _app
from database import init_db, seed_from_json

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    seed_from_json()

@pytest.fixture
def client():
    with TestClient(_app) as c:
        yield c

def test_login_known_user(client):
    resp = client.post("/api/v1/auth/login", json={"user_id": "alice"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "alice"
    assert data["global_role"] == "system_admin"

def test_login_unknown_user(client):
    resp = client.post("/api/v1/auth/login", json={"user_id": "unknown"})
    assert resp.status_code == 401

def test_login_returns_project_roles(client):
    resp = client.post("/api/v1/auth/login", json={"user_id": "bob"})
    assert resp.status_code == 200
    assert resp.json()["project_roles"] is not None
