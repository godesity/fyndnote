"""End-to-end tests for the Label Studio migration tool.

These drive the real HTTP surface through ``TestClient`` injected as the
migration client's session, so the API-only constraint is itself under test: if
the tool ever reached for the database it would fail here rather than silently
passing.
"""

import json
from pathlib import Path

import pytest

from fyndnote.tools import migrate_labelstudio as mig

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
EXPORT_JSON = FIXTURES / "labelstudio_export.json"
EXPORT_JSONL = FIXTURES / "labelstudio_export.jsonl"
CONFIG_XML = FIXTURES / "labelstudio_config.xml"


def _args(**overrides):
    ns = mig.build_parser().parse_args(
        ["--input", str(EXPORT_JSON), "--user", "alice", "--project-name", "ls-import"]
    )
    for k, v in overrides.items():
        setattr(ns, k, v)
    return ns


def _project_ids(client):
    body = client.get("/api/v1/projects?user_id=alice").json()
    return {p["id"] for p in body["projects"]}


class RecordingClient(mig.Client):
    """Captures annotate calls so ordering/attribution are assertable."""

    def __init__(self, session):
        super().__init__(session=session)
        self.annotated: list[tuple[int, str, dict]] = []

    def annotate(self, pid, row_index, user_id, data):
        super().annotate(pid, row_index, user_id, data)
        self.annotated.append((row_index, user_id, data))


def test_migrate_creates_dataset_template_project_and_annotations(client):
    session = RecordingClient(session=client)
    summary = mig.migrate(
        _args(config=str(CONFIG_XML), allow_partial=True), client=session
    )

    assert summary["tasks"] == 5
    assert summary["dataset_id"] and summary["template_id"] and summary["project_id"]
    # task 5 is the unmappable timeseries task -> no annotation for it
    assert summary["annotations"] == 4
    assert summary["skipped_annotations"] == 1
    assert summary["dropped"] == {"timeserieslabels": ["5"]}
    assert summary["predictions"] == 1  # counted, never written

    proj = client.get(f"/api/v1/projects/{summary['project_id']}?user_id=alice").json()
    assert proj["dataset_id"] == summary["dataset_id"]
    assert proj["num_rows"] == 5
    # every migrated control must be filterable in Browse
    assert proj["annotation_fields"] == [
        "sentiment",
        "topics",
        "summary",
        "quality",
        "entities",
        "objects",
        "outlines",
        "speech",
    ]

    rows = client.post(
        f"/api/v1/projects/{summary['project_id']}/rows",
        json={"user_id": "alice", "page": 1, "per_page": 10, "filter": []},
    ).json()
    assert rows["total"] == 5
    assert (
        rows["rows"][2]["preview"]["image_url"]
        == "/data/local-files/?d=img/street-01.jpg"
    )

    # annotations round-trip through the API in the widget contract shapes
    pid = summary["project_id"]
    a0 = client.get(f"/api/v1/projects/{pid}/annotations/0?user_id=alice").json()[
        "data"
    ]
    assert a0["sentiment"] == "negative"  # cancelled annotation ignored
    assert a0["topics"] == ["security", "policy"]
    assert a0["quality"] == 4.0
    assert a0["summary"] == "Weights must stay internal."

    a2 = client.get(f"/api/v1/projects/{pid}/annotations/2?user_id=alice").json()[
        "data"
    ]
    assert a2["objects"][0] == {
        "x": 0.1,
        "y": 0.2,
        "w": 0.3,
        "h": 0.4,
        "category": "car",
    }
    assert a2["outlines"][0]["type"] == "closed"
    assert a2["outlines"][0]["points"][0] == {"x": 0.05, "y": 0.05}

    a3 = client.get(f"/api/v1/projects/{pid}/annotations/3?user_id=alice").json()[
        "data"
    ]
    assert a3["speech"] == [
        {"start": 1.25, "end": 4.5, "label": "question"},
        {"start": 6.0, "end": 9.75, "label": "answer"},
    ]

    # row index == task order position; every annotation attributed to --user
    assert [r for r, _u, _d in session.annotated] == [0, 1, 2, 3]
    assert all(u == "alice" for _r, u, _d in session.annotated)

    # the generated template is stored and references every planned control
    tmpl = client.get(f"/api/v1/templates/{summary['template_id']}").json()
    assert tmpl["source"].startswith("<div")
    for widget in (
        "<SelectField",
        "<CheckboxGroup",
        "<TextField",
        "<RatingField",
        "<NERField",
        "<BBoxField",
        "<PolygonField",
        "<AudioSegmentField",
    ):
        assert widget in tmpl["source"], widget
    # LS rows are sparse: every data-driven widget must be guarded by its
    # column, or a null cell (image task with no audio) blanks the preview.
    assert "{data.image_url && (" in tmpl["source"]
    assert "{data.audio && (" in tmpl["source"]
    assert "{data.text && (" in tmpl["source"]

    # the migrating user can see the project (create_project granted permission)
    assert pid in _project_ids(client)


