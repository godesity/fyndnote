"""Header-only rejection of oversized dataset uploads.

Lives in its own module (rather than ``routers/datasets.py``) so that ``main.py``
can install it without importing the routers, and because it has to be a *pure
ASGI* app — a middleware built on ``BaseHTTPMiddleware`` would already have the
request body streamed at it before we get to look.
"""

import json
import logging
from pathlib import Path

from .config import MAX_CONCURRENT_UPLOADS, MAX_UPLOAD_BYTES

logger = logging.getLogger(__name__)

UPLOAD_PATH_SUFFIX = "/datasets/upload"


def too_large_detail() -> str:
    return f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit"


def header(scope: dict, name: bytes) -> str | None:
    for key, value in scope.get("headers") or ():
        if key.lower() == name:
            return value.decode("latin-1")
    return None


class UploadSizeGuard:
    """Refuse an oversized ``POST /datasets/upload`` before its body arrives.

    This cannot be expressed inside the endpoint. ``file: UploadFile =
    File(...)`` makes FastAPI parse the *whole* multipart body before the handler
    is entered (``fastapi/routing.py`` calls ``await request.form()`` in its
    route wrapper), so code written inside the function only runs after every
    byte has been transferred and spooled to disk. It is also unreachable for a
    client that lies about ``Content-Length``: uvicorn keeps waiting for the
    promised bytes, the handler is never entered, and the request hangs until a
    timeout kills it — with a gigabyte-scale claim, effectively forever.

    ``Content-Length`` is the only signal available before the body, so the guard
    reads it straight from the ASGI scope and answers 413 without consuming a
    single chunk. The authoritative check for uploads that arrive without
    ``Content-Length`` stays in ``DatasetService.save_upload``, which enforces the
    cap while streaming to disk.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and scope["path"].rstrip("/").endswith(UPLOAD_PATH_SUFFIX)
        ):
            declared = header(scope, b"content-length")
            oversize = False
            if declared is not None:
                try:
                    oversize = int(declared) > MAX_UPLOAD_BYTES
                except ValueError:
                    oversize = False  # unparseable: the streamed check decides
            if oversize:
                logger.warning(
                    "rejected upload claiming %s bytes (cap %s)",
                    declared,
                    MAX_UPLOAD_BYTES,
                )
                body = json.dumps({"detail": too_large_detail()}).encode()
                await send(
                    {
                        "type": "http.response.start",
                        "status": 413,
                        "headers": [
                            (b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode()),
                            # The body is deliberately never read, so the
                            # connection cannot be reused — the same thing nginx
                            # does for an oversized POST. Without it uvicorn would
                            # keep waiting for the promised bytes on keep-alive.
                            (b"connection", b"close"),
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


# Baseline worker RSS before any upload (FastAPI + datasets + PIL, measured
# ~175 MB) plus headroom for the LRU-cached dataset objects.
_BASELINE_BYTES = 400 * 1024 * 1024
# Measured anonymous-memory cost of a pyarrow conversion: a 1.05 GB CSV took the
# worker from 175 MB to 454 MB, i.e. ~0.27x the file size. The arrow cache is
# mmap'd, so its pages are reclaimable page cache rather than anonymous memory
# and get evicted under pressure instead of triggering the OOM killer. 0.5x
# leaves margin for wider/taller schemas and for json, which is read twice.
_CONVERSION_FACTOR = 0.5


def required_memory_bytes() -> int:
    return int(
        _BASELINE_BYTES + MAX_CONCURRENT_UPLOADS * MAX_UPLOAD_BYTES * _CONVERSION_FACTOR
    )


def container_memory_limit(
    paths: tuple[str, ...] = (
        "/sys/fs/cgroup/memory.max",  # cgroup v2
        "/sys/fs/cgroup/memory/memory.limit_in_bytes",  # cgroup v1
    ),
) -> int | None:
    """Memory ceiling of the current cgroup, or None if unlimited/unavailable."""
    for path in paths:
        try:
            raw = Path(path).read_text().strip()
        except OSError:
            continue
        if raw in ("", "max"):
            continue
        try:
            limit = int(raw)
        except ValueError:
            continue
        # v1 reports "no limit" as a huge sentinel rather than "max".
        if limit >= 2**62:
            continue
        return limit
    return None


def check_memory_budget() -> None:
    """Warn at startup if the upload budget cannot fit inside the memory limit.

    Called from the app's startup hook. Warns only, never clamps: silently
    lowering an operator's configured cap hides the misconfiguration, whereas a
    refusal to start would be hostile to a dev box that has no cgroup limit at
    all. Being OOM-killed mid-upload is the consequence this is meant to predict.
    """
    limit = container_memory_limit()
    if limit is None:
        return
    needed = required_memory_bytes()
    if needed <= limit:
        logger.info(
            "upload budget ok: %s concurrent x %s MB needs ~%s MB, limit is %s MB",
            MAX_CONCURRENT_UPLOADS,
            MAX_UPLOAD_BYTES // (1024 * 1024),
            needed // (1024 * 1024),
            limit // (1024 * 1024),
        )
        return
    safe = max(
        1,
        int((limit - _BASELINE_BYTES) / (_CONVERSION_FACTOR * MAX_UPLOAD_BYTES)),
    )
    logger.warning(
        "memory limit (%s MB) is below the ~%s MB needed for %s concurrent "
        "uploads of %s MB each — the OOM killer will reap this container during "
        "a large import. Set MAX_CONCURRENT_UPLOADS<=%s, lower MAX_UPLOAD_BYTES, "
        "or raise the container memory limit.",
        limit // (1024 * 1024),
        needed // (1024 * 1024),
        MAX_CONCURRENT_UPLOADS,
        MAX_UPLOAD_BYTES // (1024 * 1024),
        safe,
    )
