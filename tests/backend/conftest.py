"""Backend test fixtures.

Nothing here may touch the developer's real data directory. ``fyndnote.config``
freezes every path at *import* time (``labeling.db``, ``data/datasets``,
``data/templates``) and the services import those constants by value, so the
redirection has to happen in two places:

1. before ``fyndnote`` is first imported, via ``FYNDNOTE_HOME``, and
2. per test, by rebinding the module globals the services actually read.

Each test gets a brand-new ``labeling.db`` (real isolation: no test can see
another test's rows) plus its own upload directory. The HuggingFace cache under
``data/datasets/<id>/hf_cache`` is deliberately *shared* through a symlink —
it is tens of gigabytes, and re-downloading/re-converting it per test would
make the suite unrunnable.
"""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

# Set before ``fyndnote.config`` is imported anywhere: it reads these once.
# A repo-local home keeps the shared cache next to the dev server's copy, so
# cached datasets are reused instead of re-downloaded on every run.
_HOME = Path(os.environ.get("FYNDNOTE_TEST_HOME") or _ROOT / ".pytest-home")
(_HOME / "data").mkdir(parents=True, exist_ok=True)
os.environ["FYNDNOTE_HOME"] = str(_HOME)
# A server-dialect DATABASE_URL in the environment would outrank the isolated
# SQLite file and send every test to the developer's real database.
os.environ["DATABASE_URL"] = ""

import pytest
from fastapi.testclient import TestClient

from fyndnote import config, database
from fyndnote.database import init_db, seed_from_json
from fyndnote.services.dataset_service import DatasetService

# The heavy, content-addressed part of the tree is shared; the database is not.
_SHARED = ("datasets", "templates")


@pytest.fixture(autouse=True)
def isolated_home(monkeypatch, tmp_path_factory):
    """Point the whole data tree at a throwaway location for one test."""
    home = tmp_path_factory.mktemp("home")
    data = home / "data"
    data.mkdir()
    for name in _SHARED:
        shared = config.DATA_DIR / name
        shared.mkdir(parents=True, exist_ok=True)
        (data / name).symlink_to(shared)
    db_path = data / "labeling.db"

    monkeypatch.setattr(config, "DATABASE_PATH", db_path)
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    monkeypatch.setattr(config, "DATABASE_URL", "")
    monkeypatch.setattr(database, "DATABASE_URL", "")
    # Uploaded originals are persisted next to the cache; keep them in the
    # scratch dir instead of accumulating one uuid file per test forever.
    uploads = data / "datasets" / "uploads"
    monkeypatch.setattr(config, "DATASETS_UPLOAD_DIR", uploads)
    monkeypatch.setattr(
        sys.modules["fyndnote.services.dataset_service"], "DATASETS_UPLOAD_DIR", uploads
    )

    # Engines and loaded Datasets are process-lifetime caches: without a reset
    # they outlive the temp directory they were created for.
    database._engines.clear()
    DatasetService._instances.clear()
    DatasetService._access_times.clear()

    init_db()
    seed_from_json()
    yield
    for engine in database._engines.values():
        engine.dispose()
    database._engines.clear()


@pytest.fixture
def client():
    from fyndnote.main import app

    # ``with`` runs the app's startup handlers (init_db + seed), matching a real
    # server instead of leaving lifespan-dependent state uninitialised.
    with TestClient(app) as test_client:
        yield test_client
