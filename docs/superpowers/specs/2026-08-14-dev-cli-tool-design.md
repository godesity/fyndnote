# Dev CLI Tool Design

**Date:** 2026-08-14
**Status:** Approved

## Purpose

A single `tools/dev.py` script that installs dependencies, starts both backend and frontend dev servers, and cleans up on exit.

## Interface

```
python tools/dev.py
```

No arguments — always runs both servers. Ctrl+C stops both.

## Behavior

1. **Install phase (blocking, sequential):**
   - `cd backend && uv sync` (stdout/stderr streamed)
   - `cd frontend && npm install` (stdout/stderr streamed)
   - If either fails, print error and exit without starting servers

2. **Start phase (concurrent):**
   - Backend: `cd backend && uv run uvicorn main:app --reload --port 8000`
   - Frontend: `cd frontend && npm run dev`
   - Each spawned via `subprocess.Popen` with `start_new_session=True`
   - Dedicated thread reads stdout/stderr per process, prefixes lines with `[backend]` / `[frontend]`
   - Main thread sleeps until SIGINT

3. **Shutdown phase:**
   - Trap SIGINT via `signal.signal`
   - Send SIGTERM to each process group (`os.killpg`)
   - Wait up to 5 seconds for graceful exit, then SIGKILL
   - Exit with code 0

## File

- `tools/dev.py` — single-file script, executable, shebang `#!/usr/bin/env python3`
