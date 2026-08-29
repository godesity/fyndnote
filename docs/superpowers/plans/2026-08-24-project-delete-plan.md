# Project Delete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Danger Zone to the project Settings page with a Delete button that opens a confirm dialog requiring the user to type `delete`, backed by a hardened `DELETE /projects/{pid}` endpoint.

**Architecture:** Move the project-deletion SQL into `AnnotationService.delete_project` (returns False if the project is missing → router raises 404). On the frontend, extract the modal shell from `LoadTemplateDialog` into a generic `Dialog` component (adds Escape-key close, `closeOnBackdrop` flag), add `api.deleteProject()`, and add a `DeleteProjectDialog` + Danger Zone section to `EditProjectView`.

**Tech Stack:** FastAPI + SQLite (SQLite via `get_db()` from `backend/database.py`), React 19 + Vite + Tailwind v4 (inline styles for modals, Tailwind classes for sections — match the existing code), tests via pytest + `fastapi.testclient`.

Spec: `docs/superpowers/specs/2026-08-24-project-delete-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/services/annotation_service.py` | Modify | Add `AnnotationService.delete_project(pid) -> bool` |
| `backend/routers/projects.py` | Modify | Rebuild `DELETE /projects/{pid}` on the service; 404 when missing; drop unused `get_db` import |
| `tests/backend/test_projects.py` | Modify | Add `test_delete_project` |
| `frontend/src/components/Dialog.tsx` | Create | Generic modal shell (backdrop, panel, ✕, title, Escape) |
| `frontend/src/components/LoadTemplateDialog.tsx` | Modify | Use `Dialog` shell instead of inline markup |
| `frontend/src/api/client.ts` | Modify | Add `api.deleteProject(id)` |
| `frontend/src/components/DeleteProjectDialog.tsx` | Create | Type-to-confirm delete dialog |
| `frontend/src/views/EditProjectView.tsx` | Modify | Danger Zone section + dialog wiring |

---

### Task 1: Backend — `delete_project` service + 404 (TDD)

**Files:**
- Test: `tests/backend/test_projects.py` (append)
- Modify: `backend/services/annotation_service.py` (add method between `update_project` and `get_project`, i.e. before line 402 `def get_project`)
- Modify: `backend/routers/projects.py` (line 4 import; lines 157-166 endpoint)

- [ ] **Step 1: Write the failing test**

Append to `tests/backend/test_projects.py`:

```python
def test_delete_project(client):
    ds_resp = client.post("/api/v1/datasets/load", json={"source": "stanfordnlp/imdb", "split": "train"})
    ds_id = ds_resp.json()["id"]
    t_resp = client.post("/api/v1/templates", json={"name": "del-tpl", "source": "<div>{data.text}</div>"})
    t_id = t_resp.json()["id"]
    p_resp = client.post("/api/v1/projects", json={"name": "del-test", "dataset_id": ds_id, "template_id": t_id})
    assert p_resp.status_code == 201
    pid = p_resp.json()["id"]

    # Annotate one row so there is related data to delete
    a_resp = client.post(f"/api/v1/projects/{pid}/annotate", json={
        "row_index": 0, "user_id": "alice", "data": {"sentiment": "positive"}
    })
    assert a_resp.status_code == 201
    assert client.get(f"/api/v1/projects/{pid}?user_id=alice").status_code == 200

    # Delete
    d_resp = client.delete(f"/api/v1/projects/{pid}")
    assert d_resp.status_code == 200
    assert d_resp.json() == {"status": "deleted"}

    # Project gone; annotations gone with it
    assert client.get(f"/api/v1/projects/{pid}?user_id=alice").status_code == 404
    assert client.delete(f"/api/v1/projects/{pid}").status_code == 404

    # Dataset survived
    ds_list = client.get("/api/v1/datasets").json()["datasets"]
    assert any(d["id"] == ds_id for d in ds_list)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd backend && uv run pytest ../tests/backend/test_projects.py::test_delete_project -v
```

