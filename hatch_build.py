"""Hatchling custom build hook: build the SPA + docs during PEP 517 builds.

Registered in ``pyproject.toml``::

    [tool.hatch.build.hooks.custom]
    path = "hatch_build.py"

Why this exists: ``pip install git+https://github.com/godesity/fyndnote.git``
hands pip a bare clone in which ``fyndnote/web/`` does not exist (it is
gitignored generated content). Without this hook the wheel builds API-only and
``/`` and ``/fyndnote/`` 404. The hook runs the same npm builds
``tools/build_wheel.py`` runs, so the assets exist before hatchling collects
package data.

Escape hatches, in order of preference:
  * ``FYNDNOTE_SKIP_WEB_BUILD=1`` - build an API-only wheel; needs no node/npm.
  * Pre-staged ``fyndnote/web/``  - the npm build is skipped and shipped as-is.

Otherwise ``node``/``npm``/``git`` must be on PATH; a missing tool raises a
message naming all three options rather than half-packaging the UI.
"""

import importlib.util
import os
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_SKIP = "FYNDNOTE_SKIP_WEB_BUILD"
_TRUTHY = {"1", "true", "yes", "on"}


def _load_build_assets(root: Path):
    """Import ``tools/build_assets.py`` by path (build cwd is not the source root)."""
    module_path = root / "tools" / "build_assets.py"
    if not module_path.is_file():
        raise RuntimeError(f"build hook missing helper: {module_path}")
    spec = importlib.util.spec_from_file_location("fyndnote_build_assets", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FyndnoteWebHook(BuildHookInterface):
    """Builds ``fyndnote/web/{frontend,docs}`` before the wheel is assembled.

    The sdist deliberately skips the npm builds: it carries the *sources*, and
    consumers of the sdist build the assets themselves.
    """

    def _info(self, message: str) -> None:
        if self.app is not None:
            self.app.display_info(message)
        else:  # bare `python -m build` without a hatchling app context
            print(message, flush=True)

    def initialize(self, version: str, build_data: dict) -> None:
        if self.target_name != "wheel" or version == "editable":
            # Editable builds are `uv sync`/dev installs — they must not require node.
            return
        root = Path(self.root)

        if os.environ.get(_SKIP, "").strip().lower() in _TRUTHY:
            self._info(
                f"[fyndnote] {_SKIP} set - building API-only wheel (no web assets)"
            )
            return

        build_assets = _load_build_assets(root)
        if build_assets.web_ready(root):
            self._info("[fyndnote] web assets already staged - skipping npm build")
            return

        self._info("[fyndnote] building web assets (vite SPA + vitepress docs)")
        try:
            build_assets.build_web(root)
        except build_assets.AssetBuildError as exc:
            raise RuntimeError(
                f"{exc}\n\nOptions:\n"
                f"  1. install node/npm and retry\n"
                f"  2. set {_SKIP}=1 for an API-only wheel\n"
                f"  3. build the assets first with `npm run build:wheel`"
            ) from exc
