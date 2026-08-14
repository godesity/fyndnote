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
