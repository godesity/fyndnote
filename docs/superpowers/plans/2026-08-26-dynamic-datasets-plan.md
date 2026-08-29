# Dynamic Datasets — Add Rows + Remove Annotations / ML Predictions

> **For agentic workers:** execute task-by-task below, committing after each step.
> Work in a feature branch (`git worktree` / branch off `main`), not directly on `main`.
> Each task follows TDD: write the failing test → run → implement → run → commit.

**Goal:** Implement `features/dynamic-datasets.md`: let a project (a) **import additional
rows** into its own append-only dataset and (b) **remove annotations and ML predictions**
it has collected, via a small REST API surface.

**Architecture (per spec):**
- **Row data** lives in append-only **Parquet fragment files** on disk — one folder per
  project, unique per project only once it has been modified. Reads for a modified project
  come from the fragments; unmodified projects keep serving from the HF source dataset.
- **Annotations / ML predictions** stay in SQLite/PostgreSQL and are removed with plain
  `DELETE` statements keyed by `(project_id, row_index[, user_id])`.
- Two independent subsystems, safe to ship separately:
  - **Subsystem A (small, no storage work):** delete endpoints for annotations + predictions.
  - **Subsystem B (larger):** append-only fragment storage + `rows/bulk` import.

**Tech Stack:** FastAPI + SQLite/PostgreSQL via `get_db()` in `annotation_service.py`;
pyarrow for Parquet; React 19 + Vite frontend; pytest + `fastapi.testclient`.

**Spec:** `features/dynamic-datasets.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/database.py` | Modify | Create `dataset_meta` table (Subsystem B) |
| `backend/config.py` | Modify | `PROJECTS_DIR` constant (Subsystem B) |
| `backend/services/project_dataset.py` | **Create** | Fragment storage service (Subsystem B) |
| `backend/services/annotation_service.py` | Modify | Delete methods + read-path fallback (A & B) |
| `backend/routers/projects.py` | Modify | New REST endpoints (A & B) |
| `tests/backend/test_projects.py` | Modify | Delete endpoint + rows/bulk tests |
| `tests/backend/test_project_dataset.py` | **Create** | Storage service unit tests (B) |
| `frontend/src/api/client.ts` | Modify | API client methods (A & B) |
| `frontend/src/components/RowDetail.tsx` | Modify | Clear-annotation / clear-predictions buttons (A) |
| `frontend/src/views/SetupView.tsx` | Modify | "Import rows" control (B) |
| `docs/guide/dynamic-datasets.md` | **Create** | User docs (final task) |

---

## Subsystem A — Remove Annotations & ML Predictions

> No storage work. Pure SQL deletes on existing tables. Shippable first.

### Task A1: Service delete methods

**Files:** `backend/services/annotation_service.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/backend/test_projects.py`)

```python
def test_delete_annotation_single_user(client):
    # create project inline (match existing test pattern: POST /api/v1/projects with
    # a dataset_id), then annotate row 0 as alice and bob via POST /api/v1/projects/{pid}/annotate
    from database import get_db
    db = get_db()
    db.execute("DELETE FROM fyndnot_annotations WHERE project_id=? AND row_index=? AND user_id=?",
               (pid, 0, "alice"))
    db.commit(); db.close()
    # GET /projects/{pid}/annotations/0 -> bob only (alice's gone)
```

Also test: delete-all-for-row (`row_index` w/o `user_id`), delete-all-for-project.

- [ ] **Step 2: Run to confirm fail** — `cd backend && uv run pytest ../tests/backend/test_projects.py -v`
  Expected: FAIL — method/endpoint does not exist yet.

- [ ] **Step 3: Implement in `annotation_service.py`** (next to `submit_annotation`):

