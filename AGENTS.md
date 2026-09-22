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

## Dataset display names (`name` column)
- `fyndnote_datasets.name` is the display label shown by every picker/list. It is
  NOT `hf_name` — that is the HuggingFace *config* (`""`/`NULL` on most imports),
  which repeats across repos and cannot disambiguate datasets.
- `name` is `NOT NULL` and carries a UNIQUE index (`fyndnote_datasets_name_uq`).
  Two datasets must never share a label: a picker showing `imdb`, `imdb`, `imdb`
  is unusable, and a race silently creating the Nth copy poisons the whole list.
- `metadata.create_all` skips an existing table *wholesale* — indexes included —
  so `_backfill_dataset_names()`/`_ensure_dataset_name_index()` (run before
  `create_all`) are what give an *upgraded* database both the column and the
  unique index. Adding an index to the `Table` alone only helps fresh databases.
- Write path: `DatasetService.load(..., alias=)` / `load_upload(..., alias=)`
  compute `display = alias or derive_display_name(source)`, pre-check it with
  `_require_free_name()` *before* the (possibly minutes-long) conversion so a
  duplicate fails fast, then `INSERT`. Two concurrent loads can both pass the
  pre-check, so the unique index is the real arbiter: the `INSERT` catching an
  `IntegrityError` on `name` (via `_is_unique_violation`) tears down the cache
  dir + in-memory entry and re-raises `DatasetNameConflict(name, suggested)`.
  A rejected upload never commits, so it never reserves its name.
- The router maps `DatasetNameConflict` to `409` + `{detail, suggested_name}`;
  the picker then offers "Use <suggested_name>". `GET
  /datasets/name-available?name=|source=` is the debounced pre-flight the UI
  calls (it reports `available = unique_name(base) == base`); `_require_free_name`
  stays the authoritative server-side check — the UI is advisory only.
- Never `INSERT` into `fyndnote_datasets` outside `load()`/`load_upload()`, and
  always thread the user-chosen label through the `alias` kwarg — a raw insert
  or a missing `alias` breaks the uniqueness contract the pickers rely on.

## How to run
See `README.md`. Quick start: `uv run uvicorn fyndnote.main:app --reload` (repo root) + `cd frontend && npm run dev`
