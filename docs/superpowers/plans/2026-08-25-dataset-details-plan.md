# Dataset Details Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `GET /api/v1/datasets/{ds_id}/details` (dataset meta + per-project annotation/prediction counts + totals) and a collapsed "Dataset details" section in the Browse view.

**Architecture:** A read-only service method on `DatasetService` (single DB connection, matching `list_datasets`) plus a thin router endpoint; the Browse view fetches it fire-and-forget after the project load and renders a collapsible `<details>` card via a local `DatasetDetailsSection` helper component.

**Tech Stack:** FastAPI + SQLite via `get_db()`; React 19 + Vite + Tailwind; pytest + `fastapi.testclient`.

Spec: `docs/superpowers/specs/2026-08-25-dataset-details-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `tests/backend/test_datasets.py` | Modify | `test_dataset_details` |
| `backend/services/dataset_service.py` | Modify | `DatasetService.dataset_details` |
| `backend/routers/datasets.py` | Modify | `GET /datasets/{ds_id}/details` |
| `frontend/src/api/client.ts` | Modify | `api.getDatasetDetails` |
| `frontend/src/views/BrowseView.tsx` | Modify | State + fetch + `DatasetDetailsSection` |

---

### Task A: Backend — `GET /datasets/{ds_id}/details` (TDD)

**Files:**
- Test: `tests/backend/test_datasets.py` (append)
- Modify: `backend/services/dataset_service.py` (add classmethod after `list_datasets`)
- Modify: `backend/routers/datasets.py` (add route)

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_datasets.py`:

```python
def test_dataset_details(client):
    import tempfile, pathlib
    f = pathlib.Path(tempfile.mktemp(suffix=".csv"))
    f.write_text("text,label\nrow one,0\nrow two,1\n")
    load_resp = client.post("/api/v1/datasets/load", json={"source": f"file://{f}"})
    assert load_resp.status_code == 200
    ds_id = load_resp.json()["id"]

    t_resp = client.post("/api/v1/templates", json={"name": "details-tpl", "source": "<div>{data.text}</div>"})
    t_id = t_resp.json()["id"]
    a_resp = client.post("/api/v1/projects", json={"name": "details-a", "dataset_id": ds_id, "template_id": t_id})
    p_a = a_resp.json()["id"]
    b_resp = client.post("/api/v1/projects", json={"name": "details-b", "dataset_id": ds_id, "template_id": t_id})
    p_b = b_resp.json()["id"]

    # Project A: alice + bob on row 0 -> 1 distinct row, 2 annotations
    client.post(f"/api/v1/projects/{p_a}/annotate", json={"row_index": 0, "user_id": "alice", "data": {"l": "a1"}})
    client.post(f"/api/v1/projects/{p_a}/annotate", json={"row_index": 0, "user_id": "bob", "data": {"l": "b1"}})
    # Project B: alice on rows 0 and 1 -> 2 distinct rows, 2 annotations
    client.post(f"/api/v1/projects/{p_b}/annotate", json={"row_index": 0, "user_id": "alice", "data": {"l": "a2"}})
    client.post(f"/api/v1/projects/{p_b}/annotate", json={"row_index": 1, "user_id": "alice", "data": {"l": "a3"}})

    # ML predictions: 1 for A, 2 for B
    from database import get_db
    db = get_db()
    for pid, count in ((p_a, 1), (p_b, 2)):
        for row in range(count):
            db.execute(
                "INSERT OR REPLACE INTO fyndnot_ml_annotations "
                "(project_id, row_index, annotator, data, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (pid, row, "ml-test", "{}", "2026-08-25T00:00:00", "2026-08-25T00:00:00"),
            )
    db.commit()
    db.close()

    resp = client.get(f"/api/v1/datasets/{ds_id}/details")
    assert resp.status_code == 200
    body = resp.json()
    assert body["dataset"]["num_rows"] == 2
    assert body["dataset"]["source"].endswith(".csv")

    by_name = {p["name"]: p for p in body["projects"]}
    assert by_name["details-a"] == {"id": p_a, "name": "details-a", "color": by_name["details-a"]["color"],
                                    "annotated_rows": 1, "annotations": 2, "predictions": 1}
    assert by_name["details-b"]["annotated_rows"] == 2
    assert by_name["details-b"]["annotations"] == 2
    assert by_name["details-b"]["predictions"] == 2
    assert body["totals"] == {"annotations": 4, "predictions": 3}

    missing = client.get("/api/v1/datasets/does-not-exist/details")
    assert missing.status_code == 404
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && uv run pytest ../tests/backend/test_datasets.py::test_dataset_details -v
```