```python
@staticmethod
def delete_annotation(pid: str, row_index: int, user_id: str | None = None) -> int:
    db = get_db()
    if user_id:
        cur = db.execute(
            "DELETE FROM fyndnot_annotations WHERE project_id=? AND row_index=? AND user_id=?",
            (pid, row_index, user_id))
    else:
        cur = db.execute(
            "DELETE FROM fyndnot_annotations WHERE project_id=? AND row_index=?",
            (pid, row_index))
    db.commit(); db.close()
    return cur.rowcount

@staticmethod
def delete_all_annotations(pid: str) -> int:
    db = get_db()
    cur = db.execute("DELETE FROM fyndnot_annotations WHERE project_id=?", (pid,))
    db.commit(); db.close()
    return cur.rowcount

@staticmethod
def delete_ml_annotation(pid: str, row_index: int) -> int:
    db = get_db()
    cur = db.execute(
        "DELETE FROM fyndnot_ml_annotations WHERE project_id=? AND row_index=?",
        (pid, row_index))
    db.commit(); db.close()
    return cur.rowcount

@staticmethod
def delete_all_ml_annotations(pid: str) -> int:
    db = get_db()
    cur = db.execute("DELETE FROM fyndnot_ml_annotations WHERE project_id=?", (pid,))
    db.commit(); db.close()
    return cur.rowcount
```

- [ ] **Step 4: Run tests** — PASS.
- [ ] **Step 5: Commit** — `feat: annotation/ML delete service methods`

### Task A2: Delete REST endpoints

**Files:** `backend/routers/projects.py`

- [ ] **Step 1: Failing tests** — extend `test_projects.py`:

```python
def test_delete_annotation_endpoint(client):
    # create project inline, annotate row 0 as alice + bob (match existing test setup)
    resp = client.delete(f"/api/v1/projects/{pid}/annotations/0?user_id=alice")
    assert resp.status_code == 200 and resp.json()["status"] == "deleted"
    # remaining: bob only
    resp = client.delete(f"/api/v1/projects/{pid}/annotations")
    assert resp.status_code == 200  # deletes all
    resp = client.delete(f"/api/v1/projects/{pid}/ml-annotations/0")
    assert resp.status_code == 200
    resp = client.delete(f"/api/v1/projects/{pid}/ml-annotations")
    assert resp.status_code == 200
    # 404 for unknown project
    assert client.delete("/api/v1/projects/nope/annotations").status_code == 404
```

- [ ] **Step 2: Run** — FAIL (endpoints missing).
- [ ] **Step 3: Implement routes** in `projects.py`:

```python
@router.delete("/projects/{pid}/annotations/{row_index}")
def delete_annotation(pid: str, row_index: int, user_id: str | None = None):
    if not AnnotationService.get_project(pid):
        raise HTTPException(404, "project not found")
    n = AnnotationService.delete_annotation(pid, row_index, user_id)
    return {"status": "deleted", "rows": n}

@router.delete("/projects/{pid}/annotations")
def delete_all_annotations(pid: str):
    if not AnnotationService.get_project(pid):
        raise HTTPException(404, "project not found")
    n = AnnotationService.delete_all_annotations(pid)
    return {"status": "deleted", "rows": n}

@router.delete("/projects/{pid}/ml-annotations/{row_index}")
def delete_ml_annotation(pid: str, row_index: int):
    if not AnnotationService.get_project(pid):
        raise HTTPException(404, "project not found")
    n = AnnotationService.delete_ml_annotation(pid, row_index)
    return {"status": "deleted", "rows": n}

@router.delete("/projects/{pid}/ml-annotations")
def delete_all_ml_annotations(pid: str):
    if not AnnotationService.get_project(pid):
        raise HTTPException(404, "project not found")
    n = AnnotationService.delete_all_ml_annotations(pid)
    return {"status": "deleted", "rows": n}
```

> The existence check is confirmed: `AnnotationService.get_project(pid)` returns the
> project row or `None` — use the same guard the project's existing routes use.

- [ ] **Step 4: Run tests** — PASS.
- [ ] **Step 5: Commit** — `feat: delete annotation/ML-prediction endpoints`

### Task A3: Frontend clear controls

**Files:** `frontend/src/api/client.ts`, `frontend/src/components/RowDetail.tsx`

- [ ] **Step 1: API client methods** (mirror existing `request` helper):

```ts
deleteAnnotation: (pid, rowIndex, userId?) =>
  request(`/projects/${pid}/annotations/${rowIndex}${userId ? `?user_id=${userId}` : ''}`, { method: 'DELETE' }),
deleteAllAnnotations: (pid) =>
  request(`/projects/${pid}/annotations`, { method: 'DELETE' }),
deleteMLAnnotation: (pid, rowIndex) =>
  request(`/projects/${pid}/ml-annotations/${rowIndex}`, { method: 'DELETE' }),
deleteAllMLAnnotations: (pid) =>
  request(`/projects/${pid}/ml-annotations`, { method: 'DELETE' }),
```