Expected: FAIL — `assert client.delete(...).status_code == 404` fails with `assert 200 == 404`, because the current endpoint deletes nothing for a missing project and still returns 200.

- [ ] **Step 3: Implement `AnnotationService.delete_project`**

Add this method in `backend/services/annotation_service.py` right before `get_project` (inside `class AnnotationService`):

```python
    @staticmethod
    def delete_project(pid: str) -> bool:
        db = get_db()
        row = db.execute("SELECT 1 FROM fyndnot_projects WHERE id = ?", (pid,)).fetchone()
        if not row:
            db.close()
            return False
        db.execute("DELETE FROM fyndnot_annotations WHERE project_id = ?", (pid,))
        db.execute("DELETE FROM fyndnot_ml_annotations WHERE project_id = ?", (pid,))
        db.execute("DELETE FROM fyndnot_project_permissions WHERE project_id = ?", (pid,))
        db.execute("DELETE FROM fyndnot_projects WHERE id = ?", (pid,))
        db.commit()
        db.close()
        return True
```

- [ ] **Step 4: Rebuild the router endpoint**

In `backend/routers/projects.py`, replace the endpoint at lines 157-166:

```python
@router.delete("/projects/{pid}")
def delete_project(pid: str):
    if not AnnotationService.delete_project(pid):
        raise HTTPException(status_code=404, detail="project not found")
    return {"status": "deleted"}
```

And remove the now-unused import on line 4:

```python
from database import get_db
```

(the whole line goes away; `get_db` was only used by the old endpoint body).

- [ ] **Step 5: Run the test to verify it passes**

```bash
cd backend && uv run pytest ../tests/backend/test_projects.py::test_delete_project -v
```

Expected: PASS.

- [ ] **Step 6: Run the full backend suite**

```bash
cd backend && uv run pytest ../tests/backend -v
```

Expected: all tests pass (previously 22, now 23).

- [ ] **Step 7: Commit**

```bash
git add tests/backend/test_projects.py backend/services/annotation_service.py backend/routers/projects.py
git commit -m "feat: harden DELETE /projects/{pid} with service method and 404"
```

---

### Task 2: Frontend — extract generic `Dialog` shell

There is no frontend test framework in this repo (no vitest/jest in `frontend/package.json`), so this refactor is verified by `tsc` build + `oxlint` + manual check. Keep this task behavior-neutral apart from the new Escape-key close on the template dialog.

**Files:**
- Create: `frontend/src/components/Dialog.tsx`
- Modify: `frontend/src/components/LoadTemplateDialog.tsx` (lines 34-63 top shell; lines 184-185 bottom closing tags)

- [ ] **Step 1: Create `frontend/src/components/Dialog.tsx`**

