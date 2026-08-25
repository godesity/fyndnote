from database import init_db

def test_list_datasets_empty():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    resp = client.get("/api/v1/datasets")
    assert resp.status_code == 200

def test_load_dataset():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    resp = client.post("/api/v1/datasets/load", json={"source": "stanfordnlp/imdb", "split": "train"})
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["num_rows"] > 0

def test_load_http_csv():
    init_db()
    from unittest.mock import patch, MagicMock
    from services.dataset_service import DatasetService
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.iter_content.return_value = [b"text,label\nhello,0\nworld,1\n"]
    with patch("services.dataset_service.requests.get", return_value=mock_resp):
        meta = DatasetService.load("https://example.com/data.csv")
    assert meta["source_type"] == "http"
    assert meta["source_format"] == "csv"
    assert meta["num_rows"] == 2

def test_upload_csv():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    content = b"text,label\nhello,0\nworld,1\n"
    resp = client.post("/api/v1/datasets/upload", files={"file": ("test.csv", content, "text/csv")})
    assert resp.status_code == 201
    data = resp.json()
    assert data["num_rows"] == 2
    assert data["source_type"] == "file"

def test_upload_unsupported_format():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    content = b"test"
    resp = client.post("/api/v1/datasets/upload", files={"file": ("test.xlsx", content, "application/octet-stream")})
    assert resp.status_code == 400

def test_load_file_csv(tmp_path):
    init_db()
    f = tmp_path / "test.csv"
    f.write_text("text,label\nhello,0\nworld,1\n")
    from services.dataset_service import DatasetService
    meta = DatasetService.load(f"file://{f}")
    assert meta["source_type"] == "file"
    assert meta["num_rows"] == 2


def test_load_dataset_workflow(client):
    import tempfile, pathlib
    f = pathlib.Path(tempfile.mktemp(suffix=".csv"))
    f.write_text("text,label\nhello,0\nworld,1\n")
    resp = client.post("/api/v1/datasets/load", json={"source": f"file://{f}"})
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
    load_resp = client.post("/api/v1/datasets/load", json={"source": f"file://{f}"})
    assert load_resp.status_code == 200
    ds_id = load_resp.json()["id"]

    t_resp = client.post("/api/v1/templates", json={"name": "details-tpl", "source": "<div>{data.text}</div>"})
    t_id = t_resp.json()["id"]
    a_resp = client.post("/api/v1/projects", json={"name": "details-a", "dataset_id": ds_id, "template_id": t_id})
    p_a = a_resp.json()["id"]
    b_resp = client.post("/api/v1/projects", json={"name": "details-b", "dataset_id": ds_id, "template_id": t_id})
    p_b = b_resp.json()["id"]

    # Project A: alice + bob on row 0 -> 1 distinct row, 2 annotations
    client.post(f"/api/v1/projects/{p_a}/annotate", json={"row_index": 0, "user_id": "alice", "data": {"l": "a1"}})
    client.post(f"/api/v1/projects/{p_a}/annotate", json={"row_index": 0, "user_id": "bob", "data": {"l": "b1"}})
    # Project B: alice on rows 0 and 1 -> 2 distinct rows, 2 annotations
    client.post(f"/api/v1/projects/{p_b}/annotate", json={"row_index": 0, "user_id": "alice", "data": {"l": "a2"}})
    client.post(f"/api/v1/projects/{p_b}/annotate", json={"row_index": 1, "user_id": "alice", "data": {"l": "a3"}})

    # ML predictions: 1 for A, 2 for B
    from database import get_db
    db = get_db()
    for pid, count in ((p_a, 1), (p_b, 2)):
        for row in range(count):
            db.execute(
                "INSERT OR REPLACE INTO fyndnot_ml_annotations "
                "(project_id, row_index, annotator, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (pid, row, "ml-test", "{}", "2026-08-25T00:00:00", "2026-08-25T00:00:00"),
            )
    db.commit()
    db.close()

    resp = client.get(f"/api/v1/datasets/{ds_id}/details")
    assert resp.status_code == 200
    body = resp.json()
    assert body["dataset"]["num_rows"] == 2
    assert body["dataset"]["source"].endswith(".csv")

    by_name = {p["name"]: p for p in body["projects"]}
    assert by_name["details-a"] == {"id": p_a, "name": "details-a", "color": by_name["details-a"]["color"],
                                    "annotated_rows": 1, "annotations": 2, "predictions": 1}
    assert by_name["details-b"]["annotated_rows"] == 2
    assert by_name["details-b"]["annotations"] == 2
    assert by_name["details-b"]["predictions"] == 2
    assert body["totals"] == {"annotations": 4, "predictions": 3}

    missing = client.get("/api/v1/datasets/does-not-exist/details")
    assert missing.status_code == 404
