
from fastapi import APIRouter, HTTPException, Response

from schemas import AnnotateRequest, BrowseRowsRequest, MLBatchRequest, MLPrefillRequest
from services.annotation_service import AnnotationService
from services.dataset_service import DatasetService
from services.ml_service import batch_prefill, get_ml_annotation, prefill_row
from services.template_service import TemplateService

router = APIRouter()


@router.get("/projects")
def list_projects(user_id: str):
    return {"projects": AnnotationService.list_projects(user_id)}


@router.post("/projects", status_code=201)
def create_project(body: dict):
    p = AnnotationService.create_project(
        body["name"],
        body["dataset_id"],
        body["template_id"],
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
        pid,
        name,
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
    annotation_fields = (
        AnnotationService.extract_annotation_fields(template["source"])
        if template
        else []
    )
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
    from services.project_dataset import ProjectDatasetService

    meta = ProjectDatasetService.get_meta(pid)
    if meta is not None:
        num_rows = meta["num_rows"]

        def serve(i: int):
            return ProjectDatasetService.get_row(pid, i)

    else:
        ds_meta = DatasetService.list_datasets()
        dmeta = next((d for d in ds_meta if d["id"] == p["dataset_id"]), None)
        if not dmeta:
            raise HTTPException(status_code=404, detail="dataset not found for project")
        num_rows = dmeta["num_rows"]

        def serve(i: int):
            return DatasetService.get_row(p["dataset_id"], i)

    idx = AnnotationService.next_row(pid, user_id, num_rows)
    if idx is None:
        return {"index": None, "row": None, "message": "all rows annotated"}
    try:
        row = serve(idx)
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
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename=annotations.{format}"},
    )


@router.delete("/projects/{pid}")
def delete_project(pid: str):
    if not AnnotationService.delete_project(pid):
        raise HTTPException(status_code=404, detail="project not found")
    return {"status": "deleted"}


@router.delete("/projects/{pid}/annotations/{row_index}")
def delete_annotation(pid: str, row_index: int, user_id: str | None = None):
    if not AnnotationService.get_project(pid):
        raise HTTPException(status_code=404, detail="project not found")
    n = AnnotationService.delete_annotation(pid, row_index, user_id)
    return {"status": "deleted", "rows": n}


@router.delete("/projects/{pid}/annotations")
def delete_all_annotations(pid: str):
    if not AnnotationService.get_project(pid):
        raise HTTPException(status_code=404, detail="project not found")
    n = AnnotationService.delete_all_annotations(pid)
    return {"status": "deleted", "rows": n}


@router.delete("/projects/{pid}/ml-annotations/{row_index}")
def delete_ml_annotation(pid: str, row_index: int):
    if not AnnotationService.get_project(pid):
        raise HTTPException(status_code=404, detail="project not found")
    n = AnnotationService.delete_ml_annotation(pid, row_index)
    return {"status": "deleted", "rows": n}


@router.delete("/projects/{pid}/ml-annotations")
def delete_all_ml_annotations(pid: str):
    if not AnnotationService.get_project(pid):
        raise HTTPException(status_code=404, detail="project not found")
    n = AnnotationService.delete_all_ml_annotations(pid)
    return {"status": "deleted", "rows": n}


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
