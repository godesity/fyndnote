import os
from pathlib import Path

_PKG_PARENT = Path(__file__).resolve().parent.parent
_IN_REPO = (_PKG_PARENT / "data").is_dir()  # source checkout vs site-packages
ROOT = Path(
    os.getenv("FYNDNOTE_HOME")
    or (_PKG_PARENT if _IN_REPO else Path.home() / ".fyndnote")
)
DATA_DIR = ROOT / "data"
DATABASE_PATH = DATA_DIR / "labeling.db"

# Set DATABASE_URL to use a server database instead of SQLite, e.g.
#   DATABASE_URL=postgresql://user:pass@localhost:5432/fyndnote
# Any SQLAlchemy dialect works (postgresql, mysql, mariadb, …); see
# fyndnote/database.py for the dialect-specific SQL codegen.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DATASETS_DIR = DATA_DIR / "datasets"
PROJECTS_DIR = DATASETS_DIR / "projects"
DATASETS_UPLOAD_DIR = DATA_DIR / "datasets" / "uploads"
TEMPLATES_DIR = DATA_DIR / "templates"

# Redirect HF datasets cache into our managed tree (avoids duplication)
os.environ.setdefault("HF_DATASETS_CACHE", str(DATASETS_DIR))

# S3 cache settings
S3_CACHE_ENABLED = os.getenv("S3_CACHE_ENABLED", "false").lower() == "true"
S3_CACHE_BUCKET = os.getenv("S3_CACHE_BUCKET", "")
S3_CACHE_PREFIX = os.getenv("S3_CACHE_PREFIX", "datasets-cache")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL") or None

# LRU / disk-pressure settings
MAX_CACHED_DATASETS = int(os.getenv("MAX_CACHED_DATASETS", "10"))
DISK_USAGE_THRESHOLD = float(os.getenv("DISK_USAGE_THRESHOLD", "0.9"))

# Upload limits. MAX_UPLOAD_BYTES bounds a single uploaded file (checked twice:
# from Content-Length before any byte is written, and again from the spooled
# part on disk). MAX_CONCURRENT_UPLOADS bounds how many uploads may be parsed at
# once — each one costs a file copy plus a full pyarrow conversion, so without a
# cap N simultaneous uploads scale RAM and disk with N.
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(2 * 1024**3)))
MAX_CONCURRENT_UPLOADS = int(os.getenv("MAX_CONCURRENT_UPLOADS", "2"))
# Seconds a request may sit waiting for a free slot before it gets a 503. The
# browser has already paid the transfer cost by then, so waiting is cheaper than
# making the user re-upload gigabytes.
MAX_UPLOAD_WAIT_SECONDS = float(os.getenv("MAX_UPLOAD_WAIT_SECONDS", "900"))
UPLOAD_READ_BYTES = 1024 * 1024

# ---------------------------------------------------------------------------
# Keycloak SSO (OpenID Connect) — MinIO-style: backend validates Keycloak JWTs
# statelessly against the realm JWKS endpoint.
# ---------------------------------------------------------------------------
SSO_ENABLED = os.getenv("SSO_ENABLED", "false").lower() == "true"
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "fyndnote")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "fyndnote-app")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "")
# Public redirect URI that Keycloak sends the auth code back to. Point it at the
# backend callback so Keycloak redirects the browser (top-level nav) to the API
# — the SameSite=Lax session cookie IS sent on a top-level navigation, so the
# CSRF state check works. authorize_url() appends "/callback" to this value.
SSO_REDIRECT_URI = os.getenv("SSO_REDIRECT_URI", "http://localhost:8000/api/v1/sso")
# SPA origin the backend redirects to with the token after a successful exchange.
SSO_APP_ORIGIN = os.getenv("SSO_APP_ORIGIN", "http://localhost:8000")
SSO_AUDIENCE = os.getenv("SSO_AUDIENCE", "fyndnote-app")
