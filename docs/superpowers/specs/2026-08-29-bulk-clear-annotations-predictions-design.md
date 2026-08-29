# Bulk-clear annotations & ML-predictions (filtered + all)

## Goal

Let admins/owners clear all annotations and ML-predictions in a filtered view, and
clear them globally. Annotators get no bulk removal.

## Permission model

Bulk-clear actions are gated to **owner/admin**:
- allowed when the user is `system_admin` globally OR has `project_admin` role for the project
- annotators get a 403 on the bulk endpoints
- per-row clear in RowDetail stays unchanged

## Backend

New endpoints in `backend/routers/projects.py`:

- `DELETE /projects/{pid}/annotations/bulk` — body `{ filter: FilterExpression[] | null }`
- `DELETE /projects/{pid}/ml-annotations/bulk` — body `{ filter: FilterExpression[] | null }`

Semantics:
- `filter === null` → delete all rows (current delete-all behavior)
- `filter` provided → resolve matching row indices by reusing the `browse_rows`
  filter pipeline (refactor into a helper `_resolve_matching_indices(pid, filter)`),
  then delete annotations/predictions only for those rows

Both endpoints check admin/owner role before deleting; return 403 for annotators.

## Frontend

- Add `clearAnnotationsBulk(filter)` / `clearPredictionsBulk(filter)` to the API client
- In BrowseView toolbar, a dropdown (visible only to admin/owner) with four actions:
  clear filtered/all annotations, clear filtered/all predictions
- Each action opens a confirmation dialog (e.g. `Clear 47 annotations? This cannot be undone`),
  then calls the API and reloads rows

## Tests

Backend tests in `tests/backend/test_projects.py`:
- bulk-clear with a filter (only matching rows deleted)
- bulk-clear with null filter (all rows deleted)
- 403 for annotator role
