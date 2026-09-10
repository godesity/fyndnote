#!/usr/bin/env python3
"""Build the fyndnote wheel with the built frontend and docs bundled.

Run from the repo root:
    uv run python tools/build_wheel.py

Steps:
  1. Ensure node_modules for frontend/ and root (docs deps) — `npm ci` when missing.
  2. Build assets: `npm --prefix frontend run build` and `npm run docs:build`.
  3. Sync dists into fyndnote/web/{frontend,docs} (package data).
  4. `uv build` -> dist/fyndnote-<ver>-py3-none-any.whl + sdist.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(*args: str, cwd: Path) -> None:
    print(f"[wheel] $ {' '.join(args)}  (cwd={cwd.relative_to(ROOT)})")
    result = subprocess.run(args, cwd=cwd)
    if result.returncode != 0:
        sys.exit(f"[wheel] FAILED ({result.returncode}): {' '.join(args)}")


def main() -> None:
    frontend = ROOT / "frontend"
    node_modules = ROOT / "node_modules"

    if not (frontend / "node_modules").is_dir():
        run("npm", "ci", cwd=frontend)
    if not node_modules.is_dir():
        run("npm", "ci", cwd=ROOT)

    run("npm", "--prefix", "frontend", "run", "build", cwd=ROOT)
    run("npm", "run", "docs:build", cwd=ROOT)

    frontend_dist = frontend / "dist"
    docs_dist = ROOT / "docs" / ".vitepress" / "dist"
    if not frontend_dist.is_dir():
        sys.exit(f"[wheel] missing build output: {frontend_dist}")
    if not docs_dist.is_dir():
        sys.exit(f"[wheel] missing build output: {docs_dist}")

    web = ROOT / "fyndnote" / "web"
    for name in ("frontend", "docs"):
        target = web / name
        if target.exists():
            shutil.rmtree(target)
    web.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(frontend_dist), str(web / "frontend"))
    shutil.copytree(str(docs_dist), str(web / "docs"))
    print(f"[wheel] synced assets -> {web.relative_to(ROOT)}/frontend|docs")

    run("uv", "build", cwd=ROOT)
    print("[wheel] done — artifacts in dist/")


if __name__ == "__main__":
    main()
