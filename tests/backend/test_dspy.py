"""DSPy ML backend tests — no network; LLM paths are monkeypatched."""

import json

import pytest

from fyndnote.database import get_db
from fyndnote.services import dspy_service

TEMPLATE = """<div>
  <h3>Classify</h3>
  <p>{data.text}</p>
  <SelectField name="sentiment" labels={["positive", "negative", "neutral"]} />
  <CheckboxGroup name="topics" labels={["m", "s"]} />
  <RatingField name="quality" max={5} />
  <TextField name="notes" />
</div>"""


@pytest.fixture
def dspy_dir(tmp_path, monkeypatch):
    """Isolate the per-project program JSON store into tmp_path."""
    d = tmp_path / "dspy"
    monkeypatch.setattr("fyndnote.services.dspy_service.DSPY_DIR", d)
    monkeypatch.setattr("fyndnote.config.DSPY_DIR", d)
    return d


@pytest.fixture
def project(client, tmp_path):
    """Project with a text-column CSV dataset and the widget-rich template."""
    import csv

    path = tmp_path / "data.csv"
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["text"])
        for i in range(10):
            writer.writerow([f"sample row {i}"])
    dresp = client.post("/api/v1/datasets/load", json={"source": f"file://{path}"})
    assert dresp.status_code == 200
    ds_id = dresp.json()["id"]
    tresp = client.post("/api/v1/templates", json={"name": "t", "source": TEMPLATE})
    tid = tresp.json()["id"]
    presp = client.post(
        "/api/v1/projects",
        json={
            "name": "p",
            "dataset_id": ds_id,
            "template_id": tid,
            "ml_enabled": True,
            "ml_annotator": "dspy-test",
            "ml_type": "dspy",
            "dspy_model": "openai/mock",
            "user_id": "alice",
        },
    )
    assert presp.status_code == 201
    return presp.json()["id"]


def _by_name(fields, name):
    return next(f for f in fields if f["name"] == name)


def test_derive_from_template(client, project, dspy_dir):
    resp = client.get(f"/api/v1/projects/{project}/dspy")
    assert resp.status_code == 200
    cfg = resp.json()
    kinds = {f["name"]: f["kind"] for f in cfg["output_fields"]}
    assert kinds == {
        "sentiment": "select",
        "topics": "multiselect",
        "quality": "rating",
        "notes": "text",
    }
    sent = _by_name(cfg["output_fields"], "sentiment")
    assert sent["options"] == ["positive", "negative", "neutral"]
    assert "positive" in sent["desc"] and "neutral" in sent["desc"]
    assert _by_name(cfg["output_fields"], "quality")["max"] == 5
    assert [f["name"] for f in cfg["input_fields"]] == ["text"]
    assert cfg["llm_key_set"] in (True, False)
    assert cfg["model"] == "openai/mock"
    # auto-derive persisted the file
    assert (dspy_dir / f"{project}.json").exists()


