import pytest
from fastapi.testclient import TestClient
from fyndnote.main import app as _app
from fyndnote.database import init_db, seed_from_json

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



def test_auth_config_sso_disabled_by_default(client):
    resp = client.get("/api/v1/auth/config")
    assert resp.status_code == 200
    assert resp.json() == {"sso_enabled": False}


def test_auth_config_reflects_sso_enabled(client, monkeypatch):
    from fyndnote.services import keycloak_service as kc
    monkeypatch.setattr(kc, "SSO_ENABLED", True)
    resp = client.get("/api/v1/auth/config")
    assert resp.status_code == 200
    assert resp.json() == {"sso_enabled": True}