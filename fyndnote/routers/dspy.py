from fastapi import APIRouter, HTTPException

from .. import config
from ..schemas import DspyConfigUpdate, DspyTestRequest, DspyTrainRequest
from ..services import dspy_service
from ..services.annotation_service import AnnotationService
from ..services.dataset_service import DatasetService
from ..services.template_service import TemplateService

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


@router.get("/projects/{pid}/dspy")
def get_config(pid: str):
    project = _project_or_404(pid)
    _, cfg = dspy_service._ensure_config(pid, project)
    if cfg is None:
        raise HTTPException(status_code=404, detail="project not found")
    return _response(pid, project, cfg)


@router.put("/projects/{pid}/dspy")
def update_config(pid: str, body: DspyConfigUpdate):
    project = _project_or_404(pid)
    _, cfg = dspy_service._ensure_config(pid, project)
    if cfg is None:
        raise HTTPException(status_code=404, detail="project not found")

    if body.instruction is not None:
        cfg["instruction"] = body.instruction
    if body.input_fields is not None:
        cfg["input_fields"] = body.input_fields
    if body.output_fields is not None:
        cfg["output_fields"] = body.output_fields
    # Stored tuning state overwrites the built signature on load — keep it
    # honoring the (possibly edited) instruction/descriptions.
    cfg = dspy_service.rewrite_state(cfg)
    dspy_service.DspyProgramStore.save(pid, cfg)

    if body.model is not None or body.api_base is not None:
        AnnotationService.update_project(
            pid,
            project["name"],
            dspy_model=body.model,
            dspy_api_base=body.api_base,
        )
        project = _project_or_404(pid)
    return _response(pid, project, cfg)


@router.post("/projects/{pid}/dspy/derive")
def derive(pid: str):
    project = _project_or_404(pid)
    template = TemplateService.get(project["template_id"])
    source = template["source"] if template else ""
    try:
        columns = list(DatasetService._load_ds(project["dataset_id"]).column_names)
    except Exception:
        columns = []
    cfg = dspy_service.derive_config(source, columns)
    # Schema changed: tuning state is invalid.
    cfg["program_state"] = None
    dspy_service.DspyProgramStore.save(pid, cfg)
    return _response(pid, project, cfg)


@router.post("/projects/{pid}/dspy/test")
def test(pid: str, body: DspyTestRequest):
    _project_or_404(pid)
    try:
        return dspy_service.test_predict(pid, body.row_index)
    except dspy_service.DspyNotConfigured as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
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


@router.post("/projects/{pid}/dspy/reset")
def reset(pid: str):
    project = _project_or_404(pid)
    cfg = dspy_service.reset(pid)
    if cfg is None:
        _, cfg = dspy_service._ensure_config(pid, project)
    if cfg is None:
        raise HTTPException(status_code=404, detail="project not found")
    return _response(pid, project, cfg)
