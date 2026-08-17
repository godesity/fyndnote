def _setup_project(client):
    """Helper: create template, load dataset, create project. Returns pid."""
    t_resp = client.post("/api/v1/templates", json={
        "name": "filter-test", "source": "<div>{data.text}</div>"
    })
    tid = t_resp.json()["id"]

    d_resp = client.post("/api/v1/datasets/load", json={
        "source": "stanfordnlp/imdb", "split": "train"
    })
    did = d_resp.json()["id"]

    p_resp = client.post("/api/v1/projects", json={
        "name": "filter-test-proj", "dataset_id": did, "template_id": tid
    })
    assert p_resp.status_code == 201
    return p_resp.json()["id"]


class TestFilterAPI:
    def test_browse_rows_no_filter(self, client):
        pid = _setup_project(client)
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

    def test_browse_rows_annotated_by_me(self, client):
        pid = _setup_project(client)
        client.post(f"/api/v1/projects/{pid}/annotate", json={
            "row_index": 0, "user_id": "alice", "data": {"sentiment": "positive"}
        })

        resp = client.post(f"/api/v1/projects/{pid}/rows", json={
            "user_id": "alice", "page": 1, "filter": [
                {"field": "annotations.annotated_by", "operator": "=", "value": "me", "conjunction": "AND"}
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["rows"][0]["index"] == 0

    def test_browse_rows_unannotated(self, client):
        pid = _setup_project(client)
        client.post(f"/api/v1/projects/{pid}/annotate", json={
            "row_index": 0, "user_id": "alice", "data": {"sentiment": "positive"}
        })

        resp = client.post(f"/api/v1/projects/{pid}/rows", json={
            "user_id": "alice", "page": 1, "filter": [
                {"field": "annotations.count", "operator": "=", "value": "0", "conjunction": "AND"}
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 24999
        assert data["rows"][0]["index"] != 0

    def test_browse_rows_annotation_count_gt_zero(self, client):
        pid = _setup_project(client)
        client.post(f"/api/v1/projects/{pid}/annotate", json={
            "row_index": 5, "user_id": "alice", "data": {"rating": 4}
        })

        resp = client.post(f"/api/v1/projects/{pid}/rows", json={
            "user_id": "alice", "page": 1, "filter": [
                {"field": "annotations.count", "operator": ">", "value": "0", "conjunction": "AND"}
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["rows"][0]["index"] == 5

    def test_browse_rows_row_index_range(self, client):
        pid = _setup_project(client)
        resp = client.post(f"/api/v1/projects/{pid}/rows", json={
            "user_id": "alice", "page": 1, "filter": [
                {"field": "row_index", "operator": ">=", "value": "10", "conjunction": "AND"},
                {"field": "row_index", "operator": "<=", "value": "19", "conjunction": "AND"},
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        indices = [r["index"] for r in data["rows"]]
        assert all(10 <= i <= 19 for i in indices)
