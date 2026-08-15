# Dataset Import & Browse View — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add support for loading datasets via HTTP URLs, file paths, and browser uploads (CSV/JSON/JSONL/Parquet), plus fix the stubbed browse view.

**Architecture:** Backend auto-detects dataset source type from input prefix, dispatches to the appropriate loader, and stores format metadata for rehydration. The browse rows endpoint is implemented by querying the dataset and annotations tables with pagination and status filtering.

**Tech Stack:** FastAPI, HuggingFace `datasets`, SQLite, React + react-live

---

### Task 1: Source type detection in DatasetService

**Files:**
- Modify: `backend/services/dataset_service.py`
- Create: `tests/backend/test_dataset_source_detection.py`

- [ ] **Step 1: Add source detection helper**

Add to `dataset_service.py`:

```python
import re
from pathlib import Path

DATASET_SOURCE_TYPES = {
    "csv": "csv",
    "json": "json",
    "jsonl": "json",
    "parquet": "parquet",
}

def _detect_source(source: str) -> tuple[str, str, str]:
    """Returns (source_type, format, clean_source)."""
    if source.startswith("http://") or source.startswith("https://"):
        ext = _extract_extension(source)
        if ext not in DATASET_SOURCE_TYPES:
            raise ValueError(
                f"Unsupported format: .{ext}. Supported: .csv, .json, .jsonl, .parquet"
            )
        return ("http", DATASET_SOURCE_TYPES[ext], source)
    elif source.startswith("file://"):
        path = source[7:]
        ext = _extract_extension(path)
        if ext not in DATASET_SOURCE_TYPES:
            raise ValueError(
                f"Unsupported format: .{ext}. Supported: .csv, .json, .jsonl, .parquet"
            )
        return ("file", DATASET_SOURCE_TYPES[ext], path)
    else:
        return ("huggingface", None, source)

def _extract_extension(path: str) -> str:
    return Path(path.split("?")[0]).suffix.lower().lstrip(".")
```

- [ ] **Step 2: Write failing tests**

Create `tests/backend/test_dataset_source_detection.py`:

```python
import pytest
from services.dataset_service import _detect_source

def test_detect_http_csv():
    st, fmt, src = _detect_source("https://example.com/data.csv")
    assert st == "http"
    assert fmt == "csv"
    assert src == "https://example.com/data.csv"

def test_detect_http_parquet():
    st, fmt, src = _detect_source("http://data.org/file.parquet")
    assert st == "http"
    assert fmt == "parquet"

def test_detect_file_json():
    st, fmt, src = _detect_source("file:///home/user/data.json")
    assert st == "file"
    assert fmt == "json"
    assert src == "/home/user/data.json"

def test_detect_file_jsonl():
    st, fmt, src = _detect_source("file:///home/user/data.jsonl")
    assert st == "file"
    assert fmt == "json"

def test_detect_huggingface():
    st, fmt, src = _detect_source("stanfordnlp/imdb")
    assert st == "huggingface"
    assert fmt is None
    assert src == "stanfordnlp/imdb"

def test_detect_huggingface_plain():
    st, fmt, src = _detect_source("imdb")
    assert st == "huggingface"
    assert fmt is None

def test_detect_unsupported_format():
    with pytest.raises(ValueError, match="Unsupported format"):
        _detect_source("https://example.com/data.xlsx")

def test_detect_url_with_query_params():
    st, fmt, src = _detect_source("https://example.com/data.csv?download=1")
    assert st == "http"
    assert fmt == "csv"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/backend/test_dataset_source_detection.py -v`
