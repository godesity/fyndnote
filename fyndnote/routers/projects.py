from fastapi import APIRouter, HTTPException, Response

from ..schemas import (
    AnnotateRequest,
    BrowseRowsRequest,
    BulkClearRequest,
    BulkRowsIn,
    MLBatchRequest,
    MLPrefillRequest,
    ProjectMemberCandidate,
    ProjectMemberIn,
    ProjectMemberOut,
)
from ..services.annotation_service import AnnotationService
from ..services.dataset_service import DatasetService
from ..services.ml_service import batch_prefill, get_ml_annotation, prefill_row
from ..services.permission_service import PROJECT_ROLES, PermissionService
from ..services.template_service import TemplateService

router = APIRouter()


def _require_member_view(pid: str, user_id: str) -> None:
    if not PermissionService.can_view_project(pid, user_id):
        raise HTTPException(status_code=403, detail="insufficient role")


def _require_project_manager(pid: str, user_id: str) -> None:
    """403 unless ``user_id`` may configure the project (incl. its members)."""
    if not PermissionService.can_manage_project(pid, user_id):
        raise HTTPException(status_code=403, detail="insufficient role")


def _require_project(pid: str) -> dict:
    project = AnnotationService.get_project(pid)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.get("/projects", tags=["Projects"])
def list_projects(user_id: str):
    return {"projects": AnnotationService.list_projects(user_id)}


@router.post("/projects", tags=["Projects"], status_code=201)
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
        user_id=body.get("user_id"),
    )
    return p


@router.put("/projects/{pid}", tags=["Projects"])
def update_project(pid: str, body: dict, user_id: str):
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    _require_project(pid)
    _require_project_manager(pid, user_id)
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


@router.get("/projects/{pid}", tags=["Projects"])
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
        "my_role": PermissionService.effective_role(pid, user_id),
        "can_manage": PermissionService.can_manage_project(pid, user_id),
        "can_view": PermissionService.can_view_project(pid, user_id),
    }


@router.post("/projects/{pid}/rows", tags=["Rows & Annotations"])
def browse_rows(pid: str, body: BrowseRowsRequest):
    rows, total = AnnotationService.browse_rows(
        pid, body.user_id, body.page, body.per_page, body.filter
    )
    return {"rows": rows, "total": total, "page": body.page, "per_page": body.per_page}


@router.post("/projects/{pid}/rows/bulk", tags=["Rows & Annotations"])
def import_rows(pid: str, body: BulkRowsIn):
    if not AnnotationService.get_project(pid):
        raise HTTPException(status_code=404, detail="project not found")
    from ..services.project_dataset import ProjectDatasetService

    try:
        n = ProjectDatasetService.append_rows(pid, body.rows)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"status": "ok", "imported": n}


@router.get("/projects/{pid}/next-row", tags=["Rows & Annotations"])
def next_row(pid: str, user_id: str):
    p = AnnotationService.get_project(pid)
    if not p:
        raise HTTPException(status_code=404, detail="project not found")
    from ..services.project_dataset import ProjectDatasetService

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
        raise HTTPException(
            status_code=404, detail="dataset source no longer available"
        )
    return {"index": idx, "row": row}


@router.get("/projects/{pid}/rows/{row_index}", tags=["Rows & Annotations"])
def get_project_row(pid: str, row_index: int, user_id: str):
    result = AnnotationService.get_project_row(pid, row_index, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="row not found")
    return result


@router.get("/projects/{pid}/rows/{row_index}/next", tags=["Rows & Annotations"])
def next_project_row(pid: str, row_index: int, user_id: str):
    result = AnnotationService.navigate_row(pid, user_id, row_index, 1)
    if not result:
        raise HTTPException(status_code=404, detail="no next row")
    return result


@router.get("/projects/{pid}/rows/{row_index}/prev", tags=["Rows & Annotations"])
def prev_project_row(pid: str, row_index: int, user_id: str):
    result = AnnotationService.navigate_row(pid, user_id, row_index, -1)
    if not result:
        raise HTTPException(status_code=404, detail="no previous row")
    return result


@router.post("/projects/{pid}/annotate", tags=["Rows & Annotations"], status_code=201)
def submit_annotation(pid: str, body: AnnotateRequest):
    AnnotationService.submit_annotation(pid, body.row_index, body.user_id, body.data)
    return {"status": "ok"}


@router.get("/projects/{pid}/annotations/{row_index}", tags=["Rows & Annotations"])
def get_annotation(pid: str, row_index: int, user_id: str):
    ann = AnnotationService.get_annotation(pid, row_index, user_id)
    if not ann:
        raise HTTPException(status_code=404, detail="annotation not found")
    return ann


@router.get(
    "/projects/{pid}/members", tags=["Members"], response_model=list[ProjectMemberOut]
)
def list_members(pid: str, user_id: str):
    _require_project(pid)
    _require_member_view(pid, user_id)
    return PermissionService.list_members(pid)


@router.get(
    "/projects/{pid}/member-candidates",
    tags=["Members"],
    response_model=list[ProjectMemberCandidate],
)
def list_member_candidates(pid: str, user_id: str, q: str = ""):
    _require_project(pid)
    _require_project_manager(pid, user_id)
    return PermissionService.list_candidates(pid, q)


