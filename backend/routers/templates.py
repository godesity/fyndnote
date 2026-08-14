from fastapi import APIRouter, HTTPException
from schemas import TemplateCreate, TemplateOut
from services.template_service import TemplateService

router = APIRouter()

@router.get("/templates")
def list_templates():
    return {"templates": TemplateService.list_all()}

@router.get("/templates/{tid}")
def get_template(tid: str):
    t = TemplateService.get(tid)
    if not t:
        raise HTTPException(status_code=404, detail="template not found")
    return t

@router.post("/templates", status_code=201)
def create_template(body: TemplateCreate):
    t = TemplateService.create(body.name, body.source, body.validated)
    return t

@router.put("/templates/{tid}")
def update_template(tid: str, body: dict):
    source = body.get("source")
    validated = body.get("validated")
    t = TemplateService.update(tid, source=source, validated=validated)
    if not t:
        raise HTTPException(status_code=404, detail="template not found")
    return t