Expected: All tests pass (since we wrote the code first — or if we haven't, they fail)

Actually we need to import first. Let me make sure the tests are structured properly.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/backend/test_dataset_source_detection.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/dataset_service.py tests/backend/test_dataset_source_detection.py
git commit -m "feat: add dataset source type detection"
```

---

### Task 2: Update DatasetService.load with source type dispatch

**Files:**
- Modify: `backend/services/dataset_service.py`
- Modify: `tests/backend/test_datasets.py`

- [ ] **Step 1: Update `load()` method to use source detection**

Replace the current `load()` method:

```python
@classmethod
def load(cls, source: str, split: str = "train", name: str = None) -> dict:
    source_type, source_format, clean_source = _detect_source(source)
    ds_id = str(uuid.uuid4())

    if source_type == "huggingface":
        ds = load_dataset(clean_source, name, split=split)
    elif source_type == "http":
        ds = _load_http(clean_source, source_format)
        split = None
        name = None
    elif source_type == "file":
        ds = _load_file(clean_source, source_format)
        split = None
        name = None
    else:
        raise ValueError(f"Unknown source type: {source_type}")

    cls._instances[ds_id] = ds
    meta = {
        "id": ds_id,
        "source": source,
        "source_type": source_type,
        "source_format": source_format,
        "name": name,
        "split": split,
        "num_rows": len(ds),
        "columns": [{"name": col, "type": str(ds.features[col])} for col in ds.column_names],
        "created_at": datetime.utcnow().isoformat(),
    }
    meta_dir = DATASETS_DIR / ds_id
    meta_dir.mkdir(parents=True, exist_ok=True)
    with open(meta_dir / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)
    return meta
```

- [ ] **Step 2: Add `_load_http()` and `_load_file()` helpers**

```python
import requests
import tempfile

def _load_http(url: str, fmt: str) -> Dataset:
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    suffix = f".{fmt}"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        for chunk in resp.iter_content(chunk_size=8192):
            tmp.write(chunk)
        tmp_path = tmp.name
    try:
        ds = _load_from_format(tmp_path, fmt)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return ds

def _load_file(path: str, fmt: str) -> Dataset:
    if not Path(path).exists():
        raise FileNotFoundError(f"File not found: {path}")
    return _load_from_format(path, fmt)

def _load_from_format(path: str, fmt: str) -> Dataset:
    format_map = {
        "csv": lambda p: load_dataset("csv", data_files=p, split="train"),
        "json": lambda p: load_dataset("json", data_files=p, split="train"),
        "jsonl": lambda p: load_dataset("json", data_files=p, split="train"),
        "parquet": lambda p: load_dataset("parquet", data_files=p, split="train"),
    }
    loader = format_map.get(fmt)
    if not loader:
        raise ValueError(f"Unsupported format: {fmt}")
    return loader(path)
```

Add `requests` to `backend/pyproject.toml` dependencies.

- [ ] **Step 3: Update `_load_ds()` rehydration**

```python
@classmethod
def _load_ds(cls, ds_id: str) -> Dataset:
    ds = cls._instances.get(ds_id)
    if ds is not None:
        return ds
    meta_path = DATASETS_DIR / ds_id / "meta.json"
    if not meta_path.exists():
        raise ValueError("Dataset not found")
    with open(meta_path) as f:
        meta = json.load(f)
    source_type = meta.get("source_type", "huggingface")
    source = meta["source"]
    if source_type == "huggingface":
        ds = load_dataset(meta.get("source"), meta.get("name"), split=meta.get("split", "train"))
    elif source_type == "http":
        fmt = meta.get("source_format", "csv")
        ds = _load_http(source, fmt)
    elif source_type == "file":
        clean = source[7:] if source.startswith("file://") else source
        fmt = meta.get("source_format", "csv")
        ds = _load_file(clean, fmt)
    else:
        raise ValueError(f"Unknown source type: {source_type}")
    cls._instances[ds_id] = ds
    return ds
```

- [ ] **Step 4: Add tests for HTTP and file loading**

Add to `tests/backend/test_datasets.py`:

```python
def test_load_http_csv(httpserver):
    import csv, io
    content = "text,label\nhello,0\nworld,1\n"
    httpserver.expect_request("/data.csv").respond_with_data(content, content_type="text/csv")
    from services.dataset_service import DatasetService
    meta = DatasetService.load(httpserver.url_for("/data.csv"))
    assert meta["source_type"] == "http"
    assert meta["source_format"] == "csv"
    assert meta["num_rows"] == 2

def test_load_file_csv(tmp_path):
    f = tmp_path / "test.csv"
    f.write_text("text,label\nhello,0\nworld,1\n")
    from services.dataset_service import DatasetService
    meta = DatasetService.load(f"file://{f}")
    assert meta["source_type"] == "file"
    assert meta["num_rows"] == 2
```

Note: The HTTP test requires `pytest-httpserver`. Add it to test deps if needed, or use `responses` / `requests_mock`. For simplicity, we can mock `requests.get` in the test.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/backend/test_datasets.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/services/dataset_service.py backend/pyproject.toml tests/backend/test_datasets.py
git commit -m "feat: support HTTP URL and file:// dataset loading"
```

---

### Task 3: Add file upload endpoint

**Files:**
- Modify: `backend/routers/datasets.py`
- Modify: `backend/services/dataset_service.py`
- Modify: `backend/config.py`

- [ ] **Step 1: Add upload directory to config**

In `backend/config.py`:

```python
DATASETS_UPLOAD_DIR = DATA_DIR / "datasets" / "uploads"
```

- [ ] **Step 2: Add upload method to DatasetService**

```python
import shutil

@classmethod
def load_upload(cls, filename: str, content: bytes) -> dict:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext not in DATASET_SOURCE_TYPES:
        raise ValueError(
            f"Unsupported format: .{ext}. Supported: .csv, .json, .jsonl, .parquet"
        )
    fmt = DATASET_SOURCE_TYPES[ext]
    DATASETS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = DATASETS_UPLOAD_DIR / f"{uuid.uuid4()}.{ext}"
    dest.write_bytes(content)
    return cls.load(f"file://{dest}", fmt)
```

Update `load()` to accept optional format parameter:

```python
@classmethod
def load(cls, source: str, split: str = "train", name: str = None, source_format: str = None) -> dict:
    source_type, detected_format, clean_source = _detect_source(source)
    source_format = source_format or detected_format
    ...
```

- [ ] **Step 3: Add upload route**

```python
import tempfile
from fastapi import File, UploadFile

@router.post("/datasets/upload", status_code=201)
async def upload_dataset(file: UploadFile = File(...)):
    content = await file.read()
    try:
        meta = DatasetService.load_upload(file.filename, content)
        return meta
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 4: Add test for upload**

```python
def test_upload_csv(client):
    content = b"text,label\nhello,0\nworld,1\n"
    resp = client.post("/api/v1/datasets/upload", files={"file": ("test.csv", content, "text/csv")})
    assert resp.status_code == 201
    data = resp.json()
    assert data["num_rows"] == 2
    assert data["source_type"] == "file"

def test_upload_unsupported_format(client):
    content = b"test"
    resp = client.post("/api/v1/datasets/upload", files={"file": ("test.xlsx", content, "application/octet-stream")})
    assert resp.status_code == 400
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/backend/test_datasets.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/routers/datasets.py backend/services/dataset_service.py backend/config.py tests/backend/test_datasets.py
git commit -m "feat: add dataset file upload endpoint"
```

---

### Task 4: Implement browse_rows

**Files:**
- Modify: `backend/services/annotation_service.py`
- Modify: `tests/backend/test_projects.py`

- [ ] **Step 1: Write failing test for browse_rows**

Add to `tests/backend/test_projects.py`:

```python
def test_browse_rows_all(client):
    # First load a dataset
    ds_resp = client.post("/api/v1/datasets/load", json={"source": "stanfordnlp/imdb", "split": "train"})
    ds_id = ds_resp.json()["id"]

    # Create template
    t_resp = client.post("/api/v1/templates", json={"name": "test", "source": "<div>{data.text}</div>"})
    t_id = t_resp.json()["id"]

    # Create project
    p_resp = client.post("/api/v1/projects", json={"name": "browse-test", "dataset_id": ds_id, "template_id": t_id})
    pid = p_resp.json()["id"]

    # Browse all rows
    resp = client.get(f"/api/v1/projects/{pid}/rows?user_id=alice&page=1&per_page=5&status=all")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["rows"]) == 5
    assert data["total"] == 25000
    assert data["page"] == 1
    assert data["per_page"] == 5
    assert "index" in data["rows"][0]

