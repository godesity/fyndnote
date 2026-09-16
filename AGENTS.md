# Agent conventions

## Python
- Use `uv` for all Python dependency management
- Run Python scripts with `uv run python <script>` instead of invoking Python directly

# Anchored Summary — fyndnote (complete)

## Goal
Build a general-purpose ML dataset annotation tool with FastAPI backend, React frontend, SQLite storage, and react-live template engine.

## Status: ALL TASKS COMPLETE ✅ (16 original + 7 dataset import)

### Original Features
- **Backend:** FastAPI skeleton, auth, datasets, templates, annotation/project CRUD
- **Frontend:** Vite+React scaffold, auth context, login, project list, setup view, annotation context, 6 widgets, label view, browse view, routing
- **E2E:** All checks pass

### Dataset Import Feature (7 tasks)
- Source type auto-detection (HF/HTTP/file) with format validation
- Multi-source loading (HuggingFace datasets, HTTP URLs, file:// paths, browser upload)
- `POST /api/v1/datasets/upload` endpoint (multipart file upload)
- Browse rows with pagination + status filter (`all`/`annotated_by_me`/`unannotated`)
- Load New dialog in SetupView (text input + file upload + error display)
- `uploadDataset()` in frontend API client (XHR: progress bar + abort)
- 108 backend tests passing, TypeScript compiles clean

### Large-upload hardening (branch `fix/large-dataset-uploads`)
- Uploads stream to disk in 1 MiB chunks; no whole-file `bytes` buffer
  (1.1 GB CSV: peak RSS 449 MB, was ~1.4 GB; event loop stays responsive)
- `fyndnote/upload_guard.py` — pure-ASGI 413 on an over-budget `Content-Length`
  (must stay outside the handler: FastAPI parses the multipart body first)
- Caps: `MAX_UPLOAD_BYTES`, `MAX_CONCURRENT_UPLOADS` (503 past
  `MAX_UPLOAD_WAIT_SECONDS`), all advertised by `GET /api/v1/datasets/config`
- `DELETE /api/v1/datasets/{id}` (system admin) is the only path that frees
  dataset disk; `reap_orphans()` runs at startup
- compose sets `mem_limit` + `memswap_limit` (equal = no swap, else the cap is
  2x); `check_memory_budget()` warns when the caps and the limit disagree

## Git
- Branch `fix/large-dataset-uploads` off `master`
- Last commit: `4491601` — build(compose): hard memory ceiling for the app container
- `data/users.json` tracked; `data/{labeling.db,datasets/,templates/}` in .gitignore

## How to run
See `README.md`. Quick start: `uv run uvicorn fyndnote.main:app --reload` (repo root) + `cd frontend && npm run dev`