Expected: FAIL — `GET /api/v1/datasets/{ds_id}/details` returns 404 (route does not exist yet), so `assert resp.status_code == 200` fails.

- [ ] **Step 3: Implement `DatasetService.dataset_details`**

Add this classmethod in `backend/services/dataset_service.py` immediately after `list_datasets`:

```python
    @classmethod
    def dataset_details(cls, ds_id: str) -> dict | None:
        db = get_db()
        row = db.execute(
            "SELECT * FROM fyndnot_datasets WHERE id = ?", (ds_id,)
        ).fetchone()
        if not row:
            db.close()
            return None
        projects = db.execute(
            "SELECT id, name, color FROM fyndnot_projects WHERE dataset_id = ? ORDER BY created_at",
            (ds_id,),
        ).fetchall()
        result_projects = []
        total_annotations = 0
        total_predictions = 0
        for p in projects:
            annotated_rows = db.execute(
                "SELECT COUNT(DISTINCT row_index) FROM fyndnot_annotations WHERE project_id = ?",
                (p["id"],),
            ).fetchone()[0]
            annotations = db.execute(
                "SELECT COUNT(*) FROM fyndnot_annotations WHERE project_id = ?",
                (p["id"],),
            ).fetchone()[0]
            predictions = db.execute(
                "SELECT COUNT(*) FROM fyndnot_ml_annotations WHERE project_id = ?",
                (p["id"],),
            ).fetchone()[0]
            total_annotations += annotations
            total_predictions += predictions
            result_projects.append(
                {
                    "id": p["id"],
                    "name": p["name"],
                    "color": p["color"],
                    "annotated_rows": annotated_rows,
                    "annotations": annotations,
                    "predictions": predictions,
                }
            )
        db.close()
        return {
            "dataset": {
                "id": row["id"],
                "source": row["source"],
                "source_type": row["source_type"],
                "source_format": row["source_format"],
                "name": row["hf_name"],
                "split": row["hf_split"],
                "num_rows": row["num_rows"],
                "created_at": row["created_at"],
            },
            "projects": result_projects,
            "totals": {
                "annotations": total_annotations,
                "predictions": total_predictions,
            },
        }
```

(`get_db` and `json` are already imported in this file; no new imports needed.
The `fyndnot_projects.color` column always has a default, so `p["color"]`
is never NULL.)

- [ ] **Step 4: Add the route**

In `backend/routers/datasets.py`, add after the `list_datasets` route:

```python
@router.get("/datasets/{ds_id}/details")
def dataset_details(ds_id: str):
    details = DatasetService.dataset_details(ds_id)
    if details is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return details
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
cd backend && uv run pytest ../tests/backend/test_datasets.py::test_dataset_details -v
```

Expected: PASS.

- [ ] **Step 6: Run the full backend suite**

```bash
cd backend && uv run pytest ../tests/backend -q
```

Expected: all pass (previously 38, now 39).

- [ ] **Step 7: Commit**

```bash
git add tests/backend/test_datasets.py backend/services/dataset_service.py backend/routers/datasets.py
git commit -m "feat: add GET /datasets/{id}/details endpoint with project counts"
```

---

### Task B: Frontend — Browse view details section

Verification is `tsc` build + `oxlint` + the manual checklist in Step 4 (no frontend test framework in this repo).

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/views/BrowseView.tsx`

- [ ] **Step 1: Add `getDatasetDetails` to the API client**

In `frontend/src/api/client.ts`, add after the `getRow` entry:

```ts
  getDatasetDetails: (dsId: string) =>
    request<any>(`/datasets/${dsId}/details`),
```

- [ ] **Step 2: Wire `BrowseView.tsx`**

(a) Add state after `const [rowError, setRowError] = useState<string | null>(null);` (line 31):

```tsx
  const [datasetDetails, setDatasetDetails] = useState<any | null>(null);
```

(b) Inside the existing first `useEffect`, after the `api.listDatasets().then(...)` block (which ends `});` at line 44), add the fire-and-forget fetch:

```tsx
      api.getDatasetDetails(p.dataset_id).then(setDatasetDetails).catch(() => {});
