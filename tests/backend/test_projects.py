from fyndnote.database import get_db
from fyndnote.database import init_db, seed_from_json

def test_create_project_and_submit_annotation():
    init_db()
    seed_from_json()
    from fastapi.testclient import TestClient
    from fyndnote.main import app
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
        for table in ("fyndnote_annotations", "fyndnote_ml_annotations"):
            assert db.execute(
                f"SELECT COUNT(*) FROM {table} WHERE project_id = ?", (pid,)
            ).fetchone()[0] == 0
    finally:
        db.close()

    # Dataset survived
    ds_list = client.get("/api/v1/datasets").json()["datasets"]
    assert any(d["id"] == ds_id for d in ds_list)


def _make_project(client):
    dresp = client.post("/api/v1/datasets/load", json={"source": "stanfordnlp/imdb", "split": "train"})
    did = dresp.json()["id"]
    tresp = client.post("/api/v1/templates", json={"name": "tpl", "source": "<div>{data.text}</div>"})
    tid = tresp.json()["id"]
    presp = client.post("/api/v1/projects", json={"name": "del-test", "dataset_id": did, "template_id": tid})
    assert presp.status_code == 201
    return presp.json()["id"]


def test_delete_annotation_single_user(client):
    from fyndnote.services.annotation_service import AnnotationService

    pid = _make_project(client)
    AnnotationService.submit_annotation(pid, 0, "alice", {"sentiment": "positive"})
    AnnotationService.submit_annotation(pid, 0, "bob", {"sentiment": "neutral"})

    n = AnnotationService.delete_annotation(pid, 0, "alice")
    assert n == 1
    assert AnnotationService.get_annotation(pid, 0, "alice") is None
    assert AnnotationService.get_annotation(pid, 0, "bob") is not None

    # Deleting again deletes nothing
    assert AnnotationService.delete_annotation(pid, 0, "alice") == 0


def test_delete_annotations_for_row(client):
    from fyndnote.services.annotation_service import AnnotationService

    pid = _make_project(client)
    AnnotationService.submit_annotation(pid, 0, "alice", {"a": 1})
    AnnotationService.submit_annotation(pid, 0, "bob", {"a": 2})
    AnnotationService.submit_annotation(pid, 1, "alice", {"a": 3})

    n = AnnotationService.delete_annotation(pid, 0)
    assert n == 2
    assert AnnotationService.get_annotation(pid, 0, "alice") is None
    assert AnnotationService.get_annotation(pid, 0, "bob") is None
    assert AnnotationService.get_annotation(pid, 1, "alice") is not None


def test_delete_all_annotations_for_project(client):
    from fyndnote.services.annotation_service import AnnotationService

    pid = _make_project(client)
    AnnotationService.submit_annotation(pid, 0, "alice", {"a": 1})
    AnnotationService.submit_annotation(pid, 1, "alice", {"a": 2})
    AnnotationService.submit_annotation(pid, 1, "bob", {"a": 3})

    n = AnnotationService.delete_all_annotations(pid)
    assert n == 3
    from fyndnote.database import get_db
    db = get_db()
    try:
        assert db.execute(
            "SELECT COUNT(*) FROM fyndnote_annotations WHERE project_id = ?", (pid,)
        ).fetchone()[0] == 0
    finally:
        db.close()


def test_delete_ml_annotation_for_row(client):
    from fyndnote.services.annotation_service import AnnotationService

    pid = _make_project(client)
    from fyndnote.database import get_db
    db = get_db()
    db.execute(
        "INSERT INTO fyndnote_ml_annotations (project_id, row_index, annotator, data) VALUES (?, ?, ?, ?)",
        (pid, 0, "ml", '{"pred": 1}'),
    )
    db.commit()
    db.close()

    n = AnnotationService.delete_ml_annotation(pid, 0)
    assert n == 1
    db = get_db()
    try:
        assert db.execute(
            "SELECT COUNT(*) FROM fyndnote_ml_annotations WHERE project_id = ? AND row_index = ?",
            (pid, 0),
        ).fetchone()[0] == 0
    finally:
        db.close()


def test_delete_all_ml_annotations_for_project(client):
    from fyndnote.services.annotation_service import AnnotationService

    pid = _make_project(client)
    from fyndnote.database import get_db
    db = get_db()
    db.execute(
        "INSERT INTO fyndnote_ml_annotations (project_id, row_index, annotator, data) VALUES (?, ?, ?, ?)",
        (pid, 0, "ml", '{"pred": 1}'),
    )
    db.execute(
        "INSERT INTO fyndnote_ml_annotations (project_id, row_index, annotator, data) VALUES (?, ?, ?, ?)",
        (pid, 1, "ml", '{"pred": 2}'),
    )
    db.commit()
    db.close()

    n = AnnotationService.delete_all_ml_annotations(pid)
    assert n == 2
    db = get_db()
    try:
        assert db.execute(
            "SELECT COUNT(*) FROM fyndnote_ml_annotations WHERE project_id = ?", (pid,)
        ).fetchone()[0] == 0
    finally:
        db.close()


