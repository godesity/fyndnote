def test_create_and_get_template():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    resp = client.post("/api/v1/templates", json={
        "name": "test", "source": "function Foo() { return null; }"
    })
    assert resp.status_code == 201
    tid = resp.json()["id"]
    resp2 = client.get(f"/api/v1/templates/{tid}")
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "test"