```tsx
import { useEffect, type ReactNode } from "react";

interface DialogProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
  minWidth?: string;
  closeOnBackdrop?: boolean;
}

export default function Dialog({
  title,
  onClose,
  children,
  minWidth = "700px",
  closeOnBackdrop = true,
}: DialogProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && closeOnBackdrop) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeOnBackdrop, onClose]);

  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
      }}
      onClick={closeOnBackdrop ? onClose : undefined}
    >
      <div
        style={{
          background: "#fff", borderRadius: 8, padding: 24,
          minWidth, maxWidth: 900, width: "85vw",
          maxHeight: "85vh", display: "flex", flexDirection: "column", position: "relative",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          style={{
            position: "absolute", top: 12, right: 12,
            border: "none", background: "none",
            fontSize: 20, cursor: "pointer", color: "#666",
            lineHeight: 1, padding: "4px 8px", borderRadius: 4,
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "#000")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "#666")}
        >
          ✕
        </button>
        <h3 style={{ margin: "0 0 16px" }}>{title}</h3>
        {children}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Refactor `LoadTemplateDialog.tsx` to use it**

Three edits:

(a) Add the import after the existing `import { useState } from "react";` (line 1):

```tsx
import Dialog from "./Dialog";
```

(b) Replace the current JSX from `return (` through the title line (lines 34-63), i.e. this block:

```tsx
  return (
    <div
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#fff", borderRadius: 8, padding: 24,
          minWidth: 700, maxWidth: 900, width: "85vw",
          maxHeight: "85vh", display: "flex", flexDirection: "column", position: "relative",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          style={{
            position: "absolute", top: 12, right: 12,
            border: "none", background: "none",
            fontSize: 20, cursor: "pointer", color: "#666",
            lineHeight: 1, padding: "4px 8px", borderRadius: 4,
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "#000")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "#666")}
        >
          ✕
        </button>
        <h3 style={{ margin: "0 0 16px" }}>Load Template</h3>
```

with:

```tsx
  return (
    <Dialog title="Load Template" onClose={onClose}>
```

Leave the body (filter pills, two-column layout, trailing blank line) at its current indentation — JSX does not require re-indentation, and keeping the diff minimal matters more.

(c) At the end of the component (current lines 184-187), the panel `</div>` and
the backdrop `</div>` collapse into a single closing tag. Replace:

```tsx
      </div>
    </div>
  );
}
```

with:

```tsx
      </div>
    </Dialog>
  );
}
```

Only the last two closing `</div>` tags disappear — the `</div>`s at lines 180, 181
(close the two-column body) stay. This 4-line block is unique in the file, so the
replacement is unambiguous.

- [ ] **Step 3: Type-check and lint**

```bash
cd frontend && npm run build && npm run lint
```

Expected: build succeeds, no lint errors.

- [ ] **Step 4: Manual check**

Start the dev servers (see `README.md`), open any project's Settings, click **Load Template**: dialog looks identical to before; ✕, backdrop click, and now Escape all close it.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/Dialog.tsx frontend/src/components/LoadTemplateDialog.tsx
git commit -m "refactor: extract generic Dialog modal shell from LoadTemplateDialog"
```

---

### Task 3: Frontend — `api.deleteProject`, Danger Zone, confirm dialog

**Files:**
- Modify: `frontend/src/api/client.ts` (after the `updateProject` entry, line 88)
- Create: `frontend/src/components/DeleteProjectDialog.tsx`
- Modify: `frontend/src/views/EditProjectView.tsx`

- [ ] **Step 1: Add `deleteProject` to the API client**

In `frontend/src/api/client.ts`, add immediately after the `updateProject` entry:

```ts
  deleteProject: (id: string) =>
    request<any>(`/projects/${id}`, { method: "DELETE" }),
```

- [ ] **Step 2: Create `frontend/src/components/DeleteProjectDialog.tsx`**

```tsx
import { useState } from "react";
import Dialog from "./Dialog";
import { api, ApiError } from "../api/client";

interface Props {
  projectName: string;
  projectId: string;
  onClose: () => void;
}

export default function DeleteProjectDialog({ projectName, projectId, onClose }: Props) {
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const confirmed = confirmText.trim() === "delete";

  const handleDelete = async () => {
    if (!confirmed || deleting) return;
    setDeleting(true);
    setError(null);
    try {
      await api.deleteProject(projectId);
      window.location.hash = "#/projects";
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      setConfirmText("");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Dialog title="Delete project" onClose={onClose} minWidth="460px" closeOnBackdrop={false}>
      <p className="text-sm text-[var(--color-text)] mb-4">
        You are about to delete <strong>{projectName}</strong>. This will permanently remove
        the project and all annotations made on it. This action cannot be undone.
      </p>
      <label className="text-xs font-medium text-[var(--color-text-muted)] block mb-1">
        Type "delete" to confirm
      </label>
      <input
        value={confirmText}
        onChange={(e) => setConfirmText(e.target.value)}
        className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-red-400 mb-4"
      />
      {error && (
        <p className="text-sm text-red-600 mb-4">{error}</p>
      )}
      <div className="flex justify-end gap-2">
        <button
          onClick={onClose}
          disabled={deleting}
          className="px-4 py-2 rounded-lg border border-[var(--color-border)] bg-white text-sm text-[var(--color-text)] hover:bg-gray-50 transition-all disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          onClick={handleDelete}
          disabled={!confirmed || deleting}
          className="px-4 py-2 rounded-lg bg-red-500 text-white font-medium text-sm hover:bg-red-600 transition-all shadow-sm disabled:opacity-50"
        >
          {deleting ? "Deleting..." : "Delete"}
        </button>
      </div>
    </Dialog>
  );
}
```