- [ ] **Step 2: UI** — in `RowDetail.tsx`, add a "Clear annotation" button (calls
  `deleteAnnotation`) and "Clear prediction" button (calls `deleteMLAnnotation`); disable
  while pending; refetch the row after. Type-check: `cd frontend && npm run build`.
- [ ] **Step 3: Commit** — `feat: clear annotation/prediction controls`

---

## Subsystem B — Add Rows (Append-Only Fragment Storage)

### Task B1: DB schema + config

**Files:** `backend/database.py`, `backend/config.py`

- [ ] **Step 1: Add `dataset_meta` table** in `init_db()` (idempotent `CREATE TABLE IF NOT EXISTS` — no separate migration needed since it runs every startup):

```sql
CREATE TABLE IF NOT EXISTS dataset_meta (
  project_id   TEXT PRIMARY KEY,
  num_rows     INTEGER NOT NULL DEFAULT 0,
  next_fragment INTEGER NOT NULL DEFAULT 0,
  schema       TEXT,
  created_at   TEXT NOT NULL
)
```

- [ ] **Step 2: Config constant** in `config.py`:

```python
PROJECTS_DIR = DATASETS_DIR / "projects"   # data/datasets/projects/{pid}/fragments|media
```

- [ ] **Step 3: Commit** — `feat: dataset_meta table + projects dir config`

### Task B2: `project_dataset` storage service

**Files:** `backend/services/project_dataset.py` (new)

- [ ] **Step 1: Failing unit tests** — new `tests/backend/test_project_dataset.py`:
  - `ensure_meta(pid)` seeds `num_rows` from the project's source dataset when empty.
  - `append_rows(pid, [ {...}, {...} ])` writes `frag_0.parquet`, bumps `num_rows`, `next_fragment`.
  - `append_rows` twice → two fragments; `load_table(pid)` concatenates both in order.
  - `get_row(pid, i)` returns serialized dict shaped like `DatasetService.get_row`.
  - `num_rows(pid)` reads from `dataset_meta`, falls back to source dataset if no meta.
- [ ] **Step 2: Run** — FAIL (module missing).
- [ ] **Step 3: Implement**:

```python
def _project_dir(pid):  return config.PROJECTS_DIR / pid
def _frag_dir(pid):     return _project_dir(pid) / "fragments"
def _media_dir(pid):    return _project_dir(pid) / "media"

def get_meta(pid) -> dict | None:
    # SELECT * FROM dataset_meta WHERE project_id=?

def ensure_meta(pid):
    # if no row: seed num_rows from source dataset length, columns -> schema JSON, created_at

def append_rows(pid, rows: list[dict]) -> int:
    # ensure_meta; build pyarrow Table from rows (infer schema from first row);
    # write frag_{next_fragment}.parquet; bump num_rows += len(rows), next_fragment += 1;
    # store serialized Arrow schema in dataset_meta.schema; commit.

def load_table(pid) -> pa.Table:
    # pq.ParquetDataset over fragments, concatenate in fragment order

def get_row(pid, i) -> dict | None:
    # if i >= num_rows(pid): None; else load_table -> row i -> dict (JSON-safe)

def num_rows(pid) -> int:
    # meta.num_rows if meta else source-dataset length
```

> **Media materialization (image/audio → `media/` + path rewrite) is explicitly deferred**
> to a follow-up. v1 stores only JSON-serializable scalar/text columns; the spec's
> media rewrite is noted as a known gap in the plan, not built now.

- [ ] **Step 4: Run tests** — PASS.
- [ ] **Step 5: Commit** — `feat: project_dataset fragment storage service`

### Task B3: Read-path integration

**Files:** `backend/services/annotation_service.py`

