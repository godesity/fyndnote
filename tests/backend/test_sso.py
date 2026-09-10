"""Tests for the Keycloak SSO endpoints (MinIO-style OIDC flow)."""
import pytest
from fastapi.testclient import TestClient

from fyndnote.main import app as _app

# Force SSO enabled for these tests regardless of the environment.
@pytest.fixture(autouse=True)
def sso_enabled(monkeypatch):
    import fyndnote.config as config
    monkeypatch.setattr(config, "SSO_ENABLED", True)
    import fyndnote.routers.sso as sso
    monkeypatch.setattr(sso.kc, "SSO_ENABLED", True)


@pytest.fixture
def client():
    with TestClient(_app) as c:
        yield c


def test_sso_login_redirects_to_keycloak(client):
    # Do not follow the redirect — we want to assert on the 302 itself.
    resp = client.get("/api/v1/sso/login", follow_redirects=False)
    assert resp.status_code == 302
    assert "localhost:8080" in resp.headers["location"]


def test_sso_me_rejects_missing_token(client):
    resp = client.get("/api/v1/sso/me")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "missing_token"


def test_sso_me_rejects_garbage_token(client):
    resp = client.get("/api/v1/sso/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_token"


def test_sso_callback_rejects_missing_code(client):
    resp = client.get("/api/v1/sso/callback")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "missing_code"


def test_sso_callback_surfaces_keycloak_error(client):
    # Keycloak returns ?error=... when login is denied instead of ?code=...
    resp = client.get("/api/v1/sso/callback?error=access_denied")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "callback_error:access_denied"


def test_sso_callback_rejects_bad_state(client):
    # Session cookie carries the expected state; a mismatched one is rejected.
    resp = client.get(
        "/api/v1/sso/callback?code=abc&state=wrong",
        follow_redirects=False,
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_state"
