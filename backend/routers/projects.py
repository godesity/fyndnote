from fastapi import APIRouter, HTTPException, Response
from database import get_db
from schemas import AnnotateRequest, BrowseRowsRequest
from services.annotation_service import AnnotationService
from services.template_service import TemplateService
from services.dataset_service import DatasetService
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
    return {
        **p,
        "template_source": template["source"] if template else None,
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
        raise HTTPException(status_code=404, detail="dataset not found")
    idx = AnnotationService.next_row(pid, user_id, meta["num_rows"])
    if idx is None:
        return {"index": None, "row": None, "message": "all rows annotated"}
    row = DatasetService.get_row(p["dataset_id"], idx)
    return {"index": idx, "row": row}

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
    db.execute("DELETE FROM project_permissions WHERE project_id = ?", (pid,))
    db.execute("DELETE FROM projects WHERE id = ?", (pid,))
    db.commit()
    db.close()
    return {"status": "deleted"}
