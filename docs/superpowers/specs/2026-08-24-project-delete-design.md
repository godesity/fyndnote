# Project Delete — Design

**Date:** 2026-08-24
**Status:** Approved

## Overview

Users can currently create, edit, and browse projects, but there is no way to
delete one. This adds a **Danger Zone** section to the project Settings view
(`EditProjectView`) with a **Delete Project** button. Clicking it opens a
confirmation dialog where the user must type `delete` (exact match) before the
delete action becomes available.

The backend already has a `DELETE /projects/{pid}` endpoint, but it is rough:
no 404 for missing projects and inline SQL outside the service layer. This
change hardens it as well.

Shared datasets and templates are never deleted; projects reference them and
other projects may still use them.

## Backend

### `backend/services/annotation_service.py`

Add `AnnotationService.delete_project(pid: str) -> bool`:

- One DB connection via `get_db()`.
- Check the project exists first (`SELECT 1 FROM fyndnot_projects WHERE id = ?`);
  return `False` if not.
- Delete, in order: `fyndnot_annotations`, `fyndnot_ml_annotations`,
  `fyndnot_project_permissions`, `fyndnot_projects` — all where
  `project_id = ?` / `id = ?`.
- `commit()`, `close()`, return `True`.

### `backend/routers/projects.py`

Rework `delete_project`:

```python
@router.delete("/projects/{pid}")
def delete_project(pid: str):
    if not AnnotationService.delete_project(pid):
        raise HTTPException(status_code=404, detail="project not found")
    return {"status": "deleted"}
```

The endpoint keeps its existing 200 `{"status": "deleted"}` response shape.

## Frontend

### `frontend/src/api/client.ts`

Add to `api`:

```ts
deleteProject: (id: string) => request<any>(`/projects/${id}`, { method: "DELETE" }),
```

### `frontend/src/components/Dialog.tsx` (new)

Generic modal shell extracted from `LoadTemplateDialog.tsx` (today the
overlay/panel markup is inline there; no shared dialog component exists).

Props:

- `title: string`
- `onClose: () => void` — invoked on backdrop click, Escape key, or ✕ button.
  Escape handling is a small addition over today's inline shell (which only
  closes via backdrop click or ✕); it standardizes behavior.
- `children: ReactNode`
- `minWidth?: string` — panel `minWidth` (existing shell uses `700px`, which
  becomes the default)
- `closeOnBackdrop?: boolean` — default `true`; when `false`, backdrop clicks
  and Escape do not close (used for the dangerous delete dialog)

Behavior / appearance matches the existing `LoadTemplateDialog` shell exactly:

- Backdrop: `position: fixed; inset: 0; background: rgba(0,0,0,0.4);`
  centered flex, `zIndex: 1000`, click → `onClose` (unless disabled).
- Panel: inline styles matching the existing shell exactly, with the width
  prop parameterized: `background: #fff, borderRadius: 8, padding: 24,
  minWidth: <minWidth prop>, maxWidth: 900, width: "85vw",
  maxHeight: 85vh, display: flex, flexDirection: column, position: relative`.
- ✕ close button top-right, same size/colors/hover as today.
- `title` rendered as `<h3 style={{ margin: "0 0 16px" }}>`.
- Panel click must not propagate to the backdrop (existing pattern).

### `frontend/src/components/LoadTemplateDialog.tsx` (refactored)

Outer shell replaced by `<Dialog title="Load Template" onClose={onClose}>…</Dialog>`
(default `minWidth` 700px) with the existing filter pills / two-column body as
children. No visual change; file gets shorter.

### `frontend/src/views/EditProjectView.tsx`

New **Danger Zone** section after the ML Backend section:

- Card with a red border (`border-2 border-red-300`-style, consistent with the
  card styling of the other sections), white background.
- Heading **Danger Zone** (red text), description:
  "Deletes the project and all its annotations permanently. The dataset and
  templates stay available for other or new projects."
- Red **Delete Project** button (`bg-red-500 text-white`, hover darker, same
  size/shape as section buttons).
- Clicking opens `DeleteProjectDialog`.

### `frontend/src/components/DeleteProjectDialog.tsx` (new)

Uses the `Dialog` shell with `title="Delete project"`, `closeOnBackdrop=false`,
`minWidth="460px"`.

Content:

- Body text: "You are about to delete **{projectName}**. This will permanently
  remove all annotations for this project."
- Input field with label `Type "delete" to confirm`.
- Footer with **Cancel** (secondary style) and **Delete** (red, primary)
  buttons.

State machine:

- `confirmText: string` — matches when `confirmText.trim() === "delete"`
  (case-sensitive exact match, whitespace trimmed).
- `deleting: boolean` — while the `api.deleteProject` request is in flight:
  Delete button label "Deleting…", both buttons disabled.
- `error: string | null` — on `ApiError`, message shown inline above the footer.
- Dialog is closed by Cancel, ✕, or success; never by backdrop/Escape.

On confirm:

1. `await api.deleteProject(projectId)`
2. `window.location.hash = "#/projects"` (same navigation pattern as `handleSave`)
3. Close dialog (unmount) — the view navigates away.

## Error handling

- **Delete of nonexistent project** (e.g. deleted in another tab): backend
  returns 404; dialog shows the error message, remains open, confirm input is
  cleared (Delete button returns to disabled), error clears on next attempt.
- **Network failure**: `ApiError` message shown inline; dialog stays open.
- Dialog never swallows errors silently.

## Testing

### Backend (`tests/backend/test_projects.py`)

New test `test_delete_project` following the existing TestClient pattern:

1. Create a dataset (small local source per existing fixtures/conftest),
   template, project.
2. Submit an annotation on row 0.
3. `DELETE /api/v1/projects/{pid}` → 200 `{"status": "deleted"}`.
4. `GET /api/v1/projects/{pid}?user_id=...` → 404.
5. `DELETE` again → 404.
6. The dataset still exists (`GET /api/v1/datasets` includes it).

### Frontend

- `npm run build` (tsc + vite) passes.
- `npm run lint` (oxlint) passes.
- Manual: open a project's Settings, verify Danger Zone renders; cancel path
  works; typing `delete` enables the button; delete returns to the project list
  and the project no longer appears.

## Out of scope

- Deleting datasets, templates, or user accounts.
- Soft delete / restore / trash.
- Permission/role checks on delete (no RBAC enforcement exists on the current
  project endpoints).