def test_browse_rows_annotated_filter(client):
    # Same setup...
    ds_resp = client.post("/api/v1/datasets/load", json={"source": "stanfordnlp/imdb", "split": "train"})
    ds_id = ds_resp.json()["id"]
    t_resp = client.post("/api/v1/templates", json={"name": "test", "source": "<div>{data.text}</div>"})
    t_id = t_resp.json()["id"]
    p_resp = client.post("/api/v1/projects", json={"name": "browse-test-2", "dataset_id": ds_id, "template_id": t_id})
    pid = p_resp.json()["id"]

    # Annotate one row
    client.post(f"/api/v1/projects/{pid}/annotate", json={"row_index": 0, "user_id": "alice", "data": {"sentiment": "positive"}})

    # Filter annotated
    resp = client.get(f"/api/v1/projects/{pid}/rows?user_id=alice&page=1&status=annotated_by_me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["rows"][0]["index"] == 0

    # Filter unannotated
    resp = client.get(f"/api/v1/projects/{pid}/rows?user_id=alice&page=1&status=unannotated")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 24999
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/backend/test_projects.py::test_browse_rows_all -v`
Expected: FAIL — browse_rows returns empty

- [ ] **Step 3: Implement browse_rows**

Replace the stub in `AnnotationService.browse_rows()`:

```python
@staticmethod
def browse_rows(pid: str, user_id: str, page: int, per_page: int, status: str, include_annotations: bool) -> tuple:
    from services.dataset_service import DatasetService
    db = get_db()
    project = db.execute("SELECT dataset_id FROM projects WHERE id = ?", (pid,)).fetchone()
    if not project:
        db.close()
        return [], 0

    ds_id = project["dataset_id"]
    total_rows = len(DatasetService._load_ds(ds_id))

    # Get annotated set for this user
    annotated = {
        r[0] for r in db.execute(
            "SELECT row_index FROM annotations WHERE project_id = ? AND user_id = ?",
            (pid, user_id)
        ).fetchall()
    }

    db.close()

    all_indices = list(range(total_rows))

    if status == "annotated_by_me":
        indices = sorted(i for i in all_indices if i in annotated)
    elif status == "unannotated":
        indices = sorted(i for i in all_indices if i not in annotated)
    else:
        indices = all_indices

    total = len(indices)
    start = (page - 1) * per_page
    page_indices = indices[start:start + per_page]

    rows_data = []
    for idx in page_indices:
        entry = {"index": idx}
        if include_annotations and idx in annotated:
            db2 = get_db()
            ann = db2.execute(
                "SELECT data FROM annotations WHERE project_id = ? AND row_index = ? AND user_id = ?",
                (pid, idx, user_id)
            ).fetchone()
            db2.close()
            if ann:
                entry["annotations"] = json.loads(ann["data"])
        rows_data.append(entry)

    return rows_data, total
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/backend/test_projects.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add backend/services/annotation_service.py tests/backend/test_projects.py
git commit -m "feat: implement browse_rows with pagination and status filter"
```

---

### Task 5: Add uploadDataset to frontend API client

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add upload method**

```typescript
uploadDataset: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return fetch(`${BASE}/datasets/upload`, {
      method: 'POST',
      body: formData,
    }).then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new ApiError(res.status, body.detail || res.statusText);
      }
      return res.json();
    });
  },
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add uploadDataset to frontend API client"
```

---

### Task 6: Build the Load New dialog in SetupView

**Files:**
- Modify: `frontend/src/views/SetupView.tsx`

- [ ] **Step 1: Replace the "Load New" button stub with a functional dialog**

Replace lines around the "Load New" button:

```tsx
const [loadInput, setLoadInput] = useState("");
const [loadError, setLoadError] = useState<string | null>(null);
const [loading, setLoading] = useState(false);

