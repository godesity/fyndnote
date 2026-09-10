import importlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def docs_client(tmp_path, monkeypatch):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.html").write_text("<html>fyndnote-docs-fixture-home</html>")
    (docs_dir / "install").mkdir()
    (docs_dir / "install" / "index.html").write_text(
        "<html>fyndnote-docs-fixture-install</html>"
    )

    monkeypatch.setenv("DOCS_DIST", str(docs_dir))
    import fyndnote.main as main

    importlib.reload(main)
    client = TestClient(main.app)
    yield client
    # Restore module state so later tests see main without the fixture mount.
    del os.environ["DOCS_DIST"]
    importlib.reload(main)


def test_docs_index_served(docs_client):
    r = docs_client.get("/fyndnote/")
    assert r.status_code == 200
    assert "fyndnote-docs-fixture-home" in r.text


def test_docs_clean_url_served(docs_client):
    r = docs_client.get("/fyndnote/install")
    assert r.status_code == 200
    assert "fyndnote-docs-fixture-install" in r.text


def test_unknown_docs_path_is_real_404(docs_client):
    r = docs_client.get("/fyndnote/nope")
    assert r.status_code == 404


def test_spa_root_is_not_docs(docs_client):
    r = docs_client.get("/")
    assert "fyndnote-docs-fixture-home" not in r.text
