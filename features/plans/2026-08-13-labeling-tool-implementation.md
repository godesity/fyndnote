# Labeling Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a general-purpose ML dataset annotation tool with a FastAPI backend, React frontend, SQLite storage, and react-live template engine.

**Architecture:** Python FastAPI backend serves REST API for datasets (HF `datasets`), templates (file-based JSON), and annotations (SQLite). React SPA renders user-supplied labeling templates in a react-live sandbox. Six predefined annotation widgets auto-register state via AnnotationContext. Annotators and project admins have role-gated access to views.

**Tech Stack:** Python 3.11+, FastAPI, Hugging Face `datasets`, SQLite (via stdlib `sqlite3`), PyArrow, React 18, TypeScript, Vite, react-live

---

## File Structure

```
backend/
  main.py                     # FastAPI app entry, CORS, lifespan
  config.py                   # Settings (paths, defaults)
  database.py                 # SQLite connection, schema init
  schemas.py                  # Pydantic request/response models
  routers/
    auth.py                   # POST /auth/login
    datasets.py               # GET/POST /datasets, GET /datasets/:id/rows/:index, GET /datasets/:id/rows/:index/columns/:col
    templates.py              # CRUD /templates
    projects.py               # CRUD /projects, GET /projects/:id/rows, GET /projects/:id/next-row, POST /projects/:id/annotate, GET /projects/:id/annotations/:row_index, GET /projects/:id/annotations/export
  services/
    dataset_service.py        # HF datasets load + cache
    annotation_service.py     # SQLite queries for annotations, progress, ordering
    template_service.py       # JSON file CRUD for templates

frontend/
  src/
    main.tsx                  # React entry
    App.tsx                   # Router + auth gate
    api/
      client.ts               # fetch wrapper, base URL
    context/
      AuthContext.tsx          # user state, login
      AnnotationContext.tsx    # registerField, getAnnotations
    views/
      LoginView.tsx           # user ID input
      ProjectListView.tsx     # list of accessible projects
      SetupView.tsx           # dataset selector + template editor (admin)
      LabelView.tsx           # react-live preview + submit (annotator)
      BrowseView.tsx          # row grid + detail panel
    components/
      RowNavigator.tsx        # prev/next, progress bar
      SubmitButton.tsx        # calls getAnnotations, POSTs to backend
      RowGrid.tsx             # paginated grid with status badges
      RowDetail.tsx           # selected row preview with annotations
      AnnotationStatusBadge.tsx # by_me / by_any indicator
    widgets/
      SelectField.tsx
      CheckboxGroup.tsx
      BBoxField.tsx
      NERField.tsx
      TextField.tsx
      RatingField.tsx

tests/
  backend/
    test_auth.py
    test_datasets.py
    test_templates.py
    test_projects.py
    test_annotation_service.py
```

---

### Task 1: Backend skeleton — FastAPI app, config, database, schemas

**Files:**
- Create: `backend/main.py`
- Create: `backend/config.py`
- Create: `backend/database.py`
- Create: `backend/schemas.py`

- [ ] **Step 1: Write config.py**

```python
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATABASE_PATH = DATA_DIR / "labeling.db"
DATASETS_DIR = DATA_DIR / "datasets"
TEMPLATES_DIR = DATA_DIR / "templates"
```

- [ ] **Step 2: Write database.py with schema init**

```python
import sqlite3
from config import DATABASE_PATH

def get_db() -> sqlite3.Connection:
    db = sqlite3.connect(str(DATABASE_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            global_role TEXT NOT NULL CHECK(global_role IN ('system_admin','annotator')),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS projects (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            dataset_id  TEXT NOT NULL,
            template_id TEXT NOT NULL,
            salt        TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS project_permissions (
            user_id    TEXT NOT NULL REFERENCES users(id),
            project_id TEXT NOT NULL REFERENCES projects(id),
            role       TEXT NOT NULL CHECK(role IN ('project_admin','annotator')),
            PRIMARY KEY (user_id, project_id)
        );
        CREATE TABLE IF NOT EXISTS annotations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  TEXT NOT NULL REFERENCES projects(id),
            row_index   INTEGER NOT NULL,
            user_id     TEXT NOT NULL REFERENCES users(id),
            data        TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, row_index, user_id)
        );
    """)
    db.commit()
    db.close()

def seed_from_json():
    import json
    seed_file = DATABASE_PATH.parent / "users.json"
    if not seed_file.exists():
        return
    db = get_db()
    existing = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if existing > 0:
        db.close()
        return
    with open(seed_file) as f:
        data = json.load(f)
    for user in data["users"]:
        db.execute(
            "INSERT OR IGNORE INTO users (id, name, global_role) VALUES (?, ?, ?)",
            (user["id"], user["name"], user["global_role"])
        )
        for project_id, role in user.get("project_roles", {}).items():
            db.execute(
                "INSERT OR IGNORE INTO project_permissions (user_id, project_id, role) VALUES (?, ?, ?)",
                (user["id"], project_id, role)
            )
    db.commit()
    db.close()
```

- [ ] **Step 3: Write schemas.py (Pydantic models)**

```python
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
    created_at: str

class ProjectDetail(BaseModel):
    id: str
    name: str
    dataset_id: str
    template_id: str
    template_source: str
    num_rows: int
    progress: dict

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
```

- [ ] **Step 4: Write main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db, seed_from_json

app = FastAPI(title="Labeling Tool")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()
    seed_from_json()

