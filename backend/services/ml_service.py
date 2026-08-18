import json
from datetime import datetime, timezone
import httpx
from database import get_db
from services.dataset_service import DatasetService

ML_TIMEOUT = 15.0


def call_ml_backend(url: str, row_data: dict) -> dict | None:
    try:
        with httpx.Client(timeout=ML_TIMEOUT) as client:
            resp = client.post(url, json={"data": row_data})
            resp.raise_for_status()
            body = resp.json()
            annotation = body.get("annotation")
            if annotation is None:
                return None
            return annotation
    except Exception:
        return None


def get_ml_annotation(pid: str, row_index: int) -> dict | None:
    db = get_db()
    row = db.execute(
        "SELECT * FROM ml_annotations WHERE project_id = ? AND row_index = ?",
        (pid, row_index)
    ).fetchone()
    db.close()
    if not row:
        return None
    return {
        "row_index": row["row_index"],
        "annotator": row["annotator"],
        "data": json.loads(row["data"]),
        "created_at": row["created_at"],
    }


def prefill_row(pid: str, row_index: int) -> dict:
    project = _get_project_settings(pid)
    if not project or not project.get("ml_enabled"):
        return {"row_index": row_index, "annotation": None, "annotator": None}

    existing = get_ml_annotation(pid, row_index)
    if existing:
        return {"row_index": row_index, "annotation": existing["data"], "annotator": existing["annotator"]}

    row = DatasetService.get_row(project["dataset_id"], row_index)
    annotation = call_ml_backend(project["ml_url"], row)
    if annotation is None:
        return {"row_index": row_index, "annotation": None, "annotator": None}

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT OR REPLACE INTO ml_annotations (project_id, row_index, annotator, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (pid, row_index, project["ml_annotator"], json.dumps(annotation), now, now)
    )
    db.commit()
    db.close()

    return {"row_index": row_index, "annotation": annotation, "annotator": project["ml_annotator"]}


def batch_prefill(pid: str, row_indices: list[int] | None = None) -> dict:
    project = _get_project_settings(pid)
    if not project or not project.get("ml_enabled"):
        return {"total": 0, "succeeded": 0, "failed": 0}

    if row_indices is None:
        ds = DatasetService._load_ds(project["dataset_id"])
        row_indices = list(range(len(ds)))

    # Get already-prefilled rows to skip
    db = get_db()
    existing = {r[0] for r in db.execute(
        "SELECT row_index FROM ml_annotations WHERE project_id = ?", (pid,)
    ).fetchall()}
    db.close()

    succeeded = 0
    failed = 0

    for idx in row_indices:
        if idx in existing:
            continue
        row = DatasetService.get_row(project["dataset_id"], idx)
        annotation = call_ml_backend(project["ml_url"], row)
        if annotation is not None:
            db = get_db()
            now = datetime.now(timezone.utc).isoformat()
            db.execute(
                "INSERT OR REPLACE INTO ml_annotations (project_id, row_index, annotator, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (pid, idx, project["ml_annotator"], json.dumps(annotation), now, now)
            )
            db.commit()
            db.close()
            succeeded += 1
        else:
            failed += 1

    return {"total": len(row_indices), "succeeded": succeeded, "failed": failed}


def _get_project_settings(pid: str) -> dict | None:
    db = get_db()
    p = db.execute(
        "SELECT dataset_id, ml_enabled, ml_url, ml_annotator, ml_mode FROM projects WHERE id = ?",
        (pid,)
    ).fetchone()
    db.close()
    if not p:
        return None
    return {
        "dataset_id": p["dataset_id"],
        "ml_enabled": bool(p["ml_enabled"]),
        "ml_url": p["ml_url"],
        "ml_annotator": p["ml_annotator"],
        "ml_mode": p["ml_mode"],
    }
