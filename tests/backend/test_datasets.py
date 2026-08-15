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
    f.unlink()
    assert resp.status_code == 200
    data = resp.json()
    assert data["num_rows"] == 2

    # Verify re-list
    list_resp = client.get("/api/v1/datasets")
    ids = [d["id"] for d in list_resp.json()["datasets"]]
    assert data["id"] in ids
