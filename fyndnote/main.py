import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import _IN_REPO
from .database import init_db, seed_from_json
from .upload_guard import UploadSizeGuard

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Section order in Swagger UI / Scalar is the order of this list, not router
# registration order. Every route must carry exactly one of these tags; an
# untagged route lands in an unlabelled section (tests/backend/test_openapi_tags.py).
OPENAPI_TAGS = [
    {
        "name": "Auth",
        "description": "Local user-id login and the SSO-availability probe the SPA reads at boot.",
    },
    {
        "name": "SSO",
        "description": "Keycloak OpenID Connect browser flow. All routes 501 unless SSO is configured.",
    },
    {
        "name": "Datasets",
        "description": "Dataset ingest and raw row access. Datasets are the most expensive resource in the app — mutating routes require a known `user_id`.",
    },
    {
        "name": "Templates",
        "description": "react-live labeling templates.",
    },
    {
        "name": "Projects",
        "description": "Project lifecycle: create, read, rename, delete.",
    },
    {
        "name": "Rows & Annotations",
        "description": "Annotator-facing work: browse and navigate rows, submit and clear annotations, export.",
    },
    {
        "name": "Members",
        "description": "Project membership and roles. Project admins and system admins only.",
    },
    {
        "name": "AI Prefill",
        "description": "Optional ML backend: prefill one row or a batch, read and clear generated annotations.",
    },
]

app = FastAPI(title="fyndnote", openapi_tags=OPENAPI_TAGS)


# Pure-ASGI guard, added first so it ends up innermost: add_middleware prepends,
# so CORS (added next) still wraps it and stamps the 413 with CORS headers. It
# must run before the multipart body is parsed — see its docstring.
app.add_middleware(UploadSizeGuard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Signed-cookie session storage for the SSO state parameter (CSRF protection).
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "dev-insecure-session-secret"),
    https_only=False,
)


@app.on_event("startup")
def startup():
    init_db()
    seed_from_json()
    from .services.dataset_service import DatasetService
    from .upload_guard import check_memory_budget

    try:
        # Uploads are never deleted by any request path, so an abandoned or
        # rejected import would otherwise occupy disk until the end of time.
        DatasetService.reap_orphans()
        DatasetService.requeue_unuploaded()
    except Exception:  # pragma: no cover - never block boot on housekeeping
        logger.exception("Dataset housekeeping failed at startup")
    check_memory_budget()


# Import routers after app creation to avoid circular imports
from .routers import auth, datasets, projects, sso, templates

app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="static",
)

_pkg = Path(__file__).resolve().parent


def _dist_path(env_var: str, packaged: Path, dev: Path) -> Path:
    """Env override wins; prefer live build output in a source checkout; else packaged."""
    if os.getenv(env_var):
        return Path(os.environ[env_var])
    if _IN_REPO:
        return dev
    return packaged


# Serve the built VitePress docs site (public; no auth) under /fyndnote.
repo_root = _pkg.parent
docs_dist = _dist_path(
    "DOCS_DIST", _pkg / "web" / "docs", repo_root / "docs" / ".vitepress" / "dist"
)
if docs_dist.is_dir():
    app.mount(
        "/fyndnote",
        StaticFiles(directory=str(docs_dist), html=True),
        name="docs",
    )
app.include_router(auth.router, prefix="/api/v1")
app.include_router(datasets.router, prefix="/api/v1")
app.include_router(templates.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(sso.router, prefix="/api/v1")

# Serve built frontend as static files
frontend_dist = _dist_path(
    "FRONTEND_DIST", _pkg / "web" / "frontend", repo_root / "frontend" / "dist"
)
if frontend_dist.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(frontend_dist / "assets")),
        name="frontend_assets",
    )

    @app.get("/favicon.svg", include_in_schema=False)
    def favicon():
        return FileResponse(str(frontend_dist / "favicon.svg"))

    @app.get("/icons.svg", include_in_schema=False)
    def icons():
        return FileResponse(str(frontend_dist / "icons.svg"))

    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        if (
            request.url.path.startswith("/api/")
            or request.url.path.startswith("/static/")
            or request.url.path.startswith("/fyndnote")
        ):
            return PlainTextResponse("Not Found", status_code=404)
        index = frontend_dist / "index.html"
        if not index.exists():
            return PlainTextResponse("Not Found", status_code=404)
        return FileResponse(str(index))