def test_delete_annotation_endpoint(client):
    pid = _make_project(client)

    # annotate row 0 as alice + bob (match existing test setup)
    client.post(f"/api/v1/projects/{pid}/annotate", json={
        "row_index": 0, "user_id": "alice", "data": {"sentiment": "positive"}
    })
    client.post(f"/api/v1/projects/{pid}/annotate", json={
        "row_index": 0, "user_id": "bob", "data": {"sentiment": "neutral"}
    })
    # seed ML annotations directly (ml-prefill needs an ml_enabled project)
    from fyndnote.database import get_db
    db = get_db()
    db.execute(
        "INSERT INTO fyndnote_ml_annotations (project_id, row_index, annotator, data) VALUES (?, ?, ?, ?)",
        (pid, 0, "ml", '{"pred": 1}'),
    )
    db.execute(
        "INSERT INTO fyndnote_ml_annotations (project_id, row_index, annotator, data) VALUES (?, ?, ?, ?)",
        (pid, 1, "ml", '{"pred": 2}'),
    )
    db.commit()
    db.close()

    # delete one user's annotation on row 0
    resp = client.delete(f"/api/v1/projects/{pid}/annotations/0?user_id=alice")
    assert resp.status_code == 200 and resp.json()["status"] == "deleted"
    assert resp.json()["rows"] == 1
    # remaining: bob only
    from fyndnote.services.annotation_service import AnnotationService
    assert AnnotationService.get_annotation(pid, 0, "alice") is None
    assert AnnotationService.get_annotation(pid, 0, "bob") is not None

    # deletes all annotations for the project
    resp = client.delete(f"/api/v1/projects/{pid}/annotations")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"
    assert resp.json()["rows"] == 1
    assert AnnotationService.get_annotation(pid, 0, "bob") is None

    # ML single-row delete
    resp = client.delete(f"/api/v1/projects/{pid}/ml-annotations/0")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"
    assert resp.json()["rows"] == 1

    # ML all-for-project delete (removes the remaining row 1)
    resp = client.delete(f"/api/v1/projects/{pid}/ml-annotations")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"
    assert resp.json()["rows"] == 1

    # 404 for unknown project
    assert client.delete("/api/v1/projects/nope/annotations").status_code == 404


def _seed_annotations(client, pid):
    client.post(f"/api/v1/projects/{pid}/annotate", json={
        "row_index": 0, "user_id": "alice", "data": {"sentiment": "positive"}
    })
    client.post(f"/api/v1/projects/{pid}/annotate", json={
        "row_index": 1, "user_id": "alice", "data": {"sentiment": "negative"}
    })


def test_bulk_clear_annotations_filtered(client):
    pid = _make_project(client)
    _seed_annotations(client, pid)

    resp = client.request("DELETE", f"/api/v1/projects/{pid}/annotations/bulk?user_id=alice", json={
        "filter": [{"field": "row_index", "operator": "=", "value": "0", "conjunction": "AND"}]
    })
    assert resp.json()["rows"] == 1

    # row 0 cleared, row 1 still annotated
    from fyndnote.services.annotation_service import AnnotationService
    assert AnnotationService.get_annotation(pid, 0, "alice") is None
    assert AnnotationService.get_annotation(pid, 1, "alice") is not None


def test_bulk_clear_annotations_all(client):
    pid = _make_project(client)
    _seed_annotations(client, pid)

    resp = client.request("DELETE", f"/api/v1/projects/{pid}/annotations/bulk?user_id=alice", json={"filter": []})
    assert resp.status_code == 200
    assert resp.json()["rows"] == 2

    from fyndnote.services.annotation_service import AnnotationService
    assert AnnotationService.get_annotation(pid, 0, "alice") is None
    assert AnnotationService.get_annotation(pid, 1, "alice") is None


def test_bulk_clear_ml_annotations(client):
    pid = _make_project(client)
    client.post(f"/api/v1/projects/{pid}/annotate", json={
        "row_index": 0, "user_id": "alice", "data": {"sentiment": "positive"}
    })
    # seed an ML annotation directly via the DB (no ML backend needed)
    from fyndnote.database import get_db
    db = get_db()
    db.execute(
        "INSERT INTO fyndnote_ml_annotations (project_id, row_index, annotator, data) VALUES (?, ?, ?, ?)",
        (pid, 0, "ml", '{"pred": 1}'),
    )
    db.commit()
    db.close()

    resp = client.request("DELETE", f"/api/v1/projects/{pid}/ml-annotations/bulk?user_id=alice", json={"filter": []})
    assert resp.status_code == 200
    assert resp.json()["rows"] == 1


def test_bulk_clear_annotations_forbidden_for_annotator(client):
    pid = _make_project(client)
    _seed_annotations(client, pid)

    # bob is a global annotator and has no project_admin on this project
    resp = client.request("DELETE", f"/api/v1/projects/{pid}/annotations/bulk?user_id=bob", json={"filter": []})
    assert resp.status_code == 403


def test_bulk_clear_annotations_404(client):
    resp = client.request("DELETE", "/api/v1/projects/nope/annotations/bulk?user_id=alice", json={"filter": []})
    assert resp.status_code == 404
