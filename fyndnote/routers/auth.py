from fastapi import APIRouter, HTTPException

from ..database import get_db
from ..services import keycloak_service as kc
from ..schemas import AuthConfig, LoginRequest, LoginResponse

router = APIRouter(tags=["auth"])


@router.get("/auth/config", response_model=AuthConfig)
def auth_config():
    """Tell the SPA whether to offer SSO or the local user-id login form."""
    return AuthConfig(sso_enabled=kc.enabled())


@router.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    db = get_db()
    user = db.execute(
        "SELECT * FROM fyndnote_users WHERE id = ?", (req.user_id,)
    ).fetchone()
    if not user:
        db.close()
        raise HTTPException(status_code=401, detail="unknown_user")

    perms = db.execute(
        "SELECT project_id, role FROM fyndnote_project_permissions WHERE user_id = ?",
        (req.user_id,),
    ).fetchall()
    project_roles = {p["project_id"]: p["role"] for p in perms} if perms else None
    db.close()

    return LoginResponse(
        user_id=user["id"],
        name=user["name"],
        global_role=user["global_role"],
        project_roles=project_roles,
    )
