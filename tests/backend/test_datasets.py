import pytest

from fyndnote.database import init_db


def test_list_datasets_empty():
    from fastapi.testclient import TestClient
    from fyndnote.main import app

    client = TestClient(app)
    resp = client.get("/api/v1/datasets")
    assert resp.status_code == 200


def test_load_dataset():
    from fastapi.testclient import TestClient
    from fyndnote.main import app

    client = TestClient(app)
    resp = client.post(
        "/api/v1/datasets/load?user_id=alice",
        json={"source": "stanfordnlp/imdb", "split": "train"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["num_rows"] > 0


def test_load_http_csv():
    init_db()
    from unittest.mock import patch, MagicMock
    from fyndnote.services.dataset_service import DatasetService

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.iter_content.return_value = [b"text,label\nhello,0\nworld,1\n"]
    with patch(
        "fyndnote.services.dataset_service.requests.get", return_value=mock_resp
    ):
        meta = DatasetService.load("https://example.com/data.csv")
    assert meta["source_type"] == "http"
    assert meta["source_format"] == "csv"
    assert meta["num_rows"] == 2


def test_upload_csv():
    from fastapi.testclient import TestClient
    from fyndnote.main import app

    client = TestClient(app)
    content = b"text,label\nhello,0\nworld,1\n"
    resp = client.post(
        "/api/v1/datasets/upload?user_id=alice",
        files={"file": ("test.csv", content, "text/csv")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["num_rows"] == 2
    assert data["source_type"] == "file"


def test_upload_unsupported_format():
    from fastapi.testclient import TestClient
    from fyndnote.main import app

    client = TestClient(app)
    content = b"test"
    resp = client.post(
        "/api/v1/datasets/upload?user_id=alice",
        files={"file": ("test.xlsx", content, "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_load_file_csv(tmp_path):
    init_db()
    f = tmp_path / "test.csv"
    f.write_text("text,label\nhello,0\nworld,1\n")
    from fyndnote.services.dataset_service import DatasetService

    meta = DatasetService.load(f"file://{f}")
    assert meta["source_type"] == "file"
    assert meta["num_rows"] == 2


def test_load_dataset_workflow(client):
    import tempfile, pathlib

    f = pathlib.Path(tempfile.mktemp(suffix=".csv"))
    f.write_text("text,label\nhello,0\nworld,1\n")
    resp = client.post(
        "/api/v1/datasets/load?user_id=alice", json={"source": f"file://{f}"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["num_rows"] == 2

    # Row loads successfully while cache exists
    row_resp = client.get(f"/api/v1/datasets/{data['id']}/rows/0")
    assert row_resp.status_code == 200
    assert row_resp.json()["row"]["text"] == "hello"

    # Deleting the source file does NOT remove the dataset from listing
    # (external source is informational only — dataset is served from cache)
    f.unlink()
    list_resp = client.get("/api/v1/datasets")
    ids = [d["id"] for d in list_resp.json()["datasets"]]
    assert data["id"] in ids


def test_dataset_details(client):
    import tempfile, pathlib

    f = pathlib.Path(tempfile.mktemp(suffix=".csv"))
    f.write_text("text,label\nrow one,0\nrow two,1\n")
    load_resp = client.post(
        "/api/v1/datasets/load?user_id=alice", json={"source": f"file://{f}"}
    )
    assert load_resp.status_code == 200
    ds_id = load_resp.json()["id"]

    t_resp = client.post(
        "/api/v1/templates",
        json={"name": "details-tpl", "source": "<div>{data.text}</div>"},
    )
    t_id = t_resp.json()["id"]
    a_resp = client.post(
        "/api/v1/projects",
        json={"name": "details-a", "dataset_id": ds_id, "template_id": t_id},
    )
    p_a = a_resp.json()["id"]
    b_resp = client.post(
        "/api/v1/projects",
        json={"name": "details-b", "dataset_id": ds_id, "template_id": t_id},
    )
    p_b = b_resp.json()["id"]

    # Project A: alice + bob on row 0 -> 1 distinct row, 2 annotations
    client.post(
        f"/api/v1/projects/{p_a}/annotate",
        json={"row_index": 0, "user_id": "alice", "data": {"l": "a1"}},
    )
    client.post(
        f"/api/v1/projects/{p_a}/annotate",
        json={"row_index": 0, "user_id": "bob", "data": {"l": "b1"}},
    )
    # Project B: alice on rows 0 and 1 -> 2 distinct rows, 2 annotations
    client.post(
        f"/api/v1/projects/{p_b}/annotate",
        json={"row_index": 0, "user_id": "alice", "data": {"l": "a2"}},
    )
    client.post(
        f"/api/v1/projects/{p_b}/annotate",
        json={"row_index": 1, "user_id": "alice", "data": {"l": "a3"}},
    )

    # ML predictions: 1 for A, 2 for B
    from fyndnote.database import get_db

    db = get_db()
    for pid, count in ((p_a, 1), (p_b, 2)):
        for row in range(count):
            db.execute(
                "INSERT OR REPLACE INTO fyndnote_ml_annotations "
                "(project_id, row_index, annotator, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    pid,
                    row,
                    "ml-test",
                    "{}",
                    "2026-08-25T00:00:00",
                    "2026-08-25T00:00:00",
                ),
            )
    db.commit()
    db.close()

    resp = client.get(f"/api/v1/datasets/{ds_id}/details")
    assert resp.status_code == 200
    body = resp.json()
    assert body["dataset"]["num_rows"] == 2
    assert body["dataset"]["source"].endswith(".csv")

    by_name = {p["name"]: p for p in body["projects"]}
    assert by_name["details-a"] == {
        "id": p_a,
        "name": "details-a",
        "color": by_name["details-a"]["color"],
        "annotated_rows": 1,
        "annotations": 2,
        "predictions": 1,
    }
    assert by_name["details-b"]["annotated_rows"] == 2
    assert by_name["details-b"]["annotations"] == 2
    assert by_name["details-b"]["predictions"] == 2
    assert body["totals"] == {"annotations": 4, "predictions": 3}

    missing = client.get("/api/v1/datasets/does-not-exist/details")
    assert missing.status_code == 404


def test_datasets_config_advertises_limits(client):
    from fyndnote.config import MAX_CONCURRENT_UPLOADS, MAX_UPLOAD_BYTES

    resp = client.get("/api/v1/datasets/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["max_upload_bytes"] == MAX_UPLOAD_BYTES
    assert body["max_concurrent_uploads"] == MAX_CONCURRENT_UPLOADS
    assert set(body["formats"]) == {"csv", "json", "jsonl", "parquet"}


def test_upload_requires_known_user(client):
    content = b"text,label\nhello,0\n"
    missing = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("t.csv", content, "text/csv")},
    )
    assert missing.status_code == 422  # user_id is mandatory
    unknown = client.post(
        "/api/v1/datasets/upload?user_id=ghost",
        files={"file": ("t.csv", content, "text/csv")},
    )
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == "unknown_user"


def test_load_requires_known_user(client):
    assert client.post("/api/v1/datasets/load", json={"source": "x"}).status_code == 422
    resp = client.post("/api/v1/datasets/load?user_id=ghost", json={"source": "x"})
    assert resp.status_code == 401


def test_upload_size_guard_rejects_without_reading_body(monkeypatch):
    """The 413 must come from the headers alone.

    Checked at the ASGI layer on purpose: with ``UploadFile = File(...)`` FastAPI
    parses the whole multipart body before any endpoint code runs, so an
    in-handler check cannot reject a lying ``Content-Length`` at all — uvicorn
    stays blocked awaiting bytes that never arrive. This asserts the guard
    answers *and* never touches ``receive``.
    """
    import asyncio

    from fyndnote import upload_guard

    monkeypatch.setattr(upload_guard, "MAX_UPLOAD_BYTES", 8)

    body_reads = []

    async def receive():
        body_reads.append(1)
        return {"type": "http.request", "body": b"", "more_body": False}

    async def unreachable_app(scope, _receive, _send):
        raise AssertionError("guard passed an oversized request downstream")

    messages = []

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/datasets/upload",
        "headers": [(b"content-length", b"999999999")],
    }
    asyncio.run(upload_guard.UploadSizeGuard(unreachable_app)(scope, receive, send))

    assert messages[0]["status"] == 413
    assert (b"connection", b"close") in messages[0]["headers"]
    assert b"upload limit" in messages[1]["body"]
    assert body_reads == [], "guard consumed the request body"


def test_upload_size_guard_passes_normal_requests(monkeypatch):
    """Nothing else — including an in-budget upload — may be intercepted."""
    import asyncio

    from fyndnote import upload_guard

    monkeypatch.setattr(upload_guard, "MAX_UPLOAD_BYTES", 8)
    reached = []

    async def downstream(scope, _receive, _send):
        reached.append(scope["path"])

    async def send(message):
        raise AssertionError(
            f"guard answered a request it should pass through: {message}"
        )

    for path, headers in [
        ("/api/v1/datasets/upload", [(b"content-length", b"4")]),  # in budget
        ("/api/v1/datasets/upload", []),  # chunked: streamed check decides
        ("/api/v1/datasets/upload", [(b"content-length", b"huge")]),  # unparsable
        ("/api/v1/projects", [(b"content-length", b"999999999")]),  # other route
    ]:
        scope = {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": headers,
        }
        asyncio.run(upload_guard.UploadSizeGuard(downstream)(scope, None, send))
    assert reached == [
        "/api/v1/datasets/upload",
        "/api/v1/datasets/upload",
        "/api/v1/datasets/upload",
        "/api/v1/projects",
    ]


def test_upload_rejects_oversized_stream(client, monkeypatch):
    """Without a usable Content-Length the streamed copy still enforces the cap."""
    from fyndnote.services import dataset_service

    uploads = dataset_service.DATASETS_UPLOAD_DIR
    uploads.mkdir(parents=True, exist_ok=True)
    before = list(uploads.glob("*.csv"))
    monkeypatch.setattr(dataset_service, "MAX_UPLOAD_BYTES", 8)
    resp = client.post(
        "/api/v1/datasets/upload?user_id=alice",
        files={"file": ("big.csv", b"text,label\naaaaaaaaaa,1\n", "text/csv")},
    )
    assert resp.status_code == 413
    # A rejected upload must not leave its copy behind.
    assert list(uploads.glob("*.csv")) == before


def test_upload_unparseable_file_leaves_nothing(client):
    from fyndnote.services import dataset_service

    uploads = dataset_service.DATASETS_UPLOAD_DIR
    uploads.mkdir(parents=True, exist_ok=True)
    before = list(uploads.glob("*.parquet"))
    resp = client.post(
        "/api/v1/datasets/upload?user_id=alice",
        files={
            "file": (
                "broken.parquet",
                b"not a parquet file at all",
                "application/octet-stream",
            )
        },
    )
    assert resp.status_code == 400
    assert list(uploads.glob("*.parquet")) == before


def test_failed_load_removes_cache_dir(client, tmp_path):
    """A corrupt file must not leak the arrow cache dir it created."""
    from fyndnote.services import dataset_service

    bad = tmp_path / "broken.parquet"
    bad.write_bytes(b"definitely not parquet")
    before = {p.name for p in dataset_service.DATASETS_DIR.iterdir()}
    with pytest.raises(ValueError):
        dataset_service.DatasetService.load(f"file://{bad}")
    assert {p.name for p in dataset_service.DATASETS_DIR.iterdir()} == before


def test_delete_dataset_requires_admin(client, tmp_path):
    f = tmp_path / "d.csv"
    f.write_text("text,label\nhello,0\n")
    ds_id = client.post(
        "/api/v1/datasets/load?user_id=alice", json={"source": f"file://{f}"}
    ).json()["id"]
    resp = client.delete(f"/api/v1/datasets/{ds_id}?user_id=bob")
    assert resp.status_code == 403
    assert client.get(f"/api/v1/datasets/{ds_id}/details").status_code == 200


def test_delete_dataset_refuses_in_use(client, tmp_path):
    f = tmp_path / "d.csv"
    f.write_text("text,label\nhello,0\n")
    ds_id = client.post(
        "/api/v1/datasets/load?user_id=alice", json={"source": f"file://{f}"}
    ).json()["id"]
    tpl = client.post(
        "/api/v1/templates",
        json={"name": "del-tpl", "source": "<div>{data.text}</div>"},
    ).json()["id"]
    client.post(
        "/api/v1/projects",
        json={"name": "del-proj", "dataset_id": ds_id, "template_id": tpl},
    )
    resp = client.delete(f"/api/v1/datasets/{ds_id}?user_id=alice")
    assert resp.status_code == 409
    assert client.get(f"/api/v1/datasets/{ds_id}/details").status_code == 200


def test_delete_dataset_frees_disk(client):
    from pathlib import Path

    from fyndnote.services import dataset_service

    meta = client.post(
        "/api/v1/datasets/upload?user_id=alice",
        files={"file": ("gone.csv", b"text,label\nhello,0\nworld,1\n", "text/csv")},
    ).json()
    ds_id = meta["id"]
    cache_dir = dataset_service._cache_dir_for(ds_id)
    upload_copy = Path(meta["source"].removeprefix("file://"))
    assert cache_dir.is_dir()
    assert upload_copy.is_file()

    resp = client.delete(f"/api/v1/datasets/{ds_id}?user_id=alice")
    assert resp.status_code == 200
    assert not cache_dir.exists()
    assert not upload_copy.exists()
    assert ds_id not in dataset_service.DatasetService._instances
    assert client.get(f"/api/v1/datasets/{ds_id}/details").status_code == 404


def test_reap_orphans_removes_unreferenced_uploads(client):
    import os
    import time

    from fyndnote.services import dataset_service

    uploads = dataset_service.DATASETS_UPLOAD_DIR
    uploads.mkdir(parents=True, exist_ok=True)
    stale = uploads / "00000000-0000-0000-0000-00000000000a.csv"
    stale.write_text("text,label\nhello,0\n")
    dangling = uploads / "00000000-0000-0000-0000-00000000000b.csv.part"
    dangling.write_text("text,label\nhalf-written\n")
    fresh = uploads / "00000000-0000-0000-0000-00000000000c.csv"
    fresh.write_text("text,label\nin-flight\n")
    old = time.time() - 7200
    for orphan in (stale, dangling):
        os.utime(orphan, (old, old))

    removed = dataset_service.DatasetService.reap_orphans(max_age_minutes=30)
    assert removed >= 2
    assert not stale.exists()
    assert not dangling.exists()
    # An in-flight upload (written, not yet inserted) survives the sweep.
    assert fresh.exists()
    fresh.unlink()


def test_reaper_keeps_referenced_upload(client):
    """The upload copy is a file:// dataset's canonical source: never sweep it."""
    from pathlib import Path

    meta = client.post(
        "/api/v1/datasets/upload?user_id=alice",
        files={"file": ("keep.csv", b"text,label\nhello,0\n", "text/csv")},
    ).json()
    copy = Path(meta["source"].removeprefix("file://"))
    assert copy.is_file()

    from fyndnote.services import dataset_service

    dataset_service.DatasetService.reap_orphans(max_age_minutes=0)
    assert copy.is_file()
    assert (
        client.get(f"/api/v1/datasets/{meta['id']}/rows/0").json()["row"]["text"]
        == "hello"
    )


def test_delete_unknown_dataset_is_404(client):
    assert client.delete("/api/v1/datasets/nope?user_id=alice").status_code == 404


def test_upload_slot_exhaustion_is_503_not_a_hang(client, monkeypatch):
    """A full slot table must answer 503 once the queue wait expires.

    Guards two things: that exhaustion is refused rather than queued forever, and
    that the deadline is actually consulted (a broken comparison here parks the
    request indefinitely instead of failing it).
    """
    import threading
    import time

    from fyndnote.routers import datasets as datasets_router

    monkeypatch.setattr(datasets_router, "_slots", threading.Semaphore(0))
    monkeypatch.setattr(datasets_router, "MAX_UPLOAD_WAIT_SECONDS", 0.5)
    t0 = time.monotonic()
    resp = client.post(
        "/api/v1/datasets/upload?user_id=alice",
        files={"file": ("c.csv", b"text,label\nhi,0\n", "text/csv")},
    )
    waited = time.monotonic() - t0
    assert resp.status_code == 503
    assert "Too many concurrent uploads" in resp.json()["detail"]
    # Polled at 0.25 s intervals; the refused request must respect the deadline
    # instead of either returning instantly or spinning past it.
    assert 0.5 <= waited < 3.0


def test_failed_upload_releases_its_slot(client):
    """Rejected uploads must not leak slots, or N failures wedge the endpoint."""
    for _ in range(3):
        resp = client.post(
            "/api/v1/datasets/upload?user_id=alice",
            files={
                "file": (
                    "bad.parquet",
                    b"not a parquet file",
                    "application/octet-stream",
                )
            },
        )
        assert resp.status_code == 400
    ok = client.post(
        "/api/v1/datasets/upload?user_id=alice",
        files={"file": ("ok.csv", b"text,label\nhi,0\n", "text/csv")},
    )
    assert ok.status_code == 201
    ds_id = ok.json()["id"]
    assert client.delete(f"/api/v1/datasets/{ds_id}?user_id=alice").status_code == 200


def test_container_memory_limit_parses_cgroup_files(tmp_path):
    """The startup budget check must survive every shape cgroup files take.

    An unguarded int() here would raise inside the startup hook and stop the app
    from booting on hosts that report "no limit" the awkward way.
    """
    from fyndnote.upload_guard import container_memory_limit

    def probe(*contents):
        paths = []
        for i, body in enumerate(contents):
            f = tmp_path / f"cgroup_{i}_{body!r}"
            f.write_text(body)
            paths.append(str(f))
        return container_memory_limit(tuple(paths))

    gib = 3 * 1024**3
    assert probe(f"{gib}\n") == gib  # cgroup v2, real limit
    assert probe("max", f"{gib}\n") == gib  # v2 unlimited -> falls through to v1
    assert probe("max\n", "max\n") is None
    assert probe("", "") is None  # empty file
    assert probe(str(2**63 - 1)) is None  # v1 "no limit" sentinel
    assert probe("not-a-number", "not-a-number") is None
    assert container_memory_limit(("/nonexistent/v2", "/nonexistent/v1")) is None
    # An unreadable first candidate must not abort the scan.
    late = tmp_path / "late"
    late.write_text("1048576\n")
    assert container_memory_limit(("/nonexistent/v2", str(late))) == 1048576


# --------------------------------------------------------------------------- #
# Display names: every dataset gets a unique, user-meaningful label            #
# --------------------------------------------------------------------------- #

CSV = b"text,label\nhello,0\nworld,1\n"


def _upload(client, filename, content=CSV, alias=None):
    data = {"alias": alias} if alias is not None else None
    return client.post(
        "/api/v1/datasets/upload?user_id=alice",
        files={"file": (filename, content, "text/csv")},
        data=data,
    )


def test_upload_names_dataset_after_original_filename(client):
    """The label is the filename the user picked, not the uuid on disk."""
    resp = _upload(client, "imdb.csv")
    assert resp.status_code == 201
    assert resp.json()["name"] == "imdb.csv"
    listed = client.get("/api/v1/datasets").json()["datasets"]
    assert [d["name"] for d in listed] == ["imdb.csv"]


def test_upload_strips_directories_from_filename(client):
    """IE/Safari send a full path; only the basename should surface."""
    assert _upload(client, r"C:\fakepath\reviews.csv").json()["name"] == "reviews.csv"


def test_second_upload_of_same_filename_is_rejected_with_suggestion(client):
    first = _upload(client, "dup.csv")
    assert first.status_code == 201
    second = _upload(client, "dup.csv")
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["suggested_name"] == "dup.csv (2)"

    # Accepting the suggestion succeeds and keeps both datasets addressable.
    accepted = _upload(client, "dup.csv", alias=detail["suggested_name"])
    assert accepted.status_code == 201
    assert accepted.json()["name"] == "dup.csv (2)"


def test_rejected_upload_does_not_reserve_its_name(client):
    """A bad file must not poison the label (the uuid original is cleaned too)."""
    bad = _upload(client, "broken.csv", content=b"\x00\x01\x02 not a csv \x00")
    assert bad.status_code == 400
    assert _upload(client, "broken.csv").status_code == 201


def test_upload_alias_is_used_verbatim(client):
    resp = _upload(client, "whatever.csv", alias="Sentiment train")
    assert resp.status_code == 201
    assert resp.json()["name"] == "Sentiment train"
    details = client.get(f"/api/v1/datasets/{resp.json()['id']}/details").json()
    assert details["dataset"]["name"] == "Sentiment train"


def test_load_uses_alias_and_rejects_duplicates(client):
    import pathlib
    import tempfile

    f = pathlib.Path(tempfile.mktemp(suffix=".csv"))
    f.write_text("text,label\nhello,0\nworld,1\n")
    body = {"source": f"file://{f}", "alias": "corpus"}

    assert client.post("/api/v1/datasets/load?user_id=alice", json=body).json()["name"] == "corpus"

    clash = client.post("/api/v1/datasets/load?user_id=alice", json=body)
    assert clash.status_code == 409
    assert clash.json()["detail"]["suggested_name"] == "corpus (2)"


def test_name_available_endpoint(client):
    _upload(client, "taken.csv")

    free = client.get("/api/v1/datasets/name-available", params={"name": "fresh"})
    assert free.status_code == 200
    assert free.json() == {
        "name": "fresh",
        "available": True,
        "suggested_name": "fresh",
    }

    busy = client.get("/api/v1/datasets/name-available", params={"name": "taken.csv"})
    assert busy.json()["available"] is False
    assert busy.json()["suggested_name"] == "taken.csv (2)"

    # No name typed yet: the check falls back to the label the source implies.
    derived = client.get(
        "/api/v1/datasets/name-available", params={"source": "file:///tmp/taken.csv"}
    )
    assert derived.json()["name"] == "taken.csv"
    assert derived.json()["available"] is False

    assert client.get("/api/v1/datasets/name-available").status_code == 400


def test_like_wildcards_in_names_do_not_produce_phantom_collisions(client):
    """`_`/`%` in a base must not make an unrelated name look taken."""
    _upload(client, "dataXv1.csv")
    resp = client.get("/api/v1/datasets/name-available", params={"name": "data_v1.csv"})
    assert resp.json()["available"] is True


def test_legacy_rows_get_distinct_names_on_migration():
    """Pre-alias rows all displayed the same thing; backfill must de-dup them."""
    from fyndnote import database

    engine = database._get_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE fyndnote_datasets")
        # Exactly how release 0.1.0 wrote it: no `name` column at all.
        conn.exec_driver_sql(
            "CREATE TABLE fyndnote_datasets ("
            " id TEXT PRIMARY KEY, source TEXT NOT NULL, source_type TEXT NOT NULL,"
            " source_format TEXT, hf_name TEXT, hf_split TEXT, num_rows INTEGER NOT NULL,"
            " columns TEXT NOT NULL, created_at TEXT NOT NULL, s3_uploaded INTEGER DEFAULT 0)"
        )
        for i in range(3):
            conn.exec_driver_sql(
                "INSERT INTO fyndnote_datasets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"ds{i}",
                    "stanfordnlp/imdb",
                    "huggingface",
                    None,
                    "plain_text",
                    "train",
                    10,
                    "[]",
                    f"2026-01-0{i}",
                    0,
                ),
            )

    database.init_db()

    with engine.connect() as conn:
        names = [
            r[0]
            for r in conn.exec_driver_sql(
                "SELECT name FROM fyndnote_datasets ORDER BY created_at"
            )
        ]
    # Creation order decides who keeps the bare label. Uniqueness itself is
    # asserted by test_migration_creates_the_unique_index_create_all_skips.
    assert names == ["stanfordnlp/imdb", "stanfordnlp/imdb (2)", "stanfordnlp/imdb (3)"]


def test_migration_creates_the_unique_index_create_all_skips():
    """An upgraded table must enforce uniqueness at the DB level, not just in code.

    ``metadata.create_all`` skips an existing table wholesale — its indexes
    included — so without ``_ensure_dataset_name_index`` an upgraded server ends
    up with the ``name`` column but no unique index: two concurrent loads could
    both commit the same label and the picker silently shows duplicates.
    """
    import pytest
    from sqlalchemy import inspect
    from sqlalchemy.exc import IntegrityError

    from fyndnote import database

    engine = database._get_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE fyndnote_datasets")
        conn.exec_driver_sql(
            "CREATE TABLE fyndnote_datasets ("
            " id TEXT PRIMARY KEY, source TEXT NOT NULL, source_type TEXT NOT NULL,"
            " source_format TEXT, hf_name TEXT, hf_split TEXT, num_rows INTEGER NOT NULL,"
            " columns TEXT NOT NULL, created_at TEXT NOT NULL, s3_uploaded INTEGER DEFAULT 0)"
        )
        conn.exec_driver_sql(
            "INSERT INTO fyndnote_datasets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "ds0",
                "stanfordnlp/imdb",
                "huggingface",
                None,
                "plain_text",
                "train",
                10,
                "[]",
                "2026-01-01",
                0,
            ),
        )

    database.init_db()

    indexes = inspect(engine).get_indexes("fyndnote_datasets")
    unique = {i["name"] for i in indexes if i.get("unique")}
    assert "fyndnote_datasets_name_uq" in unique, indexes

    # The index must actually reject a second row claiming the same label.
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO fyndnote_datasets VALUES ("
            " 'dup', 'other/repo', 'huggingface', NULL, NULL, NULL, 1, '[]',"
            " '2026-02-01', 0, 'stanfordnlp/imdb')"
        )
