from fastapi import APIRouter, HTTPException

from .. import config
from ..schemas import (
    DspyConfigUpdate,
    DspyLabelRequest,
    DspyRevertRequest,
    DspyTestRequest,
    DspyTrainRequest,
)
from ..services import dspy_service
from ..services.annotation_service import AnnotationService

router = APIRouter()


def _project_or_404(pid: str) -> dict:
    project = AnnotationService.get_project(pid)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def _response(pid: str, project: dict, cfg: dict) -> dict:
    out = dict(cfg)
    out["model"] = project["dspy_model"] or config.DSPY_DEFAULT_MODEL
    out["api_base"] = project["dspy_api_base"] or config.LLM_API_BASE
    out["annotator"] = project["ml_annotator"]
    out["ml_enabled"] = bool(project["ml_enabled"])
    out["ml_mode"] = project["ml_mode"]
    out["ml_type"] = project.get("ml_type") or "external"
    out["llm_key_set"] = bool(config.LLM_API_KEY)
    out["unsupported"] = [
        f["name"]
        for f in cfg.get("output_fields", [])
        if f.get("kind") == "unsupported"
    ]
    return out


def _save_endpoints(pid: str, body: DspyConfigUpdate) -> dict:
    """Apply a config PUT: prompt edit as a new version + model/endpoint row."""
    _project_or_404(pid)
    cfg = dspy_service.save_config(
        pid,
        instruction=body.instruction,
        input_fields=body.input_fields,
        output_fields=body.output_fields,
        user_id=body.user_id,
    )
    if cfg is None:
        raise HTTPException(status_code=404, detail="project not found")
    if body.model is not None or body.api_base is not None:
        project = AnnotationService.update_project(
            pid,
            AnnotationService.get_project(pid)["name"],
            dspy_model=body.model,
            dspy_api_base=body.api_base,
        )
    else:
        project = AnnotationService.get_project(pid)
    return _response(pid, project, cfg)


@router.get("/projects/{pid}/dspy")
def get_config(pid: str):
    project = _project_or_404(pid)
    _, cfg = dspy_service._ensure_config(pid, project)
    if cfg is None:
        raise HTTPException(status_code=404, detail="project not found")
    return _response(pid, project, cfg)


@router.put("/projects/{pid}/dspy")
def update_config(pid: str, body: DspyConfigUpdate):
    return _save_endpoints(pid, body)


@router.post("/projects/{pid}/dspy/derive")
def derive(pid: str, body: DspyLabelRequest | None = None):
    project = _project_or_404(pid)
    cfg = dspy_service.derive_project(pid, user_id=(body.user_id if body else None))
    if cfg is None:
        raise HTTPException(status_code=404, detail="project not found")
    return _response(pid, project, cfg)


@router.get("/projects/{pid}/dspy/versions")
def versions(pid: str):
    _project_or_404(pid)
    _, cfg = dspy_service._ensure_config(pid)
    if cfg is None:
        raise HTTPException(status_code=404, detail="project not found")
    return {
        "active_version": cfg.get("active_version"),
        "versions": dspy_service.list_versions(pid),
    }


@router.post("/projects/{pid}/dspy/test")
def test(pid: str, body: DspyTestRequest):
    _project_or_404(pid)
    try:
        return dspy_service.test_predict(pid, body.row_index)
    except dspy_service.DspyNotConfigured as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:  # dspy/network failures are the caller's problem
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}") from e


@router.post("/projects/{pid}/dspy/train")
def train(pid: str, body: DspyTrainRequest):
    _project_or_404(pid)
    try:
        return dspy_service.tune(pid, body.optimizer, body.max_examples)
    except dspy_service.DspyNotConfigured as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"tuning failed: {e}") from e


@router.post("/projects/{pid}/dspy/accept")
def accept(pid: str, body: DspyLabelRequest | None = None):
    _project_or_404(pid)
    cfg = dspy_service.accept_pending(
        pid,
        user_id=(body.user_id if body else None),
        label=(body.label if body else ""),
    )
    if cfg is None:
        raise HTTPException(status_code=404, detail="nothing pending")
    project = AnnotationService.get_project(pid)
    return _response(pid, project, cfg)


@router.post("/projects/{pid}/dspy/reject")
def reject(pid: str):
    _project_or_404(pid)
    cfg = dspy_service.reject_pending(pid)
    if cfg is None:
        raise HTTPException(status_code=404, detail="nothing pending")
    project = AnnotationService.get_project(pid)
    return _response(pid, project, cfg)


@router.post("/projects/{pid}/dspy/revert")
def revert(pid: str, body: DspyRevertRequest):
    _project_or_404(pid)
    cfg = dspy_service.revert(pid, body.version)
    if cfg is None:
        raise HTTPException(status_code=404, detail="version not found")
    project = AnnotationService.get_project(pid)
    return _response(pid, project, cfg)


@router.post("/projects/{pid}/dspy/reset")
def reset(pid: str, body: DspyLabelRequest | None = None):
    project = _project_or_404(pid)
    cfg = dspy_service.reset(pid, user_id=(body.user_id if body else None))
    if cfg is None:
        raise HTTPException(status_code=404, detail="project not found")
    return _response(pid, project, cfg)
