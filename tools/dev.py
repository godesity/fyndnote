#!/usr/bin/env python3
"""Start backend + frontend dev servers with a single command."""

import os
import sys
import time
import signal
import subprocess
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BACKEND_DIR = os.path.join(ROOT, "backend")
FRONTEND_DIR = os.path.join(ROOT, "frontend")

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

    ok = run_install("frontend", FRONTEND_DIR, "npm", "install")
    if not ok:
        sys.exit(1)

    ok = run_install("backend", BACKEND_DIR, "uv", "sync")
    if not ok:
        sys.exit(1)

    be = start_server("backend", BACKEND_DIR, "uv", "run", "uvicorn", "main:app", "--reload", "--port", "8000")
    fe = start_server("frontend", FRONTEND_DIR, "npm", "run", "dev")

    if not be or not fe:
        cleanup()
        sys.exit(1)

    print("\n  Backend:  http://localhost:8000")
    print("  Frontend: http://localhost:5173")
    print("  API docs: http://localhost:8000/docs")
    print("  Press Ctrl+C to stop both servers\n")

    signal.signal(signal.SIGINT, lambda s, f: cleanup())
    signal.signal(signal.SIGTERM, lambda s, f: cleanup())

    try:
        while not interrupted:
            be_ok = be.poll() is None
            fe_ok = fe.poll() is None
            if not be_ok or not fe_ok:
                print("[dev] A server stopped unexpectedly. Shutting down...")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()
        print("\n[dev] Both servers stopped")


if __name__ == "__main__":
    main()
