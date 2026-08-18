from pydantic import BaseModel
from typing import Any

class LoginRequest(BaseModel):
    user_id: str

class LoginResponse(BaseModel):
    user_id: str
    name: str
    global_role: str
    project_roles: dict[str, str] | None = None

class DatasetOut(BaseModel):
    id: str
    name: str
    source: str
    num_rows: int
    columns: list[dict]
    created_at: str

class TemplateOut(BaseModel):
    id: str
    name: str
    source: str
    project_id: str | None = None
    validated: bool = False
    created_at: str
    updated_at: str

class TemplateCreate(BaseModel):
    name: str
    source: str
    validated: bool = False

class ProjectOut(BaseModel):
    id: str
    name: str
    dataset_id: str
    template_id: str
    color: str = '#1976d2'
    tags: str = ''
    instructions: str = ''
    created_at: str

class ProjectDetail(BaseModel):
    id: str
    name: str
    dataset_id: str
    template_id: str
    template_source: str
    num_rows: int
    progress: dict
    color: str = '#1976d2'
    tags: str = ''
    instructions: str = ''

class RowOut(BaseModel):
    index: int
    row: dict[str, Any]

class AnnotateRequest(BaseModel):
    row_index: int
    user_id: str
    data: dict[str, Any]

class AnnotationOut(BaseModel):
    row_index: int
    user_id: str
    data: dict[str, Any]
    created_at: str

class BrowseRow(BaseModel):
    index: int
    preview: dict
    annotations: list | None = None
    annotation_status: dict

class FilterExpression(BaseModel):
    field: str       # e.g. "data.text", "annotation.sentiment", "annotations.count"
    operator: str    # =, !=, ~=, >, >=, <, <=
    value: str       # the raw value as a string
    conjunction: str = "AND"  # AND or OR

class BrowseRowsRequest(BaseModel):
    user_id: str
    page: int = 1
    per_page: int = 50
    filter: list[FilterExpression] = []

class MLPrefillRequest(BaseModel):
    row_index: int

class MLPrefillResponse(BaseModel):
    row_index: int
    annotation: dict[str, Any] | None = None
    annotator: str | None = None

class MLBatchRequest(BaseModel):
    row_indices: list[int] | None = None

class MLBatchResponse(BaseModel):
    total: int
    succeeded: int
    failed: int

class MLAnnotationOut(BaseModel):
    row_index: int
    annotator: str
    data: dict[str, Any]
    created_at: str