```

So the effect body becomes:

```tsx
    api.getProject(projectId, user.user_id).then((p) => {
      setProjectColor(p.color || '#F97316');
      setProjectName(p.name || '');
      setAnnotationFields(p.annotation_fields || []);
      setMlEnabled(!!p.ml_enabled);
      setMlMode(p.ml_mode || '');
      api.listDatasets().then((res) => {
        const ds = res.datasets.find((d: any) => d.id === p.dataset_id);
        if (ds) setDatasetColumns(ds.columns || []);
      });
      api.getDatasetDetails(p.dataset_id).then(setDatasetDetails).catch(() => {});
    });
```

(c) Render the section between the header row (the `</div>` closing the
title/FilterBar flex container, currently line 121) and the batch-result
banner (`{batchResult && !batchRunning && (` currently line 123):

```tsx
        {datasetDetails && (
          <DatasetDetailsSection details={datasetDetails} />
        )}
```

(d) Add the local helper component at the end of the file, after the
default-export component's closing brace:

```tsx
function DatasetDetailsSection({ details }: { details: any }) {
  const d = details.dataset;
  const projects = details.projects;
  return (
    <details className="mb-4 group">
      <summary className="text-sm font-medium text-[var(--color-text-muted)] cursor-pointer hover:text-[var(--color-text)] select-none">
        Dataset: {d.name || d.source} · {d.num_rows.toLocaleString()} rows · {projects.length} {projects.length === 1 ? "project" : "projects"}
      </summary>
      <div className="mt-3 bg-white rounded-xl border border-[var(--color-border)] p-4 shadow-sm space-y-3">
        <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
          <span className="text-[var(--color-text-muted)]">Source</span>
          <span className="text-[var(--color-text)] break-all">{d.source}</span>
          <span className="text-[var(--color-text-muted)]">Split</span>
          <span className="text-[var(--color-text)]">{d.split || '—'}</span>
          <span className="text-[var(--color-text-muted)]">Rows</span>
          <span className="text-[var(--color-text)]">{d.num_rows.toLocaleString()}</span>
          <span className="text-[var(--color-text-muted)]">Added</span>
          <span className="text-[var(--color-text)]">{new Date(d.created_at).toLocaleDateString()}</span>
        </div>
        <div>
          <h4 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-2">Projects using this dataset</h4>
          {projects.map((proj: any) => (
            <div key={proj.id} className="flex items-center gap-2 text-sm py-1">
              <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: proj.color }} />
              <span className="font-medium text-[var(--color-text)]">{proj.name}</span>
              <span className="text-[var(--color-text-muted)]">
                {proj.annotated_rows} rows annotated · {proj.annotations} annotations · {proj.predictions} predictions
              </span>
            </div>
          ))}
        </div>
        <p className="text-sm text-[var(--color-text-muted)] border-t border-[var(--color-border)] pt-2">
          Totals: {details.totals.annotations} annotations · {details.totals.predictions} predictions
        </p>
      </div>
    </details>
  );
}
```

Behavior notes:
- Collapsed by default (`<details>` without `open`).
- Hidden entirely until the fetch resolves; a failed fetch leaves
  `datasetDetails` null → section stays hidden, no toast, no impact on rows.
- `d.name` is null for non-HF sources — the summary falls back to `source`;
  a missing split renders `—`.
- Zero projects renders normally (empty subsection, zero totals) — that is a
  valid state, not an error.

- [ ] **Step 3: Type-check and lint**

```bash
cd frontend && npm run build && npm run lint
```

Expected: build succeeds; no NEW lint findings in the two touched files.

- [ ] **Step 4: Manual check (controller does the browser pass)**

Checklist (browser, dev servers per README.md):
1. Open Browse for a project: collapsed line shows `Dataset: <name/source> · <n> rows · <k> projects`.
2. Expand: meta grid correct; each project row shows the right counts (spot-check against the filter bar's "annotated by anyone" filter total); totals row correct.
3. With no projects sharing the dataset: summary says "1 project", expanded list shows only that project.
4. Section absent while loading and when the endpoint is unreachable (e.g. stop the backend once and reload).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/views/BrowseView.tsx
git commit -m "feat: add dataset details section to Browse view"
```

---

### Task C: Final verification

- [ ] **Step 1: Full backend suite**

```bash
cd backend && uv run pytest ../tests/backend -q
```

Expected: all pass.

- [ ] **Step 2: Final git check**

```bash
git status --short   # expect clean (untracked plan doc excepted)
git log --oneline -3
```
