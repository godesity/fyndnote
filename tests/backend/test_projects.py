from database import get_db
from database import init_db, seed_from_json

def test_create_project_and_submit_annotation():
    init_db()
    seed_from_json()
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    # Create a template first
    tresp = client.post("/api/v1/templates", json={
        "name": "test", "source": "function T() { return null; }"
    })
    tid = tresp.json()["id"]

    # Load dataset
    dresp = client.post("/api/v1/datasets/load", json={"source": "stanfordnlp/imdb", "split": "train"})
    did = dresp.json()["id"]

    # Create project
    presp = client.post("/api/v1/projects", json={
        "name": "test-proj", "dataset_id": did, "template_id": tid
    })
    assert presp.status_code == 201
    pid = presp.json()["id"]

    # Submit annotation
    aresp = client.post(f"/api/v1/projects/{pid}/annotate", json={
        "row_index": 0, "user_id": "alice", "data": {"sentiment": "positive"}
    })
    assert aresp.status_code == 201

    # Get annotation
    gresp = client.get(f"/api/v1/projects/{pid}/annotations/0?user_id=alice")
    assert gresp.status_code == 200
    assert gresp.json()["data"]["sentiment"] == "positive"


def test_browse_rows_all(client):
    ds_resp = client.post("/api/v1/datasets/load", json={"source": "stanfordnlp/imdb", "split": "train"})
    ds_id = ds_resp.json()["id"]

    t_resp = client.post("/api/v1/templates", json={"name": "test", "source": "<div>{data.text}</div>"})
    t_id = t_resp.json()["id"]

    p_resp = client.post("/api/v1/projects", json={"name": "browse-test", "dataset_id": ds_id, "template_id": t_id})
    pid = p_resp.json()["id"]

    resp = client.post(f"/api/v1/projects/{pid}/rows", json={
        "user_id": "alice", "page": 1, "per_page": 5, "filter": []
    })
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["rows"]) == 5
    assert data["total"] == 25000
    assert data["page"] == 1
    assert data["per_page"] == 5
    assert "index" in data["rows"][0]
    assert "preview" in data["rows"][0]
    assert "annotation_status" in data["rows"][0]
    assert "text" in data["rows"][0]["preview"]
    assert data["rows"][0]["annotation_status"]["by_me"] == False
    assert data["rows"][0]["annotation_status"]["by_any"] == False


def test_browse_rows_annotated_filter(client):
    ds_resp = client.post("/api/v1/datasets/load", json={"source": "stanfordnlp/imdb", "split": "train"})
    ds_id = ds_resp.json()["id"]
    t_resp = client.post("/api/v1/templates", json={"name": "test", "source": "<div>{data.text}</div>"})
    t_id = t_resp.json()["id"]
    p_resp = client.post("/api/v1/projects", json={"name": "browse-test-2", "dataset_id": ds_id, "template_id": t_id})
    pid = p_resp.json()["id"]

    # Annotate one row
    client.post(f"/api/v1/projects/{pid}/annotate", json={"row_index": 0, "user_id": "alice", "data": {"sentiment": "positive"}})

    # Filter annotated
    resp = client.post(f"/api/v1/projects/{pid}/rows", json={
        "user_id": "alice", "page": 1, "filter": [
            {"field": "annotations.annotated_by", "operator": "=", "value": "me", "conjunction": "AND"}
        ]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["rows"][0]["index"] == 0
    assert data["rows"][0]["annotation_status"]["by_me"] == True
    assert data["rows"][0]["annotation_status"]["by_any"] == True

    # Filter unannotated
    resp = client.post(f"/api/v1/projects/{pid}/rows", json={
        "user_id": "alice", "page": 1, "filter": [
            {"field": "annotations.count", "operator": "=", "value": "0", "conjunction": "AND"}
        ]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 24999


def test_delete_project(client):
    ds_resp = client.post("/api/v1/datasets/load", json={"source": "stanfordnlp/imdb", "split": "train"})
    ds_id = ds_resp.json()["id"]
    t_resp = client.post("/api/v1/templates", json={"name": "del-tpl", "source": "<div>{data.text}</div>"})
    t_id = t_resp.json()["id"]
    p_resp = client.post("/api/v1/projects", json={"name": "del-test", "dataset_id": ds_id, "template_id": t_id})
    assert p_resp.status_code == 201
    pid = p_resp.json()["id"]

    # Annotate one row so there is related data to delete
    a_resp = client.post(f"/api/v1/projects/{pid}/annotate", json={
        "row_index": 0, "user_id": "alice", "data": {"sentiment": "positive"}
    })
    assert a_resp.status_code == 201
    assert client.get(f"/api/v1/projects/{pid}?user_id=alice").status_code == 200

    # Delete
    d_resp = client.delete(f"/api/v1/projects/{pid}")
    assert d_resp.status_code == 200
    assert d_resp.json() == {"status": "deleted"}

    # Project gone; annotations gone with it
    assert client.get(f"/api/v1/projects/{pid}?user_id=alice").status_code == 404
    assert client.delete(f"/api/v1/projects/{pid}").status_code == 404

    # Child rows actually gone (FK enforcement is off on runtime connections,
    # so orphaned rows would otherwise survive invisibly)
    db = get_db()
    try:
        for table in ("fyndnot_annotations", "fyndnot_ml_annotations"):
            assert db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE project_id = ?", (pid,)
            ).fetchone()[0] == 0
    finally:
        db.close()

    # Dataset survived
    ds_list = client.get("/api/v1/datasets").json()["datasets"]
    assert any(d["id"] == ds_id for d in ds_list)
