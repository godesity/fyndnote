#!/usr/bin/env python3
"""Build the SPA and the docs site, then stage them as package data.

Lands the two build outputs in ``fyndnote/web/{frontend,docs}`` so that
hatchling can ship them as package data (see ``artifacts`` in pyproject.toml).

Shared by:
  * ``tools/build_wheel.py``   - manual build (always rebuilds)
  * ``hatch_build.py``         - PEP 517 build hook for ``pip install git+...``
"""

import shutil
import subprocess
import sys
from pathlib import Path


class AssetBuildError(RuntimeError):
    """A build step failed or produced no output."""


def _require_node() -> None:
    """Fail early with an actionable message instead of a cryptic npm traceback."""
    # git is needed by `npm ci` for any git-sourced npm deps
    for tool in ("git", "npm"):
        if shutil.which(tool) is None:
            raise AssetBuildError(
                f"`{tool}` is required to build the fyndnote web assets but was not "
                f"found on PATH. Install it, or pre-build the assets with "
                f"`npm run build:wheel`, or set FYNDNOTE_SKIP_WEB_BUILD=1 to build an "
                f"API-only package."
            )


def run(args: list[str], cwd: Path) -> None:
    result = subprocess.run(args, cwd=cwd, check=False)
    if result.returncode != 0:
        raise AssetBuildError(f"command failed ({result.returncode}): {' '.join(args)}")


def web_targets(root: Path) -> tuple[Path, Path]:
    web = root / "fyndnote" / "web"
    return web / "frontend", web / "docs"


def web_ready(root: Path) -> bool:
    """True when both staged asset trees look complete."""
    frontend, docs = web_targets(root)
    return (frontend / "index.html").is_file() and (docs / "index.html").is_file()


def build_web(root: Path, force: bool = False) -> None:
    """Populate ``fyndnote/web/{frontend,docs}`` from the npm build outputs.

    Args:
        root: Repository root (contains ``package.json``, ``frontend/``, ``docs/``).
        force: Rebuild even if ``fyndnote/web`` already looks complete.
    """
    root = Path(root).resolve()
    if web_ready(root) and not force:
        print(
            "[assets] fyndnote/web already populated - skipping npm build", flush=True
        )
        return

    frontend = root / "frontend"
    if not frontend.is_dir():
        raise AssetBuildError(f"missing frontend sources: {frontend}")
    _require_node()

    if not (frontend / "node_modules").is_dir():
        run(["npm", "ci"], cwd=frontend)
    if not (root / "node_modules").is_dir():
        run(["npm", "ci"], cwd=root)

    run(["npm", "--prefix", "frontend", "run", "build"], cwd=root)
    run(["npm", "run", "docs:build"], cwd=root)

    frontend_dist = frontend / "dist"
    docs_dist = root / "docs" / ".vitepress" / "dist"
    if not frontend_dist.is_dir():
        raise AssetBuildError(f"missing build output: {frontend_dist}")
    if not docs_dist.is_dir():
        raise AssetBuildError(f"missing build output: {docs_dist}")

    staged_frontend, staged_docs = web_targets(root)
    staged_docs.parent.mkdir(parents=True, exist_ok=True)
    for target in (staged_frontend, staged_docs):
        if target.exists():
            shutil.rmtree(target)
    shutil.copytree(str(frontend_dist), str(staged_frontend))
    shutil.copytree(str(docs_dist), str(staged_docs))
    print(
        f"[assets] synced -> {staged_docs.parent.relative_to(root)}/frontend|docs",
        flush=True,
    )


if __name__ == "__main__":
    try:
        build_web(Path(__file__).resolve().parent.parent, force=True)
    except AssetBuildError as exc:
        sys.exit(f"[assets] FAILED: {exc}")
