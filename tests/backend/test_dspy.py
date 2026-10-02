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


def test_prompt_edit_persists_as_new_version(client, project, dspy_dir):
    # seed a tuned v1 (instruction + demos) the way tune/accept would leave it
    dspy_service.add_version(
        project,
        instruction="OLD INSTRUCTION",
        program_state={
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
        },
        kind="tuned",
        optimizer="bootstrap",
        score=0.5,
        n_demos=1,
    )

    resp = client.put(
        f"/api/v1/projects/{project}/dspy",
        json={"instruction": "NEW INSTRUCTION", "model": "openai/other"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["instruction"] == "NEW INSTRUCTION"
    assert body["model"] == "openai/other"
    assert body["kind"] == "edited"
    assert body["active_version"] == 2
    # a hand-edit is not a tune: no score, but demos carry over
    assert body["train_metrics"] is None

    # the edit became v2 and is what predictions run from
    versions = client.get(f"/api/v1/projects/{project}/dspy/versions").json()
    assert [v["version"] for v in versions["versions"]] == [2, 1]
    assert versions["active_version"] == 2
    assert versions["versions"][0]["kind"] == "edited"
    assert versions["versions"][0]["source_version"] == 1
    assert versions["versions"][1]["kind"] == "tuned"
    assert versions["versions"][1]["score"] == 0.5

    # state carried into v2 must agree with v2's own instruction (load_state
    # would otherwise re-assert the tuned text) and must keep the demos
    on_disk = json.loads((dspy_dir / f"{project}.json").read_text())
    assert "instruction" not in on_disk  # schema file only, no prompt state
    assert "input_fields" in on_disk
    _, cfg = dspy_service._ensure_config(project)
    assert cfg["instruction"] == "NEW INSTRUCTION"
    assert cfg["program_state"]["signature"]["instructions"] == "NEW INSTRUCTION"
    assert cfg["program_state"]["demos"] == [{"text": "a", "sentiment": "positive"}]

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


def test_train_parks_pending_then_accept_and_reset(
    client, project, dspy_dir, monkeypatch
):
    canned = {
        "status": "pending",
        "score": 0.8,
        "n_demos": 4,
        "instruction": "OPTIMIZED",
        "optimizer": "bootstrap",
        "train_size": 2,
        "val_size": 1,
        "active_version": 1,
        "active_instruction": "BEFORE",
    }

    def fake_tune(pid, optimizer="mipro", max_examples=50):
        # a real tune() writes the pending row itself; this fake mirrors that
        dspy_service.set_pending(
            pid,
            instruction="OPTIMIZED",
            program_state={
                "signature": {"instructions": "OPTIMIZED", "fields": []},
                "demos": [1, 2, 3, 4],
            },
            optimizer="bootstrap",
            score=0.8,
            train_size=2,
            val_size=1,
            n_demos=4,
            base_version=dspy_service._active_version_of(pid),
        )
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

    # tuning is never live on its own: still pending, active prompt untouched
    cfg = client.get(f"/api/v1/projects/{project}/dspy").json()
    assert (
        cfg["instruction"]
        == "Given the fields below, produce the annotation values for each output field."
    )
    assert cfg["program_state"] is None
    assert cfg["tuned_at"] is None
    assert cfg["pending"]["instruction"] == "OPTIMIZED"
    assert cfg["pending"]["score"] == 0.8

    # reject discards the candidate and changes nothing
    resp = client.post(f"/api/v1/projects/{project}/dspy/reject", json={})
    assert resp.status_code == 200
    assert resp.json()["pending"] is None
    assert resp.json()["instruction"].startswith("Given the fields")
    assert (
        client.post(f"/api/v1/projects/{project}/dspy/reject", json={}).status_code
        == 404
    )

    # accept promotes it to a new tuned version with the score recorded
    client.post(
        f"/api/v1/projects/{project}/dspy/train", json={"optimizer": "bootstrap"}
    )
    resp = client.post(
        f"/api/v1/projects/{project}/dspy/accept", json={"label": "keep"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["instruction"] == "OPTIMIZED"
    assert body["kind"] == "tuned"
    assert body["active_version"] == 2
    assert body["n_demos"] == 4
    assert body["tuned_at"]
    assert body["train_metrics"]["score"] == 0.8
    assert body["pending"] is None

    versions = client.get(f"/api/v1/projects/{project}/dspy/versions").json()
    assert versions["active_version"] == 2
    assert versions["versions"][0]["label"] == "keep"
    assert versions["versions"][0]["score"] == 0.8

    # revert goes back to the untuned v1 (instruction + state together)
    resp = client.post(f"/api/v1/projects/{project}/dspy/revert", json={"version": 1})
    assert resp.status_code == 200
    assert resp.json()["active_version"] == 1
    assert not resp.json()["instruction"].startswith("OPTIMIZED")
    assert (
        client.post(
            f"/api/v1/projects/{project}/dspy/revert", json={"version": 99}
        ).status_code
        == 404
    )


def test_delete_project_removes_program_and_versions(client, project, dspy_dir):
    client.get(f"/api/v1/projects/{project}/dspy")  # auto-derive → schema + v1
    assert (dspy_dir / f"{project}.json").exists()
    assert dspy_service.list_versions(project) != []
    assert client.delete(f"/api/v1/projects/{project}").status_code == 200
    assert not (dspy_dir / f"{project}.json").exists()
    assert dspy_service.list_versions(project) == []


def test_derive_keeps_prompt_drops_state(client, project, dspy_dir):
    # a re-derive must not silently undo the user's prompt: the template owns
    # the field schema, the prompt does not.
    dspy_service.add_version(
        project,
        instruction="MY OWN PROMPT",
        program_state={"signature": {"instructions": "x", "fields": []}, "demos": [1]},
        kind="tuned",
        optimizer="bootstrap",
        score=0.6,
        n_demos=1,
    )
    resp = client.post(f"/api/v1/projects/{project}/dspy/derive", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert "notes" in [f["name"] for f in body["output_fields"]]
    assert body["instruction"] == "MY OWN PROMPT"
    assert body["program_state"] is None  # state cannot survive schema moves
    assert body["kind"] == "edited"
    versions = client.get(f"/api/v1/projects/{project}/dspy/versions").json()
    assert versions["active_version"] == 2
    assert versions["versions"][1]["score"] == 0.6  # tuned run still recorded


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