- [ ] **Step 1: Failing test** — in `test_project_dataset.py` (or `test_projects.py`):
  unit-level: after `project_dataset.append_rows(pid, rows)`,
  `AnnotationService.get_project_row(pid, 0)` returns the imported row; for an unmodified
  project it still returns source-dataset rows. (There is no public `GET /rows/{index}`
  route today — row reads go through `get_project_row`/`navigate_row` internally. Adding a
  public read endpoint is optional/follow-up, not required here.)
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement fallback** in `get_project_row` / `navigate_row` (and any row-read
  path that currently calls `DatasetService.get_row(ds_id, i)`):

```python
meta = project_dataset.get_meta(pid)
if meta is not None:
    return project_dataset.get_row(pid, row_index)   # custom dataset wins
# else: existing DatasetService.get_row(ds_id, row_index) fallback
```

  Also make the "next row" / pagination bounds use `project_dataset.num_rows(pid)` when a
  project has custom rows. Unmodified projects keep current behavior exactly.

- [ ] **Step 4: Run full suite** — PASS (existing tests unchanged).
- [ ] **Step 5: Commit** — `feat: serve imported rows from fragments`

### Task B4: `POST /projects/{pid}/rows/bulk`

**Files:** `backend/routers/projects.py`

- [ ] **Step 1: Failing tests**:

```python
def test_import_rows_bulk(client):
    # create project inline (match existing setup)
    body = {"rows": [{"text": "imported one"}, {"text": "imported two"}]}
    resp = client.post(f"/api/v1/projects/{pid}/rows/bulk", json=body)
    assert resp.status_code == 200 and resp.json()["imported"] == 2
    # via AnnotationService.get_project_row(pid, 0) -> "imported one",
    #   get_project_row(pid, 1) -> "imported two"
    # num_rows now = source_len + 2
```

- [ ] **Step 2: Run** — FAIL (endpoint missing).
- [ ] **Step 3: Implement** — accept JSON body `{"rows": [...]}` (JSONL-style, the v1 format):

```python
class BulkRowsIn(BaseModel):
    rows: list[dict[str, Any]]

@router.post("/projects/{pid}/rows/bulk")
def import_rows(pid: str, body: BulkRowsIn):
    if not AnnotationService.get_project(pid):
        raise HTTPException(404, "project not found")
    n = project_dataset.append_rows(pid, body.rows)
    return {"status": "ok", "imported": n}
```

  (Parquet/CSV/JSON-file upload via `UploadFile` is a follow-up; v1 ships JSON-rows body.)

- [ ] **Step 4: Run tests** — PASS.
- [ ] **Step 5: Commit** — `feat: rows/bulk import endpoint`

### Task B5: Frontend import control

**Files:** `frontend/src/api/client.ts`, `frontend/src/views/EditProjectView.tsx`

- [ ] **Step 1: API method**: `importRows: (pid, rows) => request(..., { method: 'POST', body: JSON.stringify({ rows }) })`
- [ ] **Step 2: UI** — in `EditProjectView.tsx` (NOT SetupView — SetupView is the project-creation wizard and has no `projectId`; EditProjectView receives `{ projectId }`), add a textarea "Import rows (JSON array)" + Import button; show `imported` count on success; error on 422 (e.g. heterogeneous columns) and 404. Type-check: `npm run build`.
- [ ] **Step 3: Commit** — `feat: import-rows control in setup view`

---

## Final Tasks

### Task F1: Full verification

- [ ] `cd backend && uv run pytest ../tests/backend -q` — all pass (old + new).
- [ ] `cd frontend && npm run build && npm run lint` — clean (no new findings in touched files).
- [ ] Manual smoke via `uv run uvicorn main:app --reload` + curl the four DELETE routes and
  the `rows/bulk` route against a seeded project.
- [ ] Commit — `chore: verify dynamic datasets`

### Task F2: User docs

**Files:** `docs/guide/dynamic-datasets.md` (new)

- [ ] Document: fragment storage layout (`data/datasets/projects/{pid}/fragments`), the four
  DELETE endpoints, the `rows/bulk` endpoint, and the deferred media-materialization gap.
- [ ] Commit — `docs: dynamic datasets guide`

---

## Checklist

- [ ] Subsystem A: delete methods + 4 endpoints + frontend controls (shippable independently)
- [ ] Subsystem B: `dataset_meta` table + fragment service + read fallback + `rows/bulk` + UI
- [ ] All backend tests pass; frontend build/lint clean
- [ ] Docs updated; known gap (media materialization) documented