const handleLoad = async () => {
  if (!loadInput.trim()) return;
  setLoading(true);
  setLoadError(null);
  try {
    await api.loadDataset(loadInput.trim());
    setLoadInput("");
    const res = await api.listDatasets();
    setDatasets(res.datasets);
  } catch (err: any) {
    setLoadError(err.message || "Failed to load dataset");
  } finally {
    setLoading(false);
  }
};

const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
  const file = e.target.files?.[0];
  if (!file) return;
  setLoading(true);
  setLoadError(null);
  try {
    await api.uploadDataset(file);
    const res = await api.listDatasets();
    setDatasets(res.datasets);
  } catch (err: any) {
    setLoadError(err.message || "Failed to upload dataset");
  } finally {
    setLoading(false);
  }
};
```

Replace the button:

```tsx
<button onClick={() => document.getElementById('load-dialog')?.classList.toggle('hidden')} style={{ marginLeft: 8 }}>
  Load New
</button>

<div id="load-dialog" style={{ marginTop: 8, padding: 12, border: '1px solid #ccc', borderRadius: 4 }}>
  <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
    <input
      value={loadInput}
      onChange={(e) => setLoadInput(e.target.value)}
      placeholder="HF dataset ID, HTTP URL, or file:// path"
      style={{ flex: 1, padding: 8 }}
    />
    <button onClick={handleLoad} disabled={loading || !loadInput.trim()}>
      {loading ? "Loading..." : "Load"}
    </button>
  </div>
  <div>
    <input type="file" accept=".csv,.json,.jsonl,.parquet" onChange={handleFileUpload} />
  </div>
  {loadError && <p style={{ color: 'red', fontSize: 13, marginTop: 4 }}>{loadError}</p>}
</div>
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/SetupView.tsx
git commit -m "feat: add dataset load dialog with text input and file upload"
```

---

### Task 7: Add upload test for frontend-behind test

- [ ] **Step 1: Add E2E-style test**

Add to `tests/backend/test_datasets.py`:

```python
def test_load_dataset_workflow(client):
    # HTTP-style CSV
    import tempfile, pathlib
    f = pathlib.Path(tempfile.mktemp(suffix=".csv"))
    f.write_text("text,label\nhello,0\nworld,1\n")
    resp = client.post("/api/v1/datasets/load", json={"source": f"file://{f}"})
    f.unlink()
    assert resp.status_code == 200
    data = resp.json()
    assert data["num_rows"] == 2

    # Verify re-list
    list_resp = client.get("/api/v1/datasets")
    ids = [d["id"] for d in list_resp.json()["datasets"]]
    assert data["id"] in ids
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/backend/test_datasets.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/backend/test_datasets.py
git commit -m "test: add dataset load workflow test"
```