def test_prompt_edit_persists_and_rewrites_state(client, project, dspy_dir):
    # seed a tuned state shaped like dspy 3.x Predict.dump_state()
    _, cfg = dspy_service._ensure_config(project)
    cfg["program_state"] = {
        "traces": [],
        "train": [],
        "demos": [{"text": "a", "sentiment": "positive"}],
        "signature": {
            "instructions": "OLD INSTRUCTION",
            "fields": [
                {"prefix": "Text:", "description": "old input desc"},
                {"prefix": "Sentiment:", "description": "old output desc"},
                {"prefix": "Topics:", "description": "old"},
                {"prefix": "Quality:", "description": "old"},
                {"prefix": "Notes:", "description": "old"},
            ],
        },
        "lm": None,
    }
    dspy_service.DspyProgramStore.save(project, cfg)

    resp = client.put(
        f"/api/v1/projects/{project}/dspy",
        json={"instruction": "NEW INSTRUCTION", "model": "openai/other"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["instruction"] == "NEW INSTRUCTION"
    assert body["model"] == "openai/other"

    on_disk = json.loads((dspy_dir / f"{project}.json").read_text())
    assert on_disk["instruction"] == "NEW INSTRUCTION"
    # the tuned state must carry the edit (load_state would otherwise override)
    assert on_disk["program_state"]["signature"]["instructions"] == ("NEW INSTRUCTION")
    # demos survive the rewrite
    assert on_disk["program_state"]["demos"] == [{"text": "a", "sentiment": "positive"}]
    # model persisted on the project row
    proj = client.get(f"/api/v1/projects/{project}?user_id=alice").json()
    assert proj["dspy_model"] == "openai/other"


def test_predict_dispatch(client, project, dspy_dir, monkeypatch):
    calls = []

    def fake_predict(proj, row):
        calls.append((proj, row))
        return {"sentiment": "positive"}

    monkeypatch.setattr(dspy_service, "predict", fake_predict)

    resp = client.post(f"/api/v1/projects/{project}/ml-prefill", json={"row_index": 3})
    assert resp.status_code == 200
    body = resp.json()
    assert body["annotation"] == {"sentiment": "positive"}
    assert body["annotator"] == "dspy-test"
    assert len(calls) == 1
    assert calls[0][1] == {"text": "sample row 3"}

    db = get_db()
    row = db.execute(
        "SELECT * FROM fyndnote_ml_annotations WHERE project_id = ? AND row_index = ?",
        (project, 3),
    ).fetchone()
    db.close()
    assert row is not None
    assert row["annotator"] == "dspy-test"
    assert json.loads(row["data"]) == {"sentiment": "positive"}


def test_external_dispatch_unchanged(client, tmp_path, monkeypatch):
    import csv

    path = tmp_path / "e.csv"
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows([["text"], ["hello"]])
    ds_id = client.post(
        "/api/v1/datasets/load", json={"source": f"file://{path}"}
    ).json()["id"]
    tid = client.post(
        "/api/v1/templates", json={"name": "e", "source": TEMPLATE}
    ).json()["id"]
    pid = client.post(
        "/api/v1/projects",
        json={
            "name": "ext",
            "dataset_id": ds_id,
            "template_id": tid,
            "ml_enabled": True,
            "ml_url": "http://example.invalid/predict",
            "ml_annotator": "ext-bot",
            "user_id": "alice",
        },
    ).json()["id"]

    seen = {}

    def fake_external(url, row):
        seen["url"] = url
        seen["row"] = row
        return {"sentiment": "negative"}

    monkeypatch.setattr("fyndnote.services.ml_service.call_ml_backend", fake_external)
    resp = client.post(f"/api/v1/projects/{pid}/ml-prefill", json={"row_index": 0})
    assert resp.json()["annotation"] == {"sentiment": "negative"}
    assert seen["url"] == "http://example.invalid/predict"


def test_test_endpoint_shape(client, project, dspy_dir, monkeypatch):
    def fake_test_predict(pid, row_index):
        return {
            "inputs": {"text": "x"},
            "fields": [
                {
                    "name": "sentiment",
                    "desc": "d",
                    "kind": "select",
                    "value": "positive",
                }
            ],
            "annotation": {"sentiment": "positive"},
            "instruction": "I",
            "tuned": False,
        }

    monkeypatch.setattr(dspy_service, "test_predict", fake_test_predict)
    resp = client.post(f"/api/v1/projects/{project}/dspy/test", json={"row_index": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["fields"] == [
        {"name": "sentiment", "desc": "d", "kind": "select", "value": "positive"}
    ]
    assert body["annotation"] == {"sentiment": "positive"}
    assert body["tuned"] is False


def test_test_endpoint_not_configured(client, project, dspy_dir, monkeypatch):
    def boom(pid, row_index):
        raise dspy_service.DspyNotConfigured("FYNDNOTE_LLM_API_KEY is not set")

    monkeypatch.setattr(dspy_service, "test_predict", boom)
    resp = client.post(f"/api/v1/projects/{project}/dspy/test", json={"row_index": 0})
    assert resp.status_code == 400
    assert "FYNDNOTE_LLM_API_KEY" in resp.json()["detail"]


def test_train_requires_annotations(client, project, dspy_dir):
    resp = client.post(
        f"/api/v1/projects/{project}/dspy/train",
        json={"optimizer": "bootstrap"},
    )
    assert resp.status_code == 400
    assert "at least 3" in resp.json()["detail"]


def test_train_persists_and_reset(client, project, dspy_dir, monkeypatch):
    canned = {
        "status": "ok",
        "score": 0.8,
        "n_demos": 4,
        "instruction": "OPTIMIZED",
        "optimizer": "bootstrap",
        "train_size": 2,
        "val_size": 1,
    }

    def fake_tune(pid, optimizer="mipro", max_examples=50):
        _, cfg = dspy_service._ensure_config(pid)
        cfg["instruction"] = "OPTIMIZED"
        cfg["program_state"] = {
            "signature": {"instructions": "OPTIMIZED", "fields": []},
            "demos": [1, 2, 3, 4],
        }
        cfg["tuned_at"] = "2026-01-01T00:00:00+00:00"
        cfg["train_metrics"] = canned | {"extra": None}
        cfg["n_demos"] = 4
        dspy_service.DspyProgramStore.save(pid, cfg)
        return canned

    monkeypatch.setattr(dspy_service, "tune", fake_tune)
    resp = client.post(
        f"/api/v1/projects/{project}/dspy/train",
        json={"optimizer": "bootstrap", "max_examples": 50},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["score"] == 0.8
    assert body["n_demos"] == 4

    cfg = client.get(f"/api/v1/projects/{project}/dspy").json()
    assert cfg["tuned_at"] == "2026-01-01T00:00:00+00:00"
    assert cfg["instruction"] == "OPTIMIZED"

    # reset drops tuning, keeps prompt edits
    resp = client.post(f"/api/v1/projects/{project}/dspy/reset", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert body["tuned_at"] is None
    assert body["program_state"] is None
    assert body["n_demos"] == 0
    assert body["instruction"] == "OPTIMIZED"


def test_delete_project_removes_program_file(client, project, dspy_dir):
    client.get(f"/api/v1/projects/{project}/dspy")  # auto-derive → file exists
    assert (dspy_dir / f"{project}.json").exists()
    assert client.delete(f"/api/v1/projects/{project}").status_code == 200
    assert not (dspy_dir / f"{project}.json").exists()


def test_derive_endpoint_overwrites(client, project, dspy_dir):
    # edit config, then re-derive → field edits discarded, tuning dropped
    _, cfg = dspy_service._ensure_config(project)
    cfg["output_fields"] = [f for f in cfg["output_fields"] if f["name"] != "notes"]
    cfg["program_state"] = {
        "signature": {"instructions": "x", "fields": []},
        "demos": [1],
    }
    dspy_service.DspyProgramStore.save(project, cfg)

    resp = client.post(f"/api/v1/projects/{project}/dspy/derive", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert "notes" in [f["name"] for f in body["output_fields"]]
    assert body["program_state"] is None


def test_test_predict_survives_worker_thread_rotation(
    client, project, dspy_dir, monkeypatch
):
    """Regression: uvicorn rotates worker threads and dspy binds dspy.configure()
    to the thread that first called it — every LLM call must work from a fresh
    thread (dspy.context() is thread-rotation safe, configure() is not)."""
    import threading

    import dspy as dspy_mod

    monkeypatch.setattr(dspy_service, "LLM_API_KEY", "test")
    canned = {"sentiment": "positive", "topics": ["m"], "quality": 3, "notes": "ok"}
    monkeypatch.setattr(
        dspy_mod, "LM", lambda *a, **k: dspy_mod.utils.DummyLM([dict(canned)] * 10)
    )

    results = []

    def run():
        try:
            results.append(dspy_service.test_predict(project, 0)["annotation"])
        except Exception as exc:  # noqa: BLE001
            results.append(exc)

    for _ in range(3):  # each call on a NEW thread == uvicorn worker rotation
        t = threading.Thread(target=run)
        t.start()
        t.join()

    expected = {"sentiment": "positive", "topics": ["m"], "quality": 3, "notes": "ok"}
    assert results == [expected] * 3, results
