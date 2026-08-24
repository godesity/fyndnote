"""Generate the OpenAPI/Swagger JSON for the fyndnot docs site.

Run from the backend directory:
    uv run python tools/gen_openapi.py

Writes the FastAPI app's OpenAPI schema to docs/public/openapi.json,
which is committed and rendered by the Scalar reference viewer in the docs site.
Regenerate this file whenever the API surface changes.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402 - imports the FastAPI app

spec = main.app.openapi()

out = Path(__file__).resolve().parents[2] / "docs" / "public" / "openapi.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(spec, indent=2))

print(f"Wrote {out}")
