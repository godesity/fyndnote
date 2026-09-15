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
    # The seed's bob -> proj-1/proj-2 roles point at projects the seed never
    # creates. SQLite historically ran with FK checks off and kept those orphan
    # rows; a server backend rejects them, so build the whole graph here.
    from fyndnote.database import get_db

    db = get_db()
    roles = {"proj-1": "project_admin", "proj-2": "annotator"}
    for pid, role in roles.items():
        db.execute(
            "INSERT OR IGNORE INTO fyndnote_projects"
            " (id, name, dataset_id, template_id, salt) VALUES (?, ?, ?, ?, ?)",
            (pid, pid, "ds-1", "tpl-1", "salt"),
        )
        db.execute(
            "INSERT OR IGNORE INTO fyndnote_project_permissions"
            " (user_id, project_id, role) VALUES (?, ?, ?)",
            ("bob", pid, role),
        )
    db.commit()
    db.close()

    resp = client.post("/api/v1/auth/login", json={"user_id": "bob"})
    assert resp.status_code == 200
    assert resp.json()["project_roles"] == roles


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
