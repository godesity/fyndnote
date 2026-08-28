import csv
import tempfile

import pytest

from services.annotation_service import AnnotationService
from services.project_dataset import ProjectDatasetService, _frag_dir

CSV_ROWS = [
    {"id": 1, "text": "hello", "score": 0.5},
    {"id": 2, "text": "world", "score": 0.9},
    {"id": 3, "text": "foo", "score": 0.1},
]


def _make_project(client):
    # Write a small CSV source dataset and load it via the API.
    _, path = tempfile.mkstemp(suffix=".csv")
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "text", "score"])
        writer.writeheader()
        writer.writerows(CSV_ROWS)
    dresp = client.post("/api/v1/datasets/load", json={"source": f"file://{path}"})
    assert dresp.status_code == 200
    did = dresp.json()["id"]

    tresp = client.post(
        "/api/v1/templates", json={"name": "tpl", "source": "<div>{data.text}</div>"}
    )
    tid = tresp.json()["id"]

    presp = client.post(
        "/api/v1/projects", json={"name": "p", "dataset_id": did, "template_id": tid}
    )
    assert presp.status_code == 201
    pid = presp.json()["id"]
    return pid, did


def test_ensure_meta_seeds_from_source(client):
    pid, _ = _make_project(client)
    assert ProjectDatasetService.get_meta(pid) is None

    meta = ProjectDatasetService.ensure_meta(pid)
    assert meta["num_rows"] == len(CSV_ROWS)
    assert meta["next_fragment"] == 0
    assert meta["schema"] is not None

    # Second call is a no-op (idempotent).
    meta2 = ProjectDatasetService.ensure_meta(pid)
    assert meta2["num_rows"] == len(CSV_ROWS)

    # num_rows reads from meta now.
    assert ProjectDatasetService.num_rows(pid) == len(CSV_ROWS)


def test_append_rows_writes_frag0_and_bumps(client):
    pid, _ = _make_project(client)
    n = ProjectDatasetService.append_rows(
        pid, [{"a": "x", "b": 1}, {"a": "y", "b": 2}]
    )
    assert n == 2

    frag_dir = _frag_dir(pid)
    assert (frag_dir / "frag_0.parquet").exists()

    meta = ProjectDatasetService.get_meta(pid)
    assert meta["num_rows"] == len(CSV_ROWS) + 2
    assert meta["next_fragment"] == 1
    assert meta["schema"] is not None


def test_append_twice_creates_two_fragments_and_loads_in_order(client):
    pid, _ = _make_project(client)
    ProjectDatasetService.append_rows(pid, [{"a": "one"}])
    ProjectDatasetService.append_rows(pid, [{"a": "two"}, {"a": "three"}])

    frag_dir = _frag_dir(pid)
    assert (frag_dir / "frag_0.parquet").exists()
    assert (frag_dir / "frag_1.parquet").exists()

    meta = ProjectDatasetService.get_meta(pid)
    assert meta["num_rows"] == len(CSV_ROWS) + 3
    assert meta["next_fragment"] == 2

    table = ProjectDatasetService.load_table(pid)
    rows = table.to_pylist()
    # load_table returns only the appended fragment rows, concatenated in order.
    assert rows == [{"a": "one"}, {"a": "two"}, {"a": "three"}]


def test_get_row_returns_serialized_dict(client):
    pid, _ = _make_project(client)
    ProjectDatasetService.append_rows(pid, [{"a": "one"}, {"a": "two"}])

    # Source row (index 0) shaped like DatasetService.get_row.
    row0 = ProjectDatasetService.get_row(pid, 0)
    assert row0["text"] == "hello"
    assert row0["score"] == 0.5

    # Appended row: source rows occupy indices 0..2, appended start at 3.
    appended = ProjectDatasetService.get_row(pid, 3)
    assert appended["a"] == "one"

    # Out of range -> None
    assert ProjectDatasetService.get_row(pid, 9999) is None


def test_num_rows_falls_back_to_source_without_meta(client):
    pid, _ = _make_project(client)
    assert ProjectDatasetService.num_rows(pid) == len(CSV_ROWS)

    # num_rows for a nonexistent project is 0 (graceful).
    assert ProjectDatasetService.num_rows("nope") == 0


def test_get_project_row_serves_source_and_appended(client):
    pid, _ = _make_project(client)
    ProjectDatasetService.append_rows(pid, [{"a": "one"}, {"a": "two"}])

    # Source row still served at index 0.
    src = AnnotationService.get_project_row(pid, 0, "alice")
    assert src is not None
    assert src["row"]["text"] == "hello"

    # Appended row served at index src_len (3).
    appended = AnnotationService.get_project_row(pid, len(CSV_ROWS), "alice")
    assert appended is not None
    assert appended["row"]["a"] == "one"


