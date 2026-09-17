from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from ..services.dataset_service import DatasetNameConflict, DatasetService

router = APIRouter()


def _conflict_payload(e: DatasetNameConflict) -> dict:
    return {
        "detail": f"a dataset named '{e.name}' already exists",
        "suggested_name": e.suggested,
    }


@router.get("/datasets")
def list_datasets():
    return {"datasets": DatasetService.list_datasets()}


@router.get("/datasets/name-available")
def check_dataset_name(name: str | None = None, source: str | None = None):
    """Pre-flight for the load/upload forms: is this display label free?

    ``source`` is what the UI has typed so far, so the check works before the
    user picked a name: the derived default is checked instead.
    """
    base = (name or "").strip()
    if not base:
        if not (source or "").strip():
            raise HTTPException(status_code=400, detail="name or source is required")
        source = source.strip()
        base = DatasetService.default_name(source)
    suggested = DatasetService.unique_name(base)
    return {"name": base, "available": suggested == base, "suggested_name": suggested}


@router.get("/datasets/{ds_id}/details")
def dataset_details(ds_id: str):
    details = DatasetService.dataset_details(ds_id)
    if details is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return details


@router.post("/datasets/load")
def load_dataset(body: dict):
    source = body["source"]
    split = body.get("split", "train")
    name = body.get("name")
    try:
        return DatasetService.load(source, split, name, alias=body.get("alias"))
    except DatasetNameConflict as e:
        raise HTTPException(status_code=409, detail=_conflict_payload(e)) from e


@router.get("/datasets/{ds_id}/rows/{index}")
def get_row(ds_id: str, index: int):
    try:
        row = DatasetService.get_row(ds_id, index)
        return {"index": index, "row": row}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/datasets/upload", status_code=201)
async def upload_dataset(file: UploadFile = File(...), alias: str | None = Form(None)):
    content = await file.read()
    try:
        return DatasetService.load_upload(file.filename, content, alias=alias)
    except DatasetNameConflict as e:
        raise HTTPException(status_code=409, detail=_conflict_payload(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/datasets/{ds_id}/rows/{index}/columns/{column}")
def get_binary_column(ds_id: str, index: int, column: str):
    try:
        data, content_type = DatasetService.get_binary_column(ds_id, index, column)
        return Response(content=data, media_type=content_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
