import datetime


def _setup_project(client):
    t_resp = client.post("/api/v1/templates", json={
        "name": "time-filter-test", "source": "<div>{data.text}</div>"
    })
    tid = t_resp.json()["id"]

    d_resp = client.post("/api/v1/datasets/load", json={
        "source": "stanfordnlp/imdb", "split": "train"
    })
    did = d_resp.json()["id"]

    p_resp = client.post("/api/v1/projects", json={
        "name": "time-filter-proj", "dataset_id": did, "template_id": tid
    })
    assert p_resp.status_code == 201
    return p_resp.json()["id"]


class TestAnnotationTimeFilter:
    def test_annotations_created_at_relative_time(self, client):
        pid = _setup_project(client)
        client.post(f"/api/v1/projects/{pid}/annotate", json={
            "row_index": 0, "user_id": "alice", "data": {"sentiment": "positive"}
        })

        # "1h" = last hour — our annotation was just created, so it should match
        resp = client.post(f"/api/v1/projects/{pid}/rows", json={
            "user_id": "alice", "page": 1, "filter": [
                {"field": "annotations.created_at", "operator": ">=", "value": "1h", "conjunction": "AND"}
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(r["index"] == 0 for r in data["rows"])

    def test_annotations_created_at_exact_date_future_no_match(self, client):
        pid = _setup_project(client)
        client.post(f"/api/v1/projects/{pid}/annotate", json={
            "row_index": 0, "user_id": "alice", "data": {"sentiment": "positive"}
        })

        # "2099-01-01" is in the future — our annotation was not created after that
        resp = client.post(f"/api/v1/projects/{pid}/rows", json={
            "user_id": "alice", "page": 1, "filter": [
                {"field": "annotations.created_at", "operator": ">=", "value": "2099-01-01", "conjunction": "AND"}
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0

    def test_annotations_updated_at_relative_time(self, client):
        pid = _setup_project(client)
        client.post(f"/api/v1/projects/{pid}/annotate", json={
            "row_index": 5, "user_id": "alice", "data": {"rating": 4}
        })

        # "2d" = last 2 days — our annotation was just created, so it should match
        resp = client.post(f"/api/v1/projects/{pid}/rows", json={
            "user_id": "alice", "page": 1, "filter": [
                {"field": "annotations.updated_at", "operator": ">=", "value": "2d", "conjunction": "AND"}
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(r["index"] == 5 for r in data["rows"])

    def test_annotations_created_at_exact_datetime(self, client):
        pid = _setup_project(client)
        client.post(f"/api/v1/projects/{pid}/annotate", json={
            "row_index": 10, "user_id": "alice", "data": {"label": "good"}
        })

        # "2020-01-01" is in the past — our annotation was created after that
        resp = client.post(f"/api/v1/projects/{pid}/rows", json={
            "user_id": "alice", "page": 1, "filter": [
                {"field": "annotations.created_at", "operator": ">=", "value": "2020-01-01", "conjunction": "AND"}
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert any(r["index"] == 10 for r in data["rows"])
