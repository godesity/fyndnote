#!/usr/bin/env python3
"""Start backend + frontend dev servers with a single command."""

import argparse
import os
import sys
import time
import signal
import subprocess
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BACKEND_DIR = os.path.join(ROOT, "backend")
FRONTEND_DIR = os.path.join(ROOT, "frontend")
MOCK_ML_DIR = os.path.join(ROOT, "mock-ml-backend")

processes: list[subprocess.Popen] = []
interrupted = False


def run_install(label: str, cwd: str, *args: str) -> bool:
    print(f"[{label}] Installing dependencies...")
    result = subprocess.run(args, cwd=cwd)
    if result.returncode != 0:
        print(f"[{label}] Install failed (exit code {result.returncode})")
        return False
    print(f"[{label}] Install complete")
    return True


def stream_output(label: str, stream, prefix: str):
    for line in iter(stream.readline, ""):
        if interrupted:
            break
        sys.stdout.write(f"{prefix}{line}")
        sys.stdout.flush()


def start_server(label: str, cwd: str, *args: str) -> subprocess.Popen | None:
    try:
        proc = subprocess.Popen(
            args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        processes.append(proc)
        prefix = f"[{label}] "
        t = threading.Thread(target=stream_output, args=(label, proc.stdout, prefix), daemon=True)
        t.start()
        return proc
    except FileNotFoundError as e:
        print(f"[{label}] Failed to start: {e}")
        return None


def cleanup():
    global interrupted
    interrupted = True
    for proc in processes:
        if proc.poll() is None:
            try:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                proc.terminate()
    time.sleep(2)
    for proc in processes:
        if proc.poll() is None:
            try:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()


def main():
    global interrupted

    parser = argparse.ArgumentParser(description="Start label-tool dev servers")
    parser.add_argument("--no-backend", action="store_true", help="Skip backend (port 8000)")
    parser.add_argument("--no-frontend", action="store_true", help="Skip frontend (port 5173)")
    parser.add_argument("--no-mock-ml", action="store_true", help="Skip mock ML backend (port 8081)")
    args = parser.parse_args()

    want_backend = not args.no_backend
    want_frontend = not args.no_frontend
    want_mock_ml = not args.no_mock_ml

    if not (want_backend or want_frontend or want_mock_ml):
        print("[dev] All services disabled — nothing to start.")
        sys.exit(1)

    if want_frontend:
        ok = run_install("frontend", FRONTEND_DIR, "npm", "install")
        if not ok:
            sys.exit(1)

    if want_backend:
        ok = run_install("backend", BACKEND_DIR, "uv", "sync")
        if not ok:
            sys.exit(1)

    if want_mock_ml:
        ok = run_install("mock-ml", MOCK_ML_DIR, "uv", "sync")
        if not ok:
            sys.exit(1)

    be = start_server("backend", BACKEND_DIR, "uv", "run", "uvicorn", "main:app", "--reload", "--port", "8000") if want_backend else None
    fe = start_server("frontend", FRONTEND_DIR, "npm", "run", "dev") if want_frontend else None
    ml = start_server("mock-ml", MOCK_ML_DIR, "uv", "run", "uvicorn", "main:app", "--reload", "--port", "8081") if want_mock_ml else None

    if (want_backend and not be) or (want_frontend and not fe) or (want_mock_ml and not ml):
        cleanup()
        sys.exit(1)

    print()
    if want_backend:
        print("  Backend:  http://localhost:8000")
    if want_frontend:
        print("  Frontend: http://localhost:5173")
    if want_mock_ml:
        print("  Mock ML:  http://localhost:8081/inference")
    if want_backend:
        print("  API docs: http://localhost:8000/docs")
    print("  Press Ctrl+C to stop all servers\n")

    signal.signal(signal.SIGINT, lambda s, f: cleanup())
    signal.signal(signal.SIGTERM, lambda s, f: cleanup())

    running = [p for p in (be, fe, ml) if p is not None]

    try:
        while not interrupted:
            for p in running:
                if p.poll() is not None:
                    print("[dev] A server stopped unexpectedly. Shutting down...")
                    cleanup()
                    sys.exit(1)
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()
        print("\n[dev] Stopped")


if __name__ == "__main__":
    main()