# Import routers after app creation to avoid circular imports
from routers import auth, datasets, templates, projects
app.include_router(auth.router, prefix="/api/v1")
app.include_router(datasets.router, prefix="/api/v1")
app.include_router(templates.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
```

- [ ] **Step 5: Create init files**

```python
# backend/routers/__init__.py — empty
# backend/services/__init__.py — empty
```

- [ ] **Step 6: Verify startup**

Run: `cd backend && pip install fastapi uvicorn pydantic && python -c "from main import app; print('OK')"`
Expected: OK

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat: backend skeleton with FastAPI, SQLite, schema"
```

---

### Task 2: Backend — Auth router

**Files:**
- Create: `backend/routers/auth.py`
- Test: `tests/backend/test_auth.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_login_known_user():
    resp = client.post("/api/v1/auth/login", json={"user_id": "alice"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "alice"
    assert data["global_role"] == "system_admin"

def test_login_unknown_user():
    resp = client.post("/api/v1/auth/login", json={"user_id": "unknown"})
    assert resp.status_code == 401

def test_login_returns_project_roles():
    resp = client.post("/api/v1/auth/login", json={"user_id": "bob"})
    assert resp.status_code == 200
    assert resp.json()["project_roles"] is not None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && pytest ../tests/backend/test_auth.py -v`
Expected: FAIL (import errors, router not defined)

- [ ] **Step 3: Write auth router**

```python
from fastapi import APIRouter, HTTPException
from database import get_db
from schemas import LoginRequest, LoginResponse

router = APIRouter()

@router.post("/auth/login", response_model=LoginResponse)
def login(req: LoginRequest):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (req.user_id,)).fetchone()
    db.close()
    if not user:
        raise HTTPException(status_code=401, detail="unknown_user")

    perms = db.execute(
        "SELECT project_id, role FROM project_permissions WHERE user_id = ?",
        (req.user_id,)
    ).fetchall()
    project_roles = {p["project_id"]: p["role"] for p in perms} if perms else None

    return LoginResponse(
        user_id=user["id"],
        name=user["name"],
        global_role=user["global_role"],
        project_roles=project_roles,
    )
```

- [ ] **Step 4: Run tests again**

Run: `cd backend && pytest ../tests/backend/test_auth.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routers/auth.py tests/backend/test_auth.py
git commit -m "feat: auth router with login endpoint"
```

---

### Task 3: Backend — Dataset service and router

**Files:**
- Create: `backend/services/dataset_service.py`
- Create: `backend/routers/datasets.py`
- Test: `tests/backend/test_datasets.py`

- [ ] **Step 1: Write dataset_service.py**

```python
import uuid
import json
from pathlib import Path
from datasets import load_dataset, Dataset, Image as HfImage, Audio
from config import DATASETS_DIR

class DatasetService:
    _instances: dict[str, Dataset] = {}

    @classmethod
    def load(cls, source: str, split: str = "train", name: str = None) -> dict:
        ds = load_dataset(source, name, split=split)
        ds_id = str(uuid.uuid4())
        cls._instances[ds_id] = ds

        meta = {
            "id": ds_id,
            "source": source,
            "name": name,
            "split": split,
            "num_rows": len(ds),
            "columns": [{"name": col, "type": str(ds.features[col])} for col in ds.column_names],
            "created_at": str(ds_id),
        }
        meta_dir = DATASETS_DIR / ds_id
        meta_dir.mkdir(parents=True, exist_ok=True)
        with open(meta_dir / "meta.json", "w") as f:
            json.dump(meta, f, indent=2)
        return meta

    @classmethod
    def list_datasets(cls) -> list[dict]:
        if not DATASETS_DIR.exists():
            return []
        result = []
        for d in DATASETS_DIR.iterdir():
            meta_file = d / "meta.json"
            if meta_file.exists():
                with open(meta_file) as f:
                    result.append(json.load(f))
        return result

    @classmethod
    def get_row(cls, ds_id: str, index: int) -> dict:
        ds = cls._instances.get(ds_id)
        if ds is None:
            meta_path = DATASETS_DIR / ds_id / "meta.json"
            if not meta_path.exists():
                raise ValueError("Dataset not found")
            with open(meta_path) as f:
                meta = json.load(f)
            ds = load_dataset(meta["source"], meta["name"], split=meta["split"])
            cls._instances[ds_id] = ds
        row = ds[index]
        serialized = {}
        for col, val in row.items():
            if isinstance(val, HfImage):
                serialized[col] = f"/api/v1/datasets/{ds_id}/rows/{index}/columns/{col}"
            elif isinstance(val, Audio):
                serialized[col] = f"/api/v1/datasets/{ds_id}/rows/{index}/columns/{col}"
            elif isinstance(val, dict) or isinstance(val, list):
                serialized[col] = val
            else:
                serialized[col] = val
        return serialized

    @classmethod
    def get_binary_column(cls, ds_id: str, index: int, column: str) -> tuple[bytes, str]:
        ds = cls._instances.get(ds_id)
        if ds is None:
            raise ValueError("Dataset not loaded")
        val = ds[index][column]
        content_type = "application/octet-stream"
        if isinstance(val, HfImage):
            from io import BytesIO
            buf = BytesIO()
            val.save(buf, format="JPEG")
            buf.seek(0)
            content_type = "image/jpeg"
            return buf.read(), content_type
        if isinstance(val, Audio):
            raw = val["array"].tobytes()
            content_type = "audio/wav"
            return raw, content_type
        return str(val).encode(), content_type
```

- [ ] **Step 2: Write datasets router**

```python
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
```

- [ ] **Step 3: Write test**

```python
def test_list_datasets_empty():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    resp = client.get("/api/v1/datasets")
    assert resp.status_code == 200

def test_load_dataset():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    resp = client.post("/api/v1/datasets/load", json={"source": "imdb", "split": "train"})
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["num_rows"] > 0
```

- [ ] **Step 4: Install dependencies and run**

Run: `pip install datasets pyarrow Pillow && cd backend && pytest ../tests/backend/test_datasets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/dataset_service.py backend/routers/datasets.py tests/backend/test_datasets.py
git commit -m "feat: dataset loading, row access, binary column serving"
```

---

### Task 4: Backend — Template router

**Files:**
- Create: `backend/services/template_service.py`
- Create: `backend/routers/templates.py`
- Test: `tests/backend/test_templates.py`

- [ ] **Step 1: Write template_service.py**

```python
import uuid
import json
from pathlib import Path
from datetime import datetime
from config import TEMPLATES_DIR

class TemplateService:
    @staticmethod
    def _path(tid: str) -> Path:
        return TEMPLATES_DIR / f"{tid}.json"

    @classmethod
    def create(cls, name: str, source: str, validated: bool = False) -> dict:
        tid = str(uuid.uuid4())
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.utcnow().isoformat()
        data = {
            "id": tid,
            "name": name,
            "source": source,
            "project_id": None,
            "validated": validated,
            "created_at": now,
            "updated_at": now,
        }
        with open(cls._path(tid), "w") as f:
            json.dump(data, f, indent=2)
        return data

    @classmethod
    def get(cls, tid: str) -> dict | None:
        path = cls._path(tid)
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    @classmethod
    def update(cls, tid: str, source: str = None, validated: bool = None) -> dict | None:
        data = cls.get(tid)
        if data is None:
            return None
        if source is not None:
            data["source"] = source
        if validated is not None:
            data["validated"] = validated
        data["updated_at"] = datetime.utcnow().isoformat()
        with open(cls._path(tid), "w") as f:
            json.dump(data, f, indent=2)
        return data

    @classmethod
    def list_all(cls) -> list[dict]:
        if not TEMPLATES_DIR.exists():
            return []
        result = []
        for f in TEMPLATES_DIR.iterdir():
            if f.suffix == ".json":
                with open(f) as fp:
                    result.append(json.load(fp))
        return result
```

- [ ] **Step 2: Write templates router**

```python
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
```

- [ ] **Step 3: Write test**

```python
def test_create_and_get_template():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)
    resp = client.post("/api/v1/templates", json={
        "name": "test", "source": "function Foo() { return null; }"
    })
    assert resp.status_code == 201
    tid = resp.json()["id"]
    resp2 = client.get(f"/api/v1/templates/{tid}")
    assert resp2.status_code == 200
    assert resp2.json()["name"] == "test"
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest ../tests/backend/test_templates.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/template_service.py backend/routers/templates.py tests/backend/test_templates.py
git commit -m "feat: template CRUD with JSON file storage"
```

---

### Task 5: Backend — Annotation service and project router

**Files:**
- Create: `backend/services/annotation_service.py`
- Create: `backend/routers/projects.py`
- Modify: `backend/schemas.py` (if missing models)
- Test: `tests/backend/test_projects.py` , `tests/backend/test_annotation_service.py`

- [ ] **Step 1: Write annotation_service.py**

```python
import uuid
import hashlib
import random
import json
from datetime import datetime
from database import get_db

class AnnotationService:
    @staticmethod
    def create_project(name: str, dataset_id: str, template_id: str) -> dict:
        db = get_db()
        pid = str(uuid.uuid4())
        salt = hashlib.sha256(f"{pid}:{name}".encode()).hexdigest()[:16]
        db.execute(
            "INSERT INTO projects (id, name, dataset_id, template_id, salt) VALUES (?, ?, ?, ?, ?)",
            (pid, name, dataset_id, template_id, salt)
        )
        db.commit()
        proj = db.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        db.close()
        return dict(proj)

    @staticmethod
    def get_project(pid: str) -> dict | None:
        db = get_db()
        p = db.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        db.close()
        return dict(p) if p else None

    @staticmethod
    def list_projects(user_id: str) -> list[dict]:
        db = get_db()
        user = db.execute("SELECT global_role FROM users WHERE id = ?", (user_id,)).fetchone()
        if user and user["global_role"] == "system_admin":
            rows = db.execute("SELECT * FROM projects").fetchall()
        else:
            rows = db.execute("""
                SELECT p.*, pp.role FROM projects p
                JOIN project_permissions pp ON pp.project_id = p.id
                WHERE pp.user_id = ?
            """, (user_id,)).fetchall()
        db.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_progress(pid: str, user_id: str) -> dict:
        db = get_db()
        any_ann = db.execute(
            "SELECT COUNT(DISTINCT row_index) FROM annotations WHERE project_id = ?", (pid,)
        ).fetchone()[0]
        by_me = db.execute(
            "SELECT COUNT(DISTINCT row_index) FROM annotations WHERE project_id = ? AND user_id = ?",
            (pid, user_id)
        ).fetchone()[0]
        total = db.execute(
            "SELECT COUNT(*) FROM annotations WHERE project_id = ?", (pid,)
        ).fetchone()[0]
        db.close()
        return {"any_annotation": any_ann, "annotated_by_me": by_me, "total_annotations": total}

    @staticmethod
    def next_row(pid: str, user_id: str, num_rows: int) -> int | None:
        db = get_db()
        salt = db.execute("SELECT salt FROM projects WHERE id = ?", (pid,)).fetchone()
        if not salt:
            db.close()
            return None
        salt = salt[0]
        indices = list(range(num_rows))
        seed = hashlib.sha256(f"{user_id}:{salt}".encode()).hexdigest()
        rng = random.Random(seed)
        rng.shuffle(indices)

        annotated = {
            r[0] for r in db.execute(
                "SELECT row_index FROM annotations WHERE project_id = ? AND user_id = ?",
                (pid, user_id)
            ).fetchall()
        }
        db.close()
        for idx in indices:
            if idx not in annotated:
                return idx
        return None

    @staticmethod
    def submit_annotation(pid: str, row_index: int, user_id: str, data: dict):
        db = get_db()
        now = datetime.utcnow().isoformat()
        db.execute("""
            INSERT INTO annotations (project_id, row_index, user_id, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, row_index, user_id)
            DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at
        """, (pid, row_index, user_id, json.dumps(data), now, now))
        db.commit()
        db.close()

    @staticmethod
    def get_annotation(pid: str, row_index: int, user_id: str) -> dict | None:
        db = get_db()
        row = db.execute(
            "SELECT * FROM annotations WHERE project_id = ? AND row_index = ? AND user_id = ?",
            (pid, row_index, user_id)
        ).fetchone()
        db.close()
        if not row:
            return None
        return {
            "row_index": row["row_index"],
            "user_id": row["user_id"],
            "data": json.loads(row["data"]),
            "created_at": row["created_at"],
        }

    @staticmethod
    def browse_rows(pid: str, user_id: str, page: int, per_page: int, status: str, include_annotations: bool) -> tuple:
        db = get_db()
        project = db.execute("SELECT dataset_id FROM projects WHERE id = ?", (pid,)).fetchone()
        if not project:
            db.close()
            return [], 0
        num_rows = 0  # Will be set from dataset metadata
        db.close()
        # Return empty placeholder — actual implementation needs dataset row count
        return [], num_rows

    @staticmethod
    def export_annotations(pid: str):
        db = get_db()
        rows = db.execute(
            "SELECT row_index, user_id, data, created_at, updated_at FROM annotations WHERE project_id = ?",
            (pid,)
        ).fetchall()
        db.close()
        import pyarrow as pa
        import pyarrow.parquet as pq
        table = pa.Table.from_pylist([
            {
                "row_index": r["row_index"],
                "user_id": r["user_id"],
                "data": r["data"].encode(),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ])
        buf = pa.BufferOutputStream()
        pq.write_table(table, buf)
        return buf.getvalue().to_pybytes()
```

- [ ] **Step 2: Write projects router**

```python
from fastapi import APIRouter, HTTPException, Response
from schemas import AnnotateRequest
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
        body["name"], body["dataset_id"], body["template_id"]
    )
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

@router.get("/projects/{pid}/rows")
def browse_rows(pid: str, user_id: str, page: int = 1, per_page: int = 50,
                status: str = "all", include_annotations: int = 0):
    rows, total = AnnotationService.browse_rows(pid, user_id, page, per_page, status, bool(include_annotations))
    return {"rows": rows, "total": total, "page": page, "per_page": per_page}

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
    data = AnnotationService.export_annotations(pid)
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
```

Note: Add `from database import get_db` at top of projects.py router file.

- [ ] **Step 3: Write annotation service test**

```python
def test_create_project_and_submit_annotation():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    # Create a template first
    tresp = client.post("/api/v1/templates", json={
        "name": "test", "source": "function T() { return null; }"
    })
    tid = tresp.json()["id"]

    # Load dataset
    dresp = client.post("/api/v1/datasets/load", json={"source": "imdb", "split": "train"})
    did = dresp.json()["id"]

    # Create project
    presp = client.post("/api/v1/projects", json={
        "name": "test-proj", "dataset_id": did, "template_id": tid
    })
    assert presp.status_code == 201
    pid = presp.json()["id"]

    # Submit annotation
    aresp = client.post(f"/api/v1/projects/{pid}/annotate", json={
        "row_index": 0, "user_id": "alice", "data": {"sentiment": "positive"}
    })
    assert aresp.status_code == 201

    # Get annotation
    gresp = client.get(f"/api/v1/projects/{pid}/annotations/0?user_id=alice")
    assert gresp.status_code == 200
    assert gresp.json()["data"]["sentiment"] == "positive"
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest ../tests/backend/test_projects.py ../tests/backend/test_annotation_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/annotation_service.py backend/routers/projects.py tests/backend/test_projects.py tests/backend/test_annotation_service.py
git commit -m "feat: project CRUD, annotation submission, next-row ordering, export"
```

---

### Task 6: Frontend — React app scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api/client.ts`

- [ ] **Step 1: Scaffold with Vite**

Run: `cd frontend && npm create vite@latest . -- --template react-ts`

- [ ] **Step 2: Install dependencies**

Run: `cd frontend && npm install react-live`

- [ ] **Step 3: Write API client**

```typescript
// frontend/src/api/client.ts
const BASE = 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  login: (userId: string) =>
    request<{ user_id: string; name: string; global_role: string; project_roles: Record<string, string> | null }>(
      '/auth/login', { method: 'POST', body: JSON.stringify({ user_id: userId }) }
    ),
  listDatasets: () =>
    request<{ datasets: any[] }>('/datasets'),
  loadDataset: (source: string, split = 'train') =>
    request<any>('/datasets/load', { method: 'POST', body: JSON.stringify({ source, split }) }),
  getRow: (dsId: string, index: number) =>
    request<{ index: number; row: Record<string, any> }>(`/datasets/${dsId}/rows/${index}`),
  listTemplates: () =>
    request<{ templates: any[] }>('/templates'),
  createTemplate: (name: string, source: string) =>
    request<any>('/templates', { method: 'POST', body: JSON.stringify({ name, source }) }),
  updateTemplate: (id: string, source: string, validated?: boolean) =>
    request<any>(`/templates/${id}`, { method: 'PUT', body: JSON.stringify({ source, validated }) }),
  listProjects: (userId: string) =>
    request<{ projects: any[] }>(`/projects?user_id=${userId}`),
  createProject: (name: string, datasetId: string, templateId: string) =>
    request<any>('/projects', { method: 'POST', body: JSON.stringify({ name, dataset_id: datasetId, template_id: templateId }) }),
  getProject: (id: string, userId: string) =>
    request<any>(`/projects/${id}?user_id=${userId}`),
  nextRow: (projectId: string, userId: string) =>
    request<{ index: number | null; row: Record<string, any> | null }>(`/projects/${projectId}/next-row?user_id=${userId}`),
  submitAnnotation: (projectId: string, rowIndex: number, userId: string, data: any) =>
    request<any>(`/projects/${projectId}/annotate`, {
      method: 'POST',
      body: JSON.stringify({ row_index: rowIndex, user_id: userId, data }),
    }),
  getAnnotation: (projectId: string, rowIndex: number, userId: string) =>
    request<any>(`/projects/${projectId}/annotations/${rowIndex}?user_id=${userId}`),
  browseRows: (projectId: string, userId: string, page = 1, status = 'all', includeAnnotations = 0) =>
    request<any>(`/projects/${projectId}/rows?user_id=${userId}&page=${page}&status=${status}&include_annotations=${includeAnnotations}`),
};
```

- [ ] **Step 4: Write App.tsx with routing**

```tsx
import { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginView from './views/LoginView';
import ProjectListView from './views/ProjectListView';

function AppContent() {
  const { user } = useAuth();
  if (!user) return <LoginView />;
  return <ProjectListView />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
```

- [ ] **Step 5: Verify frontend builds**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: frontend scaffold with Vite, React, API client"
```

---

### Task 7: Frontend — Auth context, Login view

**Files:**
- Create: `frontend/src/context/AuthContext.tsx`
- Create: `frontend/src/views/LoginView.tsx`

- [ ] **Step 1: Write AuthContext**

```tsx
import { createContext, useContext, useState, ReactNode } from 'react';
import { api } from '../api/client';

interface User {
  user_id: string;
  name: string;
  global_role: string;
  project_roles: Record<string, string> | null;
}

interface AuthCtx {
  user: User | null;
  login: (userId: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthCtx>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  const login = async (userId: string) => {
    const u = await api.login(userId);
    setUser(u);
  };

  const logout = () => setUser(null);

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
```

- [ ] **Step 2: Write LoginView**

```tsx
import { useState } from 'react';
import { useAuth } from '../context/AuthContext';

export default function LoginView() {
  const { login } = useAuth();
  const [userId, setUserId] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setError('');
      await login(userId);
    } catch {
      setError('Unknown user ID');
    }
  };

  return (
    <div style={{ padding: 40, maxWidth: 400, margin: '0 auto' }}>
      <h1>Labeling Tool</h1>
      <form onSubmit={handleSubmit}>
        <input
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          placeholder="Enter your user ID"
          style={{ display: 'block', width: '100%', padding: 8, marginBottom: 8 }}
        />
        <button type="submit" style={{ padding: '8px 16px' }}>Login</button>
        {error && <p style={{ color: 'red' }}>{error}</p>}
      </form>
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/context/AuthContext.tsx frontend/src/views/LoginView.tsx
git commit -m "feat: auth context and login view"
```

---

### Task 8: Frontend — Project list view

**Files:**
- Create: `frontend/src/views/ProjectListView.tsx`

- [ ] **Step 1: Write ProjectListView**

```tsx
import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';

interface Project {
  id: string;
  name: string;
  dataset_id: string;
  template_id: string;
  created_at: string;
  role?: string;
}

export default function ProjectListView() {
  const { user, logout } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [view, setView] = useState<'list' | 'setup'>('list');

  useEffect(() => {
    if (user) {
      api.listProjects(user.user_id).then((res) => setProjects(res.projects));
    }
  }, [user]);

  if (!user) return null;

  const isAdmin = user.global_role === 'system_admin';

  return (
    <div style={{ padding: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <h1>Projects</h1>
        <div>
          <span style={{ marginRight: 12 }}>{user.name} ({user.global_role})</span>
          {isAdmin && <button onClick={() => setView('setup')}>New Project</button>}
          <button onClick={logout} style={{ marginLeft: 8 }}>Logout</button>
        </div>
      </div>

      {view === 'setup' && isAdmin ? (
        <SetupView onDone={() => setView('list')} />
      ) : (
        <div>
          {projects.length === 0 && <p>No projects available.</p>}
          {projects.map((p) => (
            <div key={p.id} style={{ border: '1px solid #ccc', padding: 12, marginBottom: 8, borderRadius: 4 }}>
              <strong>{p.name}</strong>
              {p.role && <span style={{ marginLeft: 12, color: '#666' }}>({p.role})</span>}
              <div style={{ marginTop: 8 }}>
                <button style={{ marginRight: 8 }}>Label</button>
                <button>Browse</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// Stub — will be implemented in Task 9
function SetupView({ onDone }: { onDone: () => void }) {
  return <div>Setup View (admin only) <button onClick={onDone}>Back</button></div>;
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/ProjectListView.tsx
git commit -m "feat: project list view with role-based access"
```

---

### Task 9: Frontend — Setup view (admin)

**Files:**
- Create: `frontend/src/views/SetupView.tsx`

- [ ] **Step 1: Write SetupView**

```tsx
import { useEffect, useState } from 'react';
import { LiveProvider, LiveEditor, LivePreview, LiveError } from 'react-live';
import { api } from '../api/client';
import * as widgets from '../widgets';

const scope = { ...widgets, useState, useCallback };

const DEFAULT_TEMPLATE = `function TextClassification({ row, annotations }) {
  return (
    <div style={{ padding: 20 }}>
      <h3>Classify the sentiment</h3>
      <p style={{ fontSize: 18 }}>{row.text}</p>
      <SelectField
        name="sentiment"
        labels={["positive", "negative", "neutral"]}
        defaultValue={annotations?.sentiment}
      />
    </div>
  );
}`;

export default function SetupView({ onDone }: { onDone: () => void }) {
  const [datasets, setDatasets] = useState<any[]>([]);
  const [selectedDataset, setSelectedDataset] = useState('');
  const [templateSource, setTemplateSource] = useState(DEFAULT_TEMPLATE);
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [projectName, setProjectName] = useState('');
  const [sampleRow, setSampleRow] = useState<any>(null);
  const [validated, setValidated] = useState(false);

  useEffect(() => {
    api.listDatasets().then((res) => setDatasets(res.datasets));
  }, []);

  const loadSample = async (dsId: string) => {
    setSelectedDataset(dsId);
    const row = await api.getRow(dsId, 0);
    setSampleRow(row.row);
  };

  const saveTemplate = async () => {
    if (templateId) {
      await api.updateTemplate(templateId, templateSource, validated);
    } else {
      const t = await api.createTemplate('custom', templateSource);
      setTemplateId(t.id);
    }
  };

  const createProject = async () => {
    if (!projectName || !selectedDataset || !templateId) return;
    await api.createProject(projectName, selectedDataset, templateId);
    onDone();
  };

  return (
    <div style={{ padding: 20 }}>
      <h2>Setup Project</h2>

      <div style={{ marginBottom: 20 }}>
        <h3>1. Select Dataset</h3>
        <select value={selectedDataset} onChange={(e) => loadSample(e.target.value)} style={{ width: '100%', padding: 8 }}>
          <option value="">-- Select --</option>
          {datasets.map((d) => (
            <option key={d.id} value={d.id}>{d.name} ({d.num_rows} rows)</option>
          ))}
        </select>
        <button onClick={() => {/* open load dialog */}} style={{ marginLeft: 8 }}>Load New</button>
      </div>

      <div style={{ marginBottom: 20 }}>
        <h3>2. Edit Template</h3>
        <div style={{ display: 'flex', gap: 16 }}>
          <div style={{ flex: 1 }}>
            <LiveProvider code={templateSource} scope={scope}>
              <LiveEditor onChange={setTemplateSource} />
              <LiveError />
            </LiveProvider>
          </div>
          <div style={{ flex: 1, border: '1px solid #ccc', padding: 8, minHeight: 200 }}>
            <h4>Preview</h4>
            {sampleRow ? (
              <LiveProvider code={templateSource} scope={scope} noInline={false}
                {...{ row: sampleRow, annotations: {} } as any}>
                <LivePreview />
              </LiveProvider>
            ) : <p>Select a dataset to preview</p>}
          </div>
        </div>
        <button onClick={saveTemplate} style={{ marginTop: 8 }}>
          {templateId ? 'Update Template' : 'Save Template'}
        </button>
      </div>

      <div>
        <h3>3. Create Project</h3>
        <input
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
          placeholder="Project name"
          style={{ padding: 8, width: 300 }}
        />
        <button onClick={createProject} disabled={!projectName || !selectedDataset || !templateId}
                style={{ marginLeft: 8, padding: '8px 16px' }}>
          Create Project
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/SetupView.tsx
git commit -m "feat: setup view with dataset selector, template editor, project creation"
```

---

### Task 10: Frontend — AnnotationContext

**Files:**
- Create: `frontend/src/context/AnnotationContext.tsx`

- [ ] **Step 1: Write AnnotationContext**

```tsx
import { createContext, useContext, useCallback, useRef, ReactNode } from 'react';

interface FieldRegistration {
  name: string;
  getValue: () => any;
}

interface AnnotationCtx {
  registerField: (field: FieldRegistration) => void;
  unregisterField: (name: string) => void;
  getAnnotations: () => Record<string, any>;
}

const AnnotationContext = createContext<AnnotationCtx>(null!);

export function AnnotationProvider({ children }: { children: ReactNode }) {
  const fieldsRef = useRef<Map<string, () => any>>(new Map());

  const registerField = useCallback((field: FieldRegistration) => {
    fieldsRef.current.set(field.name, field.getValue);
  }, []);

  const unregisterField = useCallback((name: string) => {
    fieldsRef.current.delete(name);
  }, []);

  const getAnnotations = useCallback(() => {
    const result: Record<string, any> = {};
    for (const [name, getValue] of fieldsRef.current.entries()) {
      result[name] = getValue();
    }
    return result;
  }, []);

  return (
    <AnnotationContext.Provider value={{ registerField, unregisterField, getAnnotations }}>
      {children}
    </AnnotationContext.Provider>
  );
}

export const useAnnotationContext = () => useContext(AnnotationContext);
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/context/AnnotationContext.tsx
git commit -m "feat: annotation context for widget state registration"
```

---

### Task 11: Frontend — Annotation widgets (SelectField, CheckboxGroup, TextField, RatingField)

**Files:**
- Create: `frontend/src/widgets/index.ts`
- Create: `frontend/src/widgets/SelectField.tsx`
- Create: `frontend/src/widgets/CheckboxGroup.tsx`
- Create: `frontend/src/widgets/TextField.tsx`
- Create: `frontend/src/widgets/RatingField.tsx`

- [ ] **Step 1: Write index.ts**

```typescript
export { default as SelectField } from './SelectField';
export { default as CheckboxGroup } from './CheckboxGroup';
export { default as BBoxField } from './BBoxField';
export { default as NERField } from './NERField';
export { default as TextField } from './TextField';
export { default as RatingField } from './RatingField';
```

- [ ] **Step 2: Write SelectField**

```tsx
import { useEffect, useState } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';

interface Props {
  name: string;
  labels: string[];
  defaultValue?: string;
}

export default function SelectField({ name, labels, defaultValue }: Props) {
  const [value, setValue] = useState(defaultValue || labels[0] || '');
  const { registerField, unregisterField } = useAnnotationContext();

  useEffect(() => {
    registerField({ name, getValue: () => value });
    return () => unregisterField(name);
  }, [name, value]);

  return (
    <select value={value} onChange={(e) => setValue(e.target.value)}
            style={{ padding: 8, fontSize: 14 }}>
      {labels.map((l) => (
        <option key={l} value={l}>{l}</option>
      ))}
    </select>
  );
}
```

- [ ] **Step 3: Write CheckboxGroup**

```tsx
import { useEffect, useState } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';

interface Props {
  name: string;
  options: string[];
  defaultValue?: string[];
}

export default function CheckboxGroup({ name, options, defaultValue }: Props) {
  const [checked, setChecked] = useState<Set<string>>(new Set(defaultValue || []));
  const { registerField, unregisterField } = useAnnotationContext();

  useEffect(() => {
    registerField({ name, getValue: () => Array.from(checked) });
    return () => unregisterField(name);
  }, [name, checked]);

  const toggle = (opt: string) => {
    const next = new Set(checked);
    if (next.has(opt)) next.delete(opt); else next.add(opt);
    setChecked(next);
  };

  return (
    <div>
      {options.map((opt) => (
        <label key={opt} style={{ display: 'block', marginBottom: 4 }}>
          <input type="checkbox" checked={checked.has(opt)} onChange={() => toggle(opt)} />
          {' '}{opt}
        </label>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Write TextField**

```tsx
import { useEffect, useState } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';

interface Props {
  name: string;
  placeholder?: string;
  multiline?: boolean;
  defaultValue?: string;
}

export default function TextField({ name, placeholder, multiline, defaultValue }: Props) {
  const [value, setValue] = useState(defaultValue || '');
  const { registerField, unregisterField } = useAnnotationContext();

  useEffect(() => {
    registerField({ name, getValue: () => value });
    return () => unregisterField(name);
  }, [name, value]);

  if (multiline) {
    return <textarea value={value} onChange={(e) => setValue(e.target.value)}
                     placeholder={placeholder} rows={4}
                     style={{ width: '100%', padding: 8 }} />;
  }
  return <input value={value} onChange={(e) => setValue(e.target.value)}
                placeholder={placeholder}
                style={{ width: '100%', padding: 8 }} />;
}
```

- [ ] **Step 5: Write RatingField**

```tsx
import { useEffect, useState } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';

interface Props {
  name: string;
  max: number;
  icon?: string;
  defaultValue?: number;
}

export default function RatingField({ name, max, defaultValue }: Props) {
  const [value, setValue] = useState(defaultValue || 0);
  const { registerField, unregisterField } = useAnnotationContext();

  useEffect(() => {
    registerField({ name, getValue: () => value });
    return () => unregisterField(name);
  }, [name, value]);

  return (
    <div style={{ display: 'flex', gap: 4 }}>
      {Array.from({ length: max }, (_, i) => (
        <button key={i} onClick={() => setValue(i + 1)}
                style={{
                  width: 32, height: 32,
                  background: i < value ? '#ffc107' : '#eee',
                  border: '1px solid #ccc', borderRadius: 4, cursor: 'pointer'
                }}>
          {i + 1}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 6: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 7: Commit**

```bash
git add frontend/src/widgets/
git commit -m "feat: annotation widgets — SelectField, CheckboxGroup, TextField, RatingField"
```

---

### Task 12: Frontend — BBoxField and NERField widgets

**Files:**
- Create: `frontend/src/widgets/BBoxField.tsx`
- Create: `frontend/src/widgets/NERField.tsx`

- [ ] **Step 1: Write BBoxField (stub — advanced rendering)**

```tsx
import { useEffect, useState, useRef } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';

interface BBox {
  x: number; y: number; w: number; h: number; category: string;
}

interface Props {
  name: string;
  imageUrl: string;
  categories: string[];
  defaultValue?: BBox[];
}

export default function BBoxField({ name, imageUrl, categories, defaultValue }: Props) {
  const [boxes, setBoxes] = useState<BBox[]>(defaultValue || []);
  const [activeCategory, setActiveCategory] = useState(categories[0]);
  const [drawing, setDrawing] = useState(false);
  const [start, setStart] = useState({ x: 0, y: 0 });
  const imgRef = useRef<HTMLImageElement>(null);
  const { registerField, unregisterField } = useAnnotationContext();

  useEffect(() => {
    registerField({ name, getValue: () => boxes });
    return () => unregisterField(name);
  }, [name, boxes]);

  const handleMouseDown = (e: React.MouseEvent) => {
    const rect = imgRef.current!.getBoundingClientRect();
    setStart({ x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height });
    setDrawing(true);
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    if (!drawing) return;
    const rect = imgRef.current!.getBoundingClientRect();
    const end = { x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height };
    const box: BBox = {
      x: Math.min(start.x, end.x),
      y: Math.min(start.y, end.y),
      w: Math.abs(end.x - start.x),
      h: Math.abs(end.y - start.y),
      category: activeCategory,
    };
    setBoxes((prev) => [...prev, box]);
    setDrawing(false);
  };

  const removeBox = (idx: number) => {
    setBoxes((prev) => prev.filter((_, i) => i !== idx));
  };

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        {categories.map((c) => (
          <button key={c} onClick={() => setActiveCategory(c)}
                  style={{ marginRight: 4, padding: '4px 8px', fontWeight: activeCategory === c ? 'bold' : 'normal' }}>
            {c}
          </button>
        ))}
      </div>
      <div style={{ position: 'relative', display: 'inline-block' }}>
        <img ref={imgRef} src={imageUrl} alt="annotate"
             onMouseDown={handleMouseDown} onMouseUp={handleMouseUp}
             style={{ maxWidth: '100%', cursor: 'crosshair' }} />
        {boxes.map((box, i) => (
          <div key={i} onClick={() => removeBox(i)}
               style={{
                 position: 'absolute',
                 left: `${box.x * 100}%`, top: `${box.y * 100}%`,
                 width: `${box.w * 100}%`, height: `${box.h * 100}%`,
                 border: '2px solid red', background: 'rgba(255,0,0,0.1)',
                 cursor: 'pointer', boxSizing: 'border-box',
               }}>
            <span style={{ background: 'red', color: 'white', fontSize: 10, padding: '1px 4px' }}>
              {box.category}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write NERField**

```tsx
import { useEffect, useState, useRef, useCallback } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';

interface Entity {
  start: number;
  end: number;
  entity: string;
}

interface Props {
  name: string;
  text: string;
  entityTypes: string[];
  defaultValue?: Entity[];
}

export default function NERField({ name, text, entityTypes, defaultValue }: Props) {
  const [entities, setEntities] = useState<Entity[]>(defaultValue || []);
  const [activeEntity, setActiveEntity] = useState(entityTypes[0]);
  const { registerField, unregisterField } = useAnnotationContext();

  useEffect(() => {
    registerField({ name, getValue: () => entities });
    return () => unregisterField(name);
  }, [name, entities]);

  const handleSelect = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return;
    const range = sel.getRangeAt(0);
    const start = range.startOffset;
    const end = range.endOffset;
    // Only works if selection is within the text node
    setEntities((prev) => [...prev, { start, end, entity: activeEntity }]);
    sel.removeAllRanges();
  }, [activeEntity]);

  // Build highlighted text with entity markers
  const sorted = [...entities].sort((a, b) => a.start - b.start);
  const parts: JSX.Element[] = [];
  let pos = 0;
  for (const e of sorted) {
    if (e.start > pos) {
      parts.push(<span key={`t-${pos}`}>{text.slice(pos, e.start)}</span>);
    }
    parts.push(
      <mark key={`e-${e.start}`} style={{ background: '#ffd700', cursor: 'pointer' }}
            onClick={() => setEntities((prev) => prev.filter((x) => x.start !== e.start))}>
        {text.slice(e.start, e.end)}
        <small style={{ marginLeft: 4, color: '#666' }}>({e.entity})</small>
      </mark>
    );
    pos = e.end;
  }
  if (pos < text.length) {
    parts.push(<span key={`t-end`}>{text.slice(pos)}</span>);
  }

  return (
    <div>
      <div style={{ marginBottom: 8 }}>
        {entityTypes.map((et) => (
          <button key={et} onClick={() => setActiveEntity(et)}
                  style={{ marginRight: 4, padding: '4px 8px', fontWeight: activeEntity === et ? 'bold' : 'normal' }}>
            {et}
          </button>
        ))}
      </div>
      <div onMouseUp={handleSelect}
           style={{ padding: 12, border: '1px solid #ccc', borderRadius: 4, lineHeight: 1.8, userSelect: 'text' }}>
        {parts}
      </div>
      <p style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
        Select text to tag as "{activeEntity}". Click a tag to remove it.
      </p>
    </div>
  );
}
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/widgets/BBoxField.tsx frontend/src/widgets/NERField.tsx
git commit -m "feat: BBoxField and NERField widgets"
```

---

### Task 13: Frontend — Label view

**Files:**
- Create: `frontend/src/views/LabelView.tsx`
- Create: `frontend/src/components/RowNavigator.tsx`
- Create: `frontend/src/components/SubmitButton.tsx`

- [ ] **Step 1: Write LabelView**

```tsx
import { useEffect, useState } from 'react';
import { LiveProvider, LivePreview } from 'react-live';
import { useAuth } from '../context/AuthContext';
import { AnnotationProvider } from '../context/AnnotationContext';
import { api } from '../api/client';
import RowNavigator from '../components/RowNavigator';
import SubmitButton from '../components/SubmitButton';
import * as widgets from '../widgets';

const scope = { ...widgets, useState, useCallback };

interface Props {
  projectId: string;
  templateSource: string;
  numRows: number;
  onBack: () => void;
}

export default function LabelView({ projectId, templateSource, numRows, onBack }: Props) {
  const { user } = useAuth();
  const [currentRow, setCurrentRow] = useState<{ index: number; row: Record<string, any> } | null>(null);
  const [annotations, setAnnotations] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  const fetchNext = async () => {
    if (!user) return;
    setLoading(true);
    const next = await api.nextRow(projectId, user.user_id);
    if (next.index !== null) {
      setCurrentRow(next);
      // Fetch existing annotations for this row
      try {
        const ann = await api.getAnnotation(projectId, next.index, user.user_id);
        setAnnotations(ann.data);
      } catch {
        setAnnotations({});
      }
    } else {
      setCurrentRow(null);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchNext();
  }, [projectId]);

  if (loading) return <div>Loading...</div>;
  if (!currentRow) return (
    <div>
      <p>All rows annotated! 🎉</p>
      <button onClick={onBack}>Back to Projects</button>
    </div>
  );

  return (
    <AnnotationProvider>
      <div style={{ padding: 20 }}>
        <button onClick={onBack} style={{ marginBottom: 16 }}>&larr; Back</button>
        <RowNavigator currentIndex={currentRow.index} numRows={numRows} />
        <div style={{ border: '1px solid #ccc', padding: 16, borderRadius: 4, marginTop: 16, minHeight: 300 }}>
          <LiveProvider code={templateSource} scope={scope}
                        {...{ row: currentRow.row, annotations } as any}>
            <LivePreview />
          </LiveProvider>
        </div>
        <SubmitButton projectId={projectId} rowIndex={currentRow.index}
                      onSubmitted={fetchNext} />
      </div>
    </AnnotationProvider>
  );
}
```

- [ ] **Step 2: Write RowNavigator**

```tsx
interface Props {
  currentIndex: number;
  numRows: number;
}

export default function RowNavigator({ currentIndex, numRows }: Props) {
  const pct = numRows > 0 ? Math.round(((currentIndex + 1) / numRows) * 100) : 0;
  return (
    <div style={{ marginBottom: 8 }}>
      <span>Row {currentIndex + 1} of {numRows}</span>
      <div style={{ width: '100%', height: 6, background: '#eee', borderRadius: 3, marginTop: 4 }}>
        <div style={{ width: `${pct}%`, height: '100%', background: '#4caf50', borderRadius: 3 }} />
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write SubmitButton**

```tsx
import { useState } from 'react';
import { useAnnotationContext } from '../context/AnnotationContext';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';

interface Props {
  projectId: string;
  rowIndex: number;
  onSubmitted: () => void;
}

export default function SubmitButton({ projectId, rowIndex, onSubmitted }: Props) {
  const { getAnnotations } = useAnnotationContext();
  const { user } = useAuth();
  const [saving, setSaving] = useState(false);

  const handleSubmit = async () => {
    if (!user) return;
    setSaving(true);
    const data = getAnnotations();
    await api.submitAnnotation(projectId, rowIndex, user.user_id, data);
    setSaving(false);
    onSubmitted();
  };

  return (
    <button onClick={handleSubmit} disabled={saving}
            style={{ marginTop: 16, padding: '10px 24px', fontSize: 16 }}>
      {saving ? 'Saving...' : 'Submit & Next'}
    </button>
  );
}
```

- [ ] **Step 4: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/LabelView.tsx frontend/src/components/RowNavigator.tsx frontend/src/components/SubmitButton.tsx
git commit -m "feat: label view with react-live rendering, row navigator, submit button"
```

---

### Task 14: Frontend — Browse view

**Files:**
- Create: `frontend/src/views/BrowseView.tsx`
- Create: `frontend/src/components/RowGrid.tsx`
- Create: `frontend/src/components/RowDetail.tsx`
- Create: `frontend/src/components/AnnotationStatusBadge.tsx`

- [ ] **Step 1: Write AnnotationStatusBadge**

```tsx
interface Props {
  byMe: boolean;
  byAny: boolean;
  annotators: string[];
}

export default function AnnotationStatusBadge({ byMe, byAny, annotators }: Props) {
  if (byMe) return <span style={{ background: '#4caf50', color: 'white', padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>Annotated by me</span>;
  if (byAny) return <span style={{ background: '#ff9800', color: 'white', padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>Annotated by {annotators.join(', ')}</span>;
  return <span style={{ background: '#eee', padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>Unannotated</span>;
}
```

- [ ] **Step 2: Write RowGrid**

```tsx
import AnnotationStatusBadge from './AnnotationStatusBadge';

interface RowEntry {
  index: number;
  preview: Record<string, any>;
  annotation_status: { by_me: boolean; by_any: boolean; annotators: string[] };
}

interface Props {
  rows: RowEntry[];
  onSelect: (index: number) => void;
  page: number;
  total: number;
  onPageChange: (page: number) => void;
}

export default function RowGrid({ rows, onSelect, page, total, onPageChange }: Props) {
  const perPage = 50;
  const totalPages = Math.ceil(total / perPage);

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 8 }}>
        {rows.map((r) => (
          <div key={r.index} onClick={() => onSelect(r.index)}
               style={{ border: '1px solid #ddd', padding: 8, borderRadius: 4, cursor: 'pointer' }}>
            <div style={{ fontSize: 12, color: '#666', marginBottom: 4 }}>Row {r.index}</div>
            <div style={{ fontSize: 13, marginBottom: 8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {JSON.stringify(r.preview).slice(0, 100)}
            </div>
            <AnnotationStatusBadge {...r.annotation_status} />
          </div>
        ))}
      </div>
      {totalPages > 1 && (
        <div style={{ marginTop: 16, display: 'flex', gap: 4 }}>
          {Array.from({ length: totalPages }, (_, i) => (
            <button key={i} onClick={() => onPageChange(i + 1)}
                    style={{ fontWeight: page === i + 1 ? 'bold' : 'normal', padding: '4px 8px' }}>
              {i + 1}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Write RowDetail**

```tsx
interface Props {
  index: number;
  row: Record<string, any>;
  annotations?: any[];
  onClose: () => void;
}

export default function RowDetail({ index, row, annotations, onClose }: Props) {
  return (
    <div style={{ position: 'fixed', top: 0, right: 0, width: 500, height: '100vh',
                  background: 'white', borderLeft: '1px solid #ccc', padding: 20, overflowY: 'auto', zIndex: 100 }}>
      <button onClick={onClose} style={{ float: 'right' }}>Close</button>
      <h3>Row {index}</h3>
      <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 4, overflow: 'auto' }}>
        {JSON.stringify(row, null, 2)}
      </pre>
      {annotations && annotations.length > 0 && (
        <>
          <h4>Annotations</h4>
          {annotations.map((a, i) => (
            <div key={i} style={{ border: '1px solid #eee', padding: 8, marginBottom: 8, borderRadius: 4 }}>
              <strong>{a.author_id}</strong>
              <pre style={{ fontSize: 12 }}>{JSON.stringify(a.data, null, 2)}</pre>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Write BrowseView**

```tsx
import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import RowGrid from '../components/RowGrid';
import RowDetail from '../components/RowDetail';

interface Props {
  projectId: string;
  onBack: () => void;
}

export default function BrowseView({ projectId, onBack }: Props) {
  const { user } = useAuth();
  const [rows, setRows] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [selectedRow, setSelectedRow] = useState<any>(null);
  const [statusFilter, setStatusFilter] = useState('all');

  useEffect(() => {
    if (!user) return;
    api.browseRows(projectId, user.user_id, page, statusFilter, 1).then((res) => {
      setRows(res.rows);
      setTotal(res.total);
    });
  }, [projectId, page, statusFilter]);

  const handleSelect = async (idx: number) => {
    setSelectedIndex(idx);
    if (!user) return;
    const project = await api.getProject(projectId, user.user_id);
    const rowData = await api.getRow(project.dataset_id, idx);
    setSelectedRow(rowData.row);
  };

  return (
    <div style={{ padding: 20 }}>
      <button onClick={onBack} style={{ marginBottom: 16 }}>&larr; Back</button>
      <h2>Browse Data</h2>

      <div style={{ marginBottom: 16 }}>
        <label>Status: </label>
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
          <option value="all">All</option>
          <option value="annotated_by_me">Annotated by me</option>
          <option value="unannotated">Unannotated</option>
        </select>
      </div>

      <RowGrid rows={rows} onSelect={handleSelect} page={page} total={total} onPageChange={setPage} />

      {selectedIndex !== null && selectedRow && (
        <RowDetail
          index={selectedIndex}
          row={selectedRow}
          annotations={rows.find((r) => r.index === selectedIndex)?.annotations}
          onClose={() => setSelectedIndex(null)}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 5: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/BrowseView.tsx frontend/src/components/RowGrid.tsx frontend/src/components/RowDetail.tsx frontend/src/components/AnnotationStatusBadge.tsx
git commit -m "feat: browse view with row grid, detail panel, status filters"
```

---

### Task 15: Wire up routing in ProjectListView

**Files:**
- Modify: `frontend/src/views/ProjectListView.tsx`

- [ ] **Step 1: Update ProjectListView to navigate between views**

```tsx
import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../api/client';
import SetupView from './SetupView';
import LabelView from './LabelView';
import BrowseView from './BrowseView';

interface Project {
  id: string;
  name: string;
  dataset_id: string;
  template_id: string;
  role?: string;
}

export default function ProjectListView() {
  const { user, logout } = useAuth();
  const [projects, setProjects] = useState<Project[]>([]);
  const [view, setView] = useState<'list' | 'setup'>('list');
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [activeTab, setActiveTab] = useState<'label' | 'browse'>('label');

  useEffect(() => {
    if (user) {
      api.listProjects(user.user_id).then((res) => setProjects(res.projects));
    }
  }, [user, view]);

  if (!user) return null;

  const [projectDetail, setProjectDetail] = useState<Record<string, any> | null>(null);

  if (activeProject) {
    const isAdmin = user.global_role === 'system_admin' || activeProject.role === 'project_admin';
    return (
      <div>
        <div style={{ display: 'flex', gap: 8, padding: 12, borderBottom: '1px solid #ccc' }}>
          <button onClick={() => { setActiveProject(null); setProjectDetail(null); setView('list'); }}>&larr; Projects</button>
          <strong>{activeProject.name}</strong>
          <button onClick={() => setActiveTab('label')}
                  style={{ fontWeight: activeTab === 'label' ? 'bold' : 'normal' }}>Label</button>
          <button onClick={() => setActiveTab('browse')}
                  style={{ fontWeight: activeTab === 'browse' ? 'bold' : 'normal' }}>Browse</button>
          {isAdmin && <button onClick={() => setActiveTab('setup')}>Setup</button>}
        </div>
        {activeTab === 'setup' && isAdmin && (
          <SetupView onDone={() => setActiveTab('label')} />
        )}
        {activeTab === 'label' && projectDetail && (
          <LabelView
            projectId={activeProject.id}
            templateSource={projectDetail.template_source || ''}
            numRows={projectDetail.num_rows || 0}
            onBack={() => setActiveProject(null)}
          />
        )}
        {activeTab === 'browse' && (
          <BrowseView projectId={activeProject.id} onBack={() => { setActiveProject(null); setProjectDetail(null); }} />
        )}
      </div>
    );
  }

  return (
    <div style={{ padding: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <h1>Projects</h1>
        <div>
          <span style={{ marginRight: 12 }}>{user.name} ({user.global_role})</span>
          {user.global_role === 'system_admin' && (
            <button onClick={() => setView('setup')}>New Project</button>
          )}
          <button onClick={logout} style={{ marginLeft: 8 }}>Logout</button>
        </div>
      </div>

      {view === 'setup' && user.global_role === 'system_admin' ? (
        <SetupView onDone={() => setView('list')} />
      ) : (
        <div>
          {projects.length === 0 && <p>No projects available.</p>}
          {projects.map((p) => (
            <div key={p.id} style={{ border: '1px solid #ccc', padding: 12, marginBottom: 8, borderRadius: 4 }}>
              <strong>{p.name}</strong>
              {p.role && <span style={{ marginLeft: 12, color: '#666' }}>({p.role})</span>}
              <div style={{ marginTop: 8 }}>
                <button onClick={async () => {
                  const detail = await api.getProject(p.id, user.user_id);
                  setProjectDetail(detail);
                  setActiveProject(p);
                  setActiveTab('label');
                }} style={{ marginRight: 8 }}>Label</button>
                <button onClick={() => {
                  setActiveProject(p);
                  setActiveTab('browse');
                }}>Browse</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/ProjectListView.tsx
git commit -m "feat: wired routing between project list, setup, label, and browse views"
```

---

### Task 16: End-to-end verification

- [ ] **Step 1: Start backend**

Run: `cd backend && uvicorn main:app --reload`

- [ ] **Step 2: Seed a test user**

Create `data/users.json`:
```json
{
  "users": [
    { "id": "admin", "name": "Admin", "global_role": "system_admin" },
    { "id": "annotator1", "name": "Annotator 1", "global_role": "annotator" }
  ]
}
```

- [ ] **Step 3: Start frontend**

Run: `cd frontend && npm run dev`

- [ ] **Step 4: Manual test flow**

1. Open browser to frontend URL
2. Login as "admin"
3. Click "New Project"
4. Load a dataset (e.g., {"source": "imdb"})
5. Verify template preview shows row data
6. Save template and create project
7. Go to Label view, verify row renders
8. Submit annotation, verify next row loads
9. Go to Browse view, verify row grid shows status
10. Login as "annotator1" — verify project list is empty (no permissions)
