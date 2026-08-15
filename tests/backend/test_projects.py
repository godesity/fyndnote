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

    resp = client.get(f"/api/v1/projects/{pid}/rows?user_id=alice&page=1&per_page=5&status=all")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["rows"]) == 5
    assert data["total"] == 25000
    assert data["page"] == 1
    assert data["per_page"] == 5
    assert "index" in data["rows"][0]


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
    resp = client.get(f"/api/v1/projects/{pid}/rows?user_id=alice&page=1&status=annotated_by_me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["rows"][0]["index"] == 0

    # Filter unannotated
    resp = client.get(f"/api/v1/projects/{pid}/rows?user_id=alice&page=1&status=unannotated")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 24999
