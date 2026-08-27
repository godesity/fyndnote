import csv
import tempfile

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
