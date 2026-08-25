# Dataset Details Section — Design

**Date:** 2026-08-25
**Status:** Approved

## Motivation

The project-delete Danger Zone now tells users the dataset and templates stay
available after a project is deleted. That raises natural questions: *which
other projects use this dataset* and *how much annotation/prediction work
exists on it*. This adds a place to answer them, anchored where users spend
their time — the Browse view.

## Overview

- **Backend:** new endpoint `GET /api/v1/datasets/{ds_id}/details` returning
  dataset metadata, every project that references the dataset (with
  per-project annotation and prediction counts), and dataset-wide totals.
- **Frontend:** a collapsed details section in `BrowseView` above the row grid
  showing that information.

Counts shown (agreed with user): per project — rows annotated by anyone,
total annotation records (all users), ML prediction rows — plus
dataset-wide totals.

## Backend

### `backend/services/dataset_service.py`

Add `DatasetService.dataset_details(cls, ds_id: str) -> dict | None`
(classmethod, matching `list_datasets`):

- Look up the dataset row (`SELECT * FROM fyndnot_datasets WHERE id = ?`);
  return `None` if missing.
- Projects: `SELECT id, name, color FROM fyndnot_projects WHERE dataset_id = ?
  ORDER BY created_at`.
- Per project:
  - `annotated_rows` = `COUNT(DISTINCT row_index)` from `fyndnot_annotations`
  - `annotations`   = `COUNT(*)` from `fyndnot_annotations`
  - `predictions`   = `COUNT(*)` from `fyndnot_ml_annotations`
- Totals: sum of `annotations` and `predictions` across the dataset's projects.

Response shape:

```python
{
    "dataset": {
        "id": str, "source": str, "source_type": str, "source_format": str,
        "name": str | None, "split": str | None, "num_rows": int,
        "created_at": str,
    },
    "projects": [
        {"id": str, "name": str, "color": str,
         "annotated_rows": int, "annotations": int, "predictions": int},
    ],
    "totals": {"annotations": int, "predictions": int},
}
```

DB access via `get_db()` with commit-free read-only queries, single connection
closed at the end — same lifecycle pattern as `list_datasets`.

### `backend/routers/datasets.py`

```python
@router.get("/datasets/{ds_id}/details")
def dataset_details(ds_id: str):
    details = DatasetService.dataset_details(ds_id)
    if details is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return details
```

No path conflict with the existing `/datasets/{ds_id}/rows/...` routes
(literal `details` vs `rows`).

## Frontend

### `frontend/src/api/client.ts`

```ts
getDatasetDetails: (dsId: string) =>
  request<any>(`/datasets/${dsId}/details`),
```

### `frontend/src/views/BrowseView.tsx`

- New state `const [datasetDetails, setDatasetDetails] = useState<any | null>(null)`.
- Inside the existing `getProject(...).then((p) => ...)` effect, after the
  current logic, fetch fire-and-forget:
  `api.getDatasetDetails(p.dataset_id).then(setDatasetDetails).catch(() => {});`
  — a failure must never block or error the main browse view; the section
  simply stays hidden.
- Collapsed `<details>` section rendered between the header row (title +
  FilterBar) and the batch-result banner, only when `datasetDetails` has
  loaded:
  - **Summary line (collapsed):**
    `Dataset: {name || source} · {num_rows} rows · {n} projects` (n
    pluralized). Styling matches the existing `<details>` pattern used in
    `EditProjectView` ("Available widgets").
  - **Expanded panel:** white rounded card containing:
    1. Meta grid (two-column label/value): Source, Split, Rows, Added (date).
    2. **Projects using this dataset** subsection: one row per project —
       color dot, project name, `{annotated_rows} rows annotated ·
       {annotations} annotations · {predictions} predictions`.
    3. Totals row at the bottom: `Totals: {annotations} annotations ·
       {predictions} predictions`.
- The section's JSX is implemented as a local `function
  DatasetDetailsSection({ details })` at the bottom of `BrowseView.tsx`
  (single consumer; keeps the main render readable; no new file).
- `dataset.name` is `null` for non-HF sources — summary and meta fall back to
  `source` (`—` for a missing split).

## Error handling

- Unknown `ds_id` → 404 (backend).
- Frontend: any fetch error → section hidden, no toast, no impact on rows.
- Deleting all projects of a dataset leaves `projects: []` — section renders
  with "0 projects" and zero totals (valid state, not an error).

## Testing

### Backend — `tests/backend/test_datasets.py`

New `test_dataset_details` (hermetic, no network — use a local CSV via
`file://` like `test_load_file_csv`, 2 rows):

1. `POST /api/v1/datasets/load` with `file://` CSV → `ds_id`.
2. Create a template; create two projects on `ds_id`.
3. Project A: users `alice` and `bob` both annotate row 0 (→
   `annotated_rows: 1, annotations: 2`).
4. Project B: `alice` annotates rows 0 and 1 (→
   `annotated_rows: 2, annotations: 2`).
5. Insert ML predictions directly via `get_db()` (as in
   `test_delete_project`'s assertions): 1 row for A, 2 rows for B, with
   columns `(project_id, row_index, annotator, data, created_at,
   updated_at)`.
6. `GET /api/v1/datasets/{ds_id}/details` → 200:
   - `dataset.num_rows == 2`, `dataset.source` ends with `.csv`
   - A: `{annotated_rows: 1, annotations: 2, predictions: 1}`
   - B: `{annotated_rows: 2, annotations: 2, predictions: 2}`
   - `totals == {annotations: 4, predictions: 3}`
7. `GET /api/v1/datasets/does-not-exist/details` → 404.

### Frontend

- `npm run build` + `npm run lint` pass.
- Manual: open Browse for a project; collapsed summary line shows correct
  counts; expanding shows meta, per-project rows, totals; hidden before data
  arrives and when the endpoint errors.

## Out of scope

Per-user annotation breakdown, navigation links from project names to
projects, showing the section in Setup/Settings, dataset deletion, caching of
the endpoint.
