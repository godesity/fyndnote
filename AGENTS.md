# Agent conventions

## Python
- Use `uv` for all Python dependency management
- Run Python scripts with `uv run python <script>` instead of invoking Python directly

# Anchored Summary — Labeling Tool (complete)

## Goal
Build a general-purpose ML dataset annotation tool with FastAPI backend, React frontend, SQLite storage, and react-live template engine.

## Status: ALL 16 TASKS COMPLETE ✅
- **Tasks 1–5 (Backend):** FastAPI skeleton, auth, datasets, templates, annotation/project CRUD — 7 tests pass
- **Tasks 6–15 (Frontend):** Vite+React scaffold, auth context, login, project list, setup view, annotation context, 6 widgets, label view, browse view, routing — TypeScript builds clean
- **Task 16 (E2E):** All checks pass

## Git
- 22 commits on `master` from initial skeleton through E2E verification
- Last commit: `3567021` — README with quick start
- `data/users.json` tracked; `data/{labeling.db,datasets/,templates/}` in .gitignore

## How to run
See `README.md`. Quick start: `cd backend && uv run uvicorn main:app --reload` + `cd frontend && npm run dev`
