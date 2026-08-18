from fastapi import APIRouter, HTTPException, Response
from database import get_db
from schemas import AnnotateRequest, BrowseRowsRequest, MLPrefillRequest, MLBatchRequest
from services.annotation_service import AnnotationService
from services.template_service import TemplateService
from services.dataset_service import DatasetService
from services.ml_service import prefill_row, batch_prefill, get_ml_annotation
import json

router = APIRouter()

@router.get("/projects")
def list_projects(user_id: str):
    return {"projects": AnnotationService.list_projects(user_id)}

@router.post("/projects", status_code=201)
def create_project(body: dict):
    p = AnnotationService.create_project(
        body["name"], body["dataset_id"], body["template_id"],
        color=body.get("color", "#1976d2"),
        tags=body.get("tags", ""),
        instructions=body.get("instructions", ""),
        ml_enabled=body.get("ml_enabled", False),
        ml_url=body.get("ml_url", ""),
        ml_annotator=body.get("ml_annotator", ""),
        ml_mode=body.get("ml_mode", "on_navigate"),
    )
    return p

@router.put("/projects/{pid}")
def update_project(pid: str, body: dict):
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    p = AnnotationService.update_project(
        pid, name,
        color=body.get("color"),
        tags=body.get("tags"),
        instructions=body.get("instructions"),
        ml_enabled=body.get("ml_enabled"),
        ml_url=body.get("ml_url"),
        ml_annotator=body.get("ml_annotator"),
        ml_mode=body.get("ml_mode"),
    )
    if not p:
        raise HTTPException(status_code=404, detail="project not found")
    return p

@router.get("/projects/{pid}")
def get_project(pid: str, user_id: str):
    p = AnnotationService.get_project(pid)
    if not p:
        raise HTTPException(status_code=404, detail="project not found")
    template = TemplateService.get(p["template_id"])
    ds_list = DatasetService.list_datasets()
    ds_meta = next((d for d in ds_list if d["id"] == p["dataset_id"]), None)
    progress = AnnotationService.get_progress(pid, user_id)
    annotation_fields = AnnotationService.extract_annotation_fields(template["source"]) if template else []
    return {
        **p,
        "template_source": template["source"] if template else None,
        "annotation_fields": annotation_fields,
        "num_rows": ds_meta["num_rows"] if ds_meta else 0,
        "progress": progress,
    }

@router.post("/projects/{pid}/rows")
def browse_rows(pid: str, body: BrowseRowsRequest):
    rows, total = AnnotationService.browse_rows(
        pid, body.user_id, body.page, body.per_page, body.filter
    )
    return {"rows": rows, "total": total, "page": body.page, "per_page": body.per_page}

@router.get("/projects/{pid}/next-row")
def next_row(pid: str, user_id: str):
    p = AnnotationService.get_project(pid)
    if not p:
        raise HTTPException(status_code=404, detail="project not found")
    ds_meta = DatasetService.list_datasets()
    meta = next((d for d in ds_meta if d["id"] == p["dataset_id"]), None)
    if not meta:
        raise HTTPException(status_code=404, detail="dataset not found for project")
    idx = AnnotationService.next_row(pid, user_id, meta["num_rows"])
    if idx is None:
        return {"index": None, "row": None, "message": "all rows annotated"}
    try:
        row = DatasetService.get_row(p["dataset_id"], idx)
    except Exception:
        raise HTTPException(status_code=404, detail="dataset source no longer available")
    return {"index": idx, "row": row}

@router.get("/projects/{pid}/rows/{row_index}")
def get_project_row(pid: str, row_index: int, user_id: str):
    result = AnnotationService.get_project_row(pid, row_index, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="row not found")
    return result

@router.get("/projects/{pid}/rows/{row_index}/next")
def next_project_row(pid: str, row_index: int, user_id: str):
    result = AnnotationService.navigate_row(pid, user_id, row_index, 1)
    if not result:
        raise HTTPException(status_code=404, detail="no next row")
    return result

@router.get("/projects/{pid}/rows/{row_index}/prev")
def prev_project_row(pid: str, row_index: int, user_id: str):
    result = AnnotationService.navigate_row(pid, user_id, row_index, -1)
    if not result:
        raise HTTPException(status_code=404, detail="no previous row")
    return result

@router.post("/projects/{pid}/annotate", status_code=201)
def submit_annotation(pid: str, body: AnnotateRequest):
    AnnotationService.submit_annotation(pid, body.row_index, body.user_id, body.data)
    return {"status": "ok"}

@router.get("/projects/{pid}/annotations/{row_index}")
def get_annotation(pid: str, row_index: int, user_id: str):
    ann = AnnotationService.get_annotation(pid, row_index, user_id)
    if not ann:
        raise HTTPException(status_code=404, detail="annotation not found")
    return ann

@router.get("/projects/{pid}/annotations/export")
def export_annotations(pid: str, format: str = "parquet"):
    data = AnnotationService.export_annotations(pid, format=format)
    return Response(content=data, media_type="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename=annotations.{format}"})

@router.delete("/projects/{pid}")
def delete_project(pid: str):
    db = get_db()
    db.execute("DELETE FROM annotations WHERE project_id = ?", (pid,))
    db.execute("DELETE FROM ml_annotations WHERE project_id = ?", (pid,))
    db.execute("DELETE FROM project_permissions WHERE project_id = ?", (pid,))
    db.execute("DELETE FROM projects WHERE id = ?", (pid,))
    db.commit()
    db.close()
    return {"status": "deleted"}

# ---- ML Backend endpoints ----

@router.post("/projects/{pid}/ml-prefill")
def ml_prefill(pid: str, body: MLPrefillRequest):
    result = prefill_row(pid, body.row_index)
    return result

@router.post("/projects/{pid}/ml-batch")
def ml_batch(pid: str, body: MLBatchRequest):
    result = batch_prefill(pid, body.row_indices)
    return result

@router.get("/projects/{pid}/ml-annotations/{row_index}")
def ml_annotation(pid: str, row_index: int):
    ann = get_ml_annotation(pid, row_index)
    if not ann:
        raise HTTPException(status_code=404, detail="ML annotation not found")
    return ann
