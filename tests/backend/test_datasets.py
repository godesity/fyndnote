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
