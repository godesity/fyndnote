"""Generate the OpenAPI/Swagger JSON for the fyndnote docs site.

Run from the repo root:
    uv run python -m fyndnote.tools.gen_openapi

Writes the FastAPI app's OpenAPI schema to docs/public/openapi.json,
which is committed and rendered by the Scalar reference viewer in the docs site.
Regenerate this file whenever the API surface changes.
"""

import json
from pathlib import Path

from fyndnote.main import app

spec = app.openapi()

out = Path(__file__).resolve().parents[2] / "docs" / "public" / "openapi.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(spec, indent=2))

print(f"Wrote {out}")