@router.put("/projects/{pid}/members", tags=["Members"], status_code=200)
def set_member(pid: str, body: ProjectMemberIn):
    """Add a user to the project, or change an existing member's role."""
    if body.role not in PROJECT_ROLES:
        raise HTTPException(
            status_code=400, detail=f"role must be one of {PROJECT_ROLES}"
        )
    _require_project(pid)
    _require_project_manager(pid, body.actor)
    if PermissionService.assign_role(pid, body.user_id, body.role) is None:
        raise HTTPException(status_code=404, detail="user not found")
    return {"status": "ok", "user_id": body.user_id, "role": body.role}


@router.delete("/projects/{pid}/members/{member_id}", tags=["Members"])
def remove_member(pid: str, member_id: str, user_id: str):
    _require_project(pid)
    _require_project_manager(pid, user_id)
    if PermissionService.get_project_role(pid, member_id) == "project_admin":
        # Never strand a project without an admin, unless the caller is a
        # global admin (who can always manage the project afterwards).
        if PermissionService.count_admins(
            pid
        ) <= 1 and not PermissionService.is_system_admin(user_id):
            raise HTTPException(
                status_code=409, detail="project must keep at least one project admin"
            )
    if not PermissionService.revoke(pid, member_id):
        raise HTTPException(status_code=404, detail="not a project member")
    return {"status": "removed", "user_id": member_id}


@router.get("/projects/{pid}/annotations/export", tags=["Rows & Annotations"])
def export_annotations(pid: str, format: str = "parquet"):
    data = AnnotationService.export_annotations(pid, format=format)
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename=annotations.{format}"},
    )


@router.delete("/projects/{pid}", tags=["Projects"])
def delete_project(pid: str, user_id: str):
    _require_project_manager(pid, user_id)
    if not AnnotationService.delete_project(pid):
        raise HTTPException(status_code=404, detail="project not found")
    return {"status": "deleted"}


@router.delete("/projects/{pid}/annotations/bulk", tags=["Rows & Annotations"])
def delete_annotations_bulk(pid: str, user_id: str, body: BulkClearRequest):
    if not AnnotationService.get_project(pid):
        raise HTTPException(status_code=404, detail="project not found")
    _require_project_manager(pid, user_id)
    from ..services.annotation_service import _resolve_matching_indices

    indices = _resolve_matching_indices(pid, user_id, body.filter)
    n = AnnotationService.delete_annotations_for_rows(pid, indices)
    return {"status": "deleted", "rows": n}


@router.delete("/projects/{pid}/ml-annotations/bulk", tags=["AI Prefill"])
def delete_ml_annotations_bulk(pid: str, user_id: str, body: BulkClearRequest):
    if not AnnotationService.get_project(pid):
        raise HTTPException(status_code=404, detail="project not found")
    _require_project_manager(pid, user_id)
    from ..services.annotation_service import _resolve_matching_indices

    indices = _resolve_matching_indices(pid, user_id, body.filter)
    n = AnnotationService.delete_ml_annotations_for_rows(pid, indices)
    return {"status": "deleted", "rows": n}


@router.delete("/projects/{pid}/annotations/{row_index}", tags=["Rows & Annotations"])
def delete_annotation(pid: str, row_index: int, user_id: str | None = None):
    if not AnnotationService.get_project(pid):
        raise HTTPException(status_code=404, detail="project not found")
    n = AnnotationService.delete_annotation(pid, row_index, user_id)
    return {"status": "deleted", "rows": n}


@router.delete("/projects/{pid}/annotations", tags=["Rows & Annotations"])
def delete_all_annotations(pid: str):
    if not AnnotationService.get_project(pid):
        raise HTTPException(status_code=404, detail="project not found")
    n = AnnotationService.delete_all_annotations(pid)
    return {"status": "deleted", "rows": n}


@router.delete("/projects/{pid}/ml-annotations/{row_index}", tags=["AI Prefill"])
def delete_ml_annotation(pid: str, row_index: int):
    if not AnnotationService.get_project(pid):
        raise HTTPException(status_code=404, detail="project not found")
    n = AnnotationService.delete_ml_annotation(pid, row_index)
    return {"status": "deleted", "rows": n}


@router.delete("/projects/{pid}/ml-annotations", tags=["AI Prefill"])
def delete_all_ml_annotations(pid: str):
    if not AnnotationService.get_project(pid):
        raise HTTPException(status_code=404, detail="project not found")
    n = AnnotationService.delete_all_ml_annotations(pid)
    return {"status": "deleted", "rows": n}


# ---- ML Backend endpoints ----


@router.post("/projects/{pid}/ml-prefill", tags=["AI Prefill"])
def ml_prefill(pid: str, body: MLPrefillRequest):
    result = prefill_row(pid, body.row_index)
    return result


@router.post("/projects/{pid}/ml-batch", tags=["AI Prefill"])
def ml_batch(pid: str, body: MLBatchRequest):
    result = batch_prefill(pid, body.row_indices)
    return result


@router.get("/projects/{pid}/ml-annotations/{row_index}", tags=["AI Prefill"])
def ml_annotation(pid: str, row_index: int):
    ann = get_ml_annotation(pid, row_index)
    if not ann:
        raise HTTPException(status_code=404, detail="ML annotation not found")
    return ann
