# Agent conventions

## Python
- Use `uv` for all Python dependency management
- Run Python scripts with `uv run python <script>` instead of invoking Python directly

# Anchored Summary — Labeling Tool (complete)

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
- `uploadDataset()` in frontend API client
- 22 backend tests passing, TypeScript compiles clean

## Git
- 31 commits on `master`
- Last commit: `2287015` — docs: spec and test fixtures for dataset import feature
- `data/users.json` tracked; `data/{labeling.db,datasets/,templates/}` in .gitignore

## How to run
See `README.md`. Quick start: `cd backend && uv run uvicorn main:app --reload` + `cd frontend && npm run dev`
