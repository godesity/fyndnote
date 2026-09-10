import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

import pytest
from fastapi.testclient import TestClient
from fyndnote.database import init_db, seed_from_json


@pytest.fixture
def client():
    init_db()
    seed_from_json()
    from fyndnote.main import app
    return TestClient(app)
