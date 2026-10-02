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
    from fyndnote.database import get_db

    # Seeded grants point at proj-1/proj-2, which nothing creates, so those
    # rows only survive where FK checks stay off. Give bob a grant whose
    # project really exists and drop the dangling ones so the mapping holds on
    # sqlite and PostgreSQL alike.
    db = get_db()
    db.execute(
        "INSERT OR IGNORE INTO fyndnote_projects "
        "(id, name, dataset_id, template_id, salt) VALUES (?, ?, ?, ?, ?)",
        ("proj-1", "Seed Demo", "ds-1", "tpl-1", "salt"),
    )
    db.execute("DELETE FROM fyndnote_project_permissions WHERE project_id <> 'proj-1'")
    db.execute(
        "INSERT OR IGNORE INTO fyndnote_project_permissions (user_id, project_id, role) "
        "VALUES (?, ?, ?)",
        ("bob", "proj-1", "project_admin"),
    )
    db.commit()
    db.close()

    resp = client.post("/api/v1/auth/login", json={"user_id": "bob"})
    assert resp.status_code == 200
    assert resp.json()["project_roles"] == {"proj-1": "project_admin"}


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