def test_navigate_row_bounds_include_appended(client):
    pid, _ = _make_project(client)
    ProjectDatasetService.append_rows(pid, [{"a": "one"}, {"a": "two"}])

    # Index src_len (3) is an appended row. It must be addressable in the
    # shuffled navigation list (num_rows == src + fragments), so navigating
    # from it in at least one direction returns a neighbor.
    fwd = AnnotationService.navigate_row(pid, "alice", len(CSV_ROWS), 1)
    back = AnnotationService.navigate_row(pid, "alice", len(CSV_ROWS), -1)
    assert fwd is not None or back is not None


def test_next_row_router_serves_appended_rows(client):
    pid, _ = _make_project(client)
    ProjectDatasetService.append_rows(pid, [{"a": "one"}, {"a": "two"}])

    # Annotate all source rows so next_row must fall through to the appended
    # region (indices src_len..src_len+1).
    for i in range(len(CSV_ROWS)):
        AnnotationService.submit_annotation(pid, i, "alice", {"s": i})

    resp = client.get(f"/api/v1/projects/{pid}/next-row?user_id=alice")
    assert resp.status_code == 200
    body = resp.json()
    assert body["index"] in (len(CSV_ROWS), len(CSV_ROWS) + 1)
    assert body["row"]["a"] in ("one", "two")


def test_unmodified_project_keeps_source_behavior(client):
    pid, _ = _make_project(client)

    # No dataset_meta -> source rows only, appended indices are out of range.
    src = AnnotationService.get_project_row(pid, 0, "alice")
    assert src is not None
    assert src["row"]["text"] == "hello"
    assert AnnotationService.get_project_row(pid, len(CSV_ROWS), "alice") is None

    # Router next-row still serves a source row.
    resp = client.get(f"/api/v1/projects/{pid}/next-row?user_id=alice")
    assert resp.status_code == 200
    assert resp.json()["index"] in range(len(CSV_ROWS))


def test_browse_rows_unmodified_paginates_source_only(client):
    pid, _ = _make_project(client)

    rows_data, total = AnnotationService.browse_rows(pid, "alice", 1, 100, [])
    assert total == len(CSV_ROWS)
    # Index 0 still returns the source row (unchanged behavior).
    by_idx = {e["index"]: e for e in rows_data}
    assert by_idx[0]["preview"]["text"] == "hello"
    assert set(by_idx) == set(range(len(CSV_ROWS)))


def test_import_rows_bulk_endpoint(client):
    pid, _ = _make_project(client)

    body = {"rows": [{"text": "imported one"}, {"text": "imported two"}]}
    resp = client.post(f"/api/v1/projects/{pid}/rows/bulk", json=body)
    assert resp.status_code == 200
    assert resp.json()["imported"] == 2

    # Appended rows served at indices src_len..src_len+1.
    r0 = AnnotationService.get_project_row(pid, len(CSV_ROWS), "alice")
    assert r0["row"]["text"] == "imported one"
    r1 = AnnotationService.get_project_row(pid, len(CSV_ROWS) + 1, "alice")
    assert r1["row"]["text"] == "imported two"

    # num_rows now = source_len + 2
    assert ProjectDatasetService.num_rows(pid) == len(CSV_ROWS) + 2


def test_import_rows_bulk_404_for_unknown_project(client):
    resp = client.post("/api/v1/projects/nope/rows/bulk", json={"rows": [{"text": "x"}]})
    assert resp.status_code == 404


def test_import_rows_bulk_422_on_heterogeneous(client):
    pid, _ = _make_project(client)
    resp = client.post(
        f"/api/v1/projects/{pid}/rows/bulk",
        json={"rows": [{"a": 1}, {"b": 2}]},
    )
    assert resp.status_code == 422
    assert "same columns" in resp.json()["detail"]


def test_browse_rows_modified_includes_appended_fragments(client):
    pid, _ = _make_project(client)
    ProjectDatasetService.append_rows(pid, [{"a": "one"}, {"a": "two"}])

    rows_data, total = AnnotationService.browse_rows(pid, "alice", 1, 100, [])
    assert total == len(CSV_ROWS) + 2

    by_idx = {e["index"]: e for e in rows_data}
    # Source row still served at index 0.
    assert by_idx[0]["preview"]["text"] == "hello"
    # Appended rows served at indices src_len..src_len+1.
    assert by_idx[len(CSV_ROWS)]["preview"]["a"] == "one"
    assert by_idx[len(CSV_ROWS) + 1]["preview"]["a"] == "two"


def test_append_rows_rejects_heterogeneous_columns(client):
    pid, _ = _make_project(client)
    with pytest.raises(ValueError):
        ProjectDatasetService.append_rows(pid, [{"a": 1}, {"b": 2}])

    # Nothing should have been written for the rejected batch.
    assert list(_frag_dir(pid).glob("frag_*.parquet")) == []


def test_append_rows_empty_returns_zero(client):
    pid, _ = _make_project(client)
    n = ProjectDatasetService.append_rows(pid, [])
    assert n == 0

    # No fragment should be written for an empty batch.
    assert list(_frag_dir(pid).glob("frag_*.parquet")) == []