def test_migrate_accepts_jsonl_input(client):
    summary = mig.migrate(
        _args(input=str(EXPORT_JSONL), config=str(CONFIG_XML), allow_partial=True),
        client=mig.Client(session=client),
    )
    assert summary["tasks"] == 5
    assert summary["annotations"] == 4


def test_migrate_without_config_infers_widgets(client):
    summary = mig.migrate(_args(allow_partial=True), client=mig.Client(session=client))
    assert summary["controls"] == {
        "sentiment": "SelectField",
        "topics": "CheckboxGroup",
        "summary": "TextField",
        "quality": "RatingField",
        "entities": "NERField",
        "objects": "BBoxField",
        "outlines": "PolygonField",
        "speech": "AudioSegmentField",
    }


def test_migrate_rejects_unknown_user(client):
    before = _project_ids(client)
    with pytest.raises(mig.MigrationError, match="does not exist"):
        mig.migrate(
            _args(user="nobody", allow_partial=True), client=mig.Client(session=client)
        )
    assert _project_ids(client) == before  # failed before any write


def test_migrate_reports_no_ml_annotations(client):
    """Predictions are counted but never written: no HTTP endpoint exists."""
    summary = mig.migrate(
        _args(config=str(CONFIG_XML), allow_partial=True, report_predictions=True),
        client=mig.Client(session=client),
    )
    assert summary["predictions"] == 1
    assert summary["predictions_mapped"] == 1
    assert summary["predictions_unmapped"] == 0
    resp = client.get(f"/api/v1/projects/{summary['project_id']}/ml-annotations/0")
    assert resp.status_code == 404


def test_dry_run_posts_nothing(client):
    session = RecordingClient(session=client)
    before = _project_ids(client)
    summary = mig.migrate(
        _args(config=str(CONFIG_XML), dry_run=True, allow_partial=True),
        client=session,
    )
    assert summary["dry_run"] is True
    assert session.annotated == []
    assert _project_ids(client) == before
    assert "<SelectField" in summary["template"]
    assert summary["first_annotation"]["sentiment"] == "negative"


def test_unmappable_control_hard_fails_before_any_write(client):
    session = RecordingClient(session=client)
    before = _project_ids(client)
    with pytest.raises(mig.MigrationError) as exc:
        mig.migrate(_args(config=str(CONFIG_XML), allow_partial=False), client=session)
    msg = str(exc.value)
    assert "timeserieslabels" in msg
    assert "5" in msg  # offending task id is named
    assert session.annotated == []
    assert _project_ids(client) == before  # nothing was created


def test_main_reports_error_and_exits_nonzero(capsys):
    # The plan hard-fails before any HTTP call, so no server is needed.
    code = mig.main(
        ["--input", str(EXPORT_JSON), "--user", "alice", "--config", str(CONFIG_XML)]
    )
    assert code == 1
    assert "error:" in capsys.readouterr().err


def test_cli_dry_run_prints_summary(capsys):
    code = mig.main(
        [
            "--input",
            str(EXPORT_JSONL),
            "--user",
            "alice",
            "--project-name",
            "ls",
            "--dry-run",
            "--allow-partial",
        ]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "rows to upload" in out
    assert "annotations planned" in out
    assert "(dry run)" in out
    assert "--- generated template ---" in out
    assert "<SelectField" in out


def test_load_tasks_rejects_bad_input(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text("")
    with pytest.raises(mig.MigrationError, match="empty"):
        mig.load_tasks(str(empty))

    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"id": 1}\nnot json\n')
    with pytest.raises(mig.MigrationError, match="invalid JSON line"):
        mig.load_tasks(str(bad))

    obj = tmp_path / "single.json"
    obj.write_text(json.dumps({"id": 1, "data": {"text": "hi"}}))
    assert mig.load_tasks(str(obj)) == [{"id": 1, "data": {"text": "hi"}}]