Behavior notes:
- Delete button only enabled when the trimmed input equals `delete` exactly (case-sensitive).
- Backdrop click and Escape do NOT close the dialog (`closeOnBackdrop={false}`) so a stray click can't dismiss a dangerous action; Cancel/✕/success do.
- While in flight: button label "Deleting...", both buttons disabled.
- On error: inline message shown, confirm input cleared (button back to disabled).

- [ ] **Step 3: Wire the Danger Zone into `EditProjectView.tsx`**

(a) Add the import after the existing `LoadTemplateDialog` import (line 8):

```tsx
import DeleteProjectDialog from "../components/DeleteProjectDialog";
```

(b) Add state next to the other dialog state (after line 36 `const [showTemplateDialog, setShowTemplateDialog] = useState(false);`):

```tsx
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
```

(c) Insert the Danger Zone section and dialog render after the ML Backend section's closing `</section>` (line 253) and before the container's closing `</div>` (line 254):

```tsx
        {/* Danger Zone */}
        <section className="mb-6">
          <div className="bg-white rounded-xl border-2 border-red-300 p-5 shadow-sm">
            <h3 className="text-sm font-semibold text-red-600 mb-1">Danger Zone</h3>
            <p className="text-sm text-[var(--color-text-muted)] mb-4">
              Deleting a project permanently removes the project and all annotations made
              on it. The underlying dataset and templates are kept.
            </p>
            <button
              onClick={() => setShowDeleteDialog(true)}
              className="px-5 py-2.5 rounded-lg bg-red-500 text-white font-medium text-sm hover:bg-red-600 transition-all shadow-sm"
            >
              Delete Project
            </button>
          </div>
        </section>

        {showDeleteDialog && (
          <DeleteProjectDialog
            projectName={projectName}
            projectId={projectId}
            onClose={() => setShowDeleteDialog(false)}
          />
        )}
```

- [ ] **Step 4: Type-check and lint**

```bash
cd frontend && npm run build && npm run lint
```

Expected: build succeeds, no lint errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/components/DeleteProjectDialog.tsx frontend/src/views/EditProjectView.tsx
git commit -m "feat: add danger-zone project delete with type-to-confirm dialog"
```

---

### Task 4: End-to-end verification

- [ ] **Step 1: Run the full backend suite**

```bash
cd backend && uv run pytest ../tests/backend -v
```

Expected: all pass.

- [ ] **Step 2: Manual E2E**

Start both servers per `README.md` (`cd backend && uv run uvicorn main:app --reload` and `cd frontend && npm run dev`). Then:

1. Log in and create a new project (any dataset + template).
2. Open its Settings (`#/projects/<id>/settings` route as used by existing routing). The page shows the red-outlined **Danger Zone** card at the bottom.
3. Click **Delete Project**: dialog opens with the project name and `Type "delete" to confirm` input. Verify:
   - Delete button disabled with empty/partial/`Delete`/`DELETE` input; enabled with `delete` (and with leading/trailing spaces).
   - Clicking the backdrop does nothing; Escape does nothing.
   - Cancel and ✕ close the dialog; the project still exists in the list.
4. Reopen, type `delete`, click **Delete**: button shows "Deleting...", then the app lands on the project list and the project is gone. Its annotations are gone (create a second project on the same dataset — previously annotated rows show as unannotated).
5. **Load Template** still renders and behaves as before (refactor regression check).

- [ ] **Step 3: Final commit check**

```bash
git status --short   # expect clean
git log --oneline -4
```

Expected: the three feature commits on top of the SSO commit.
