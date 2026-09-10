#!/usr/bin/env python3
"""Build the fyndnote wheel with the built frontend and docs bundled.

Run from the repo root:
    uv run python tools/build_wheel.py    # or: npm run build:wheel

Steps:
  1. Build assets via tools/build_assets.py (npm ci when needed, vite + vitepress,
     sync into fyndnote/web/{frontend,docs} as package data).
  2. `uv build` -> dist/fyndnote-<ver>-py3-none-any.whl + sdist.

The same asset build also runs automatically through hatch_build.py, so plain
`pip install git+https://...` and `python -m build` produce a UI-complete wheel too.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_assets import AssetBuildError, build_web

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    try:
        build_web(ROOT, force=True)
    except AssetBuildError as exc:
        sys.exit(f"[wheel] FAILED: {exc}")

    print("[wheel] $ uv build  (cwd=.)")
    if subprocess.run(["uv", "build"], cwd=ROOT, check=False).returncode != 0:
        sys.exit("[wheel] FAILED: uv build")
    print("[wheel] done — artifacts in dist/")


if __name__ == "__main__":
    main()
