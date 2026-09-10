"""Keycloak SSO endpoints (MinIO-style OpenID Connect).

GET  /api/v1/sso/login    -> redirect to Keycloak authorize
GET  /api/v1/sso/callback -> exchange code, create/refresh local user, return token
GET  /api/v1/sso/logout   -> redirect to Keycloak logout
GET  /api/v1/sso/me       -> decode Bearer JWT and return the local user
"""

import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import RedirectResponse
from starlette.requests import Request

from ..config import SSO_APP_ORIGIN, SSO_REDIRECT_URI
from ..database import get_db
from ..services import keycloak_service as kc

router = APIRouter(tags=["sso"])


def _require_sso():
    if not kc.enabled():
        raise HTTPException(status_code=501, detail="sso_not_enabled")


def _upsert_user(identity: dict) -> dict:
    """Create or refresh a local user row from Keycloak claims."""
    sub = identity["sub"]
    db = get_db()
    row = db.execute(
        "SELECT id, name, global_role FROM fyndnote_users WHERE id = ?", (sub,)
    ).fetchone()
    if row:
        db.execute(
            "UPDATE fyndnote_users SET name = ?, global_role = ? WHERE id = ?",
            (identity["name"], identity["global_role"], sub),
        )
    else:
        db.execute(
            "INSERT INTO fyndnote_users (id, name, global_role) VALUES (?, ?, ?)",
            (sub, identity["name"], identity["global_role"]),
        )
    db.commit()

    # Project roles come from the local DB (seeded via users.json) — SSO
    # realm roles govern global_role only.
    perms = db.execute(
        "SELECT project_id, role FROM fyndnote_project_permissions WHERE user_id = ?",
        (sub,),
    ).fetchall()
    project_roles = {p["project_id"]: p["role"] for p in perms} if perms else None
    db.close()
    return {
        "user_id": sub,
        "name": identity["name"],
        "global_role": identity["global_role"],
        "project_roles": project_roles,
        "sso_roles": identity.get("roles", []),
    }


@router.get("/sso/login")
def sso_login(request: Request):
    _require_sso()
    state = secrets.token_urlsafe(16)
    # Store state in a cookie so the callback can verify it (CSRF protection).
    request.session["sso_state"] = state
    return RedirectResponse(url=kc.authorize_url(state), status_code=302)


@router.get("/sso/callback")
def sso_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
):
    _require_sso()
    # Keycloak may return ?error=... instead of ?code=... (e.g. the user
    # denied consent or login). Surface that to the client rather than letting
    # FastAPI reject the request with a 422.
    if not code or not state:
        err = request.query_params.get("error")
        if err:
            raise HTTPException(status_code=401, detail=f"callback_error:{err}")
        raise HTTPException(status_code=401, detail="missing_code")

    expected = request.session.get("sso_state")
    if not expected or not secrets.compare_digest(expected, state):
        raise HTTPException(status_code=401, detail="invalid_state")

    tokens = kc.exchange_code(code)
    print(tokens, code)
    if tokens is None:
        raise HTTPException(status_code=401, detail="token_exchange_failed")

    claims = kc.decode_token(tokens.get("access_token", ""))
    if claims is None:
        raise HTTPException(status_code=401, detail="invalid_token")

    identity = kc.user_identity(claims)
    user = _upsert_user(identity)
    # Consume the one-time CSRF state to prevent replay.
    request.session.pop("sso_state", None)
    # Hand the tokens to the SPA via a top-level redirect (this callback was a
    # top-level navigation from Keycloak, so the browser will follow this 302).
    params = urlencode(
        {
            "token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token", ""),
            "id_token": tokens.get("id_token", ""),
            "user_id": user["user_id"],
            "name": user["name"],
            "global_role": user["global_role"],
        }
    )
    return RedirectResponse(url=f"{SSO_APP_ORIGIN}/callback?{params}", status_code=302)


@router.get("/sso/logout")
def sso_logout(request: Request):
    _require_sso()
    id_token = request.session.get("sso_id_token")
    request.session.clear()
    return RedirectResponse(url=kc.logout_url(id_token or "", SSO_REDIRECT_URI))


@router.get("/sso/me")
def sso_me(authorization: str = Header(default="")):
    _require_sso()
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing_token")
    token = authorization.split(" ", 1)[1]
    claims = kc.decode_token(token)
    if claims is None:
        raise HTTPException(status_code=401, detail="invalid_token")
    identity = kc.user_identity(claims)
    user = _upsert_user(identity)
    return {"user": user}
