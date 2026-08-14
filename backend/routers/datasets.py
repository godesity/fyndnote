from fastapi import APIRouter, HTTPException, Response
from services.dataset_service import DatasetService

router = APIRouter()

@router.get("/datasets")
def list_datasets():
    return {"datasets": DatasetService.list_datasets()}

@router.post("/datasets/load")
def load_dataset(body: dict):
    source = body["source"]
    split = body.get("split", "train")
    name = body.get("name")
    meta = DatasetService.load(source, split, name)
    return meta

@router.get("/datasets/{ds_id}/rows/{index}")
def get_row(ds_id: str, index: int):
    try:
        row = DatasetService.get_row(ds_id, index)
        return {"index": index, "row": row}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/datasets/{ds_id}/rows/{index}/columns/{column}")
def get_binary_column(ds_id: str, index: int, column: str):
    try:
        data, content_type = DatasetService.get_binary_column(ds_id, index, column)
        return Response(content=data, media_type=content_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
