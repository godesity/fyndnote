import logging
import threading
import time

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from starlette.concurrency import run_in_threadpool

from ..config import (
    MAX_CONCURRENT_UPLOADS,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_WAIT_SECONDS,
    UPLOAD_READ_BYTES,
)
from ..services.dataset_service import (
    DATASET_SOURCE_TYPES,
    DatasetNameConflict,
    DatasetService,
    UploadTooLargeError,
    _safe_filename,
)
from ..services.permission_service import PermissionService
from ..upload_guard import too_large_detail

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Datasets"])

# One in-flight upload costs a spooled copy on disk plus a full pyarrow
# conversion in RAM (measured: a 1.1 GB CSV peaked the worker at ~1.4 GB RSS).
# Uncapped, N simultaneous uploads scale RAM and disk with N and the OOM killer
# wins. ``threading`` keeps the counter correct regardless of which loop a
# request runs on; acquisition is a non-blocking poll, so a queued upload parks
# neither the event loop nor an anyio threadpool worker.
_slots = threading.Semaphore(MAX_CONCURRENT_UPLOADS)


async def _acquire_upload_slot() -> None:
    """Wait for a heavy-upload slot without blocking the loop or a thread."""
    deadline = time.monotonic() + MAX_UPLOAD_WAIT_SECONDS
    while not _slots.acquire(blocking=False):
        if time.monotonic() >= deadline:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Too many concurrent uploads (limit {MAX_CONCURRENT_UPLOADS}); "
                    "retry later"
                ),
            )
        await run_in_threadpool(time.sleep, 0.25)


def _require_user(user_id: str = Query(..., min_length=1)) -> str:
    """Gate dataset-ingest endpoints on a known account.

    Datasets are the most expensive resource in the app — one upload can cost
    gigabytes of disk and RAM — so these endpoints must not be anonymously
    callable. ``user_id`` is a query parameter because a multipart body cannot
    carry it alongside the file.
    """
    if PermissionService.get_user(user_id) is None:
        raise HTTPException(status_code=401, detail="unknown_user")
    return user_id


def _too_large() -> HTTPException:
    return HTTPException(status_code=413, detail=too_large_detail())


def _conflict_payload(e: DatasetNameConflict) -> dict:
    return {
        "detail": f"a dataset named '{e.name}' already exists",
        "suggested_name": e.suggested,
    }


@router.get("/datasets/config")
def dataset_config():
    """Limits the SPA needs to pre-flight an upload before sending gigabytes."""
    return {
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "max_concurrent_uploads": MAX_CONCURRENT_UPLOADS,
        "formats": sorted(DATASET_SOURCE_TYPES),
    }


@router.get("/datasets")
def list_datasets():
    return {"datasets": DatasetService.list_datasets()}


@router.get("/datasets/name-available")
def check_dataset_name(name: str | None = None, source: str | None = None):
    """Pre-flight for the load/upload forms: is this display label free?

    ``source`` is what the UI has typed so far, so the check works before the
    user picked a name: the derived default is checked instead.
    """
    base = (name or "").strip()
    if not base:
        if not (source or "").strip():
            raise HTTPException(status_code=400, detail="name or source is required")
        source = source.strip()
        base = DatasetService.default_name(source)
    suggested = DatasetService.unique_name(base)
    return {"name": base, "available": suggested == base, "suggested_name": suggested}


@router.get("/datasets/{ds_id}/details")
def dataset_details(ds_id: str):
    details = DatasetService.dataset_details(ds_id)
    if details is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return details


@router.post("/datasets/load")
def load_dataset(body: dict, user_id: str = Depends(_require_user)):
    source = body["source"]
    split = body.get("split", "train")
    name = body.get("name")
    try:
        return DatasetService.load(source, split, name, alias=body.get("alias"))
    except DatasetNameConflict as e:
        raise HTTPException(status_code=409, detail=_conflict_payload(e)) from e


@router.post("/datasets/upload", status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    user_id: str = Depends(_require_user),
    alias: str | None = Form(None),
):
    """Stream an uploaded dataset to disk instead of buffering it in RAM.

    Starlette already spools multipart parts to disk past ~1 MB, so the payload
    never has to become a single ``bytes`` object; the previous
    ``content = await file.read()`` materialised the whole file (a 1.1 GB CSV
    peaked the worker at ~1.4 GB RSS and pinned it for the whole transfer).
    An oversized ``Content-Length`` is refused by :class:`UploadSizeGuard`
    before the body is read at all; the size of the spooled part is then
    enforced while copying, so oversized files never reach pyarrow.

    The display name defaults to the original filename; ``alias`` overrides it.
    """
    await _acquire_upload_slot()
    dest = None
    try:
        # Both heavy steps run in a threadpool worker, never on the event loop:
        # the chunked copy, then the pyarrow conversion.
        dest = await run_in_threadpool(
            DatasetService.save_upload, file.filename, file.file, UPLOAD_READ_BYTES
        )
        # Starlette maintains ``UploadFile.size``, so this bound is exact even
        # for a chunked request that arrived without a Content-Length.
        if file.size is not None and file.size > MAX_UPLOAD_BYTES:
            raise _too_large()
        display = (alias or "").strip() or _safe_filename(file.filename or "")
        return await run_in_threadpool(
            DatasetService.load, f"file://{dest}", alias=display
        )
    except DatasetNameConflict as e:
        # ``load`` only tears down its cache dir on conflict; the retained
        # upload copy has to go with it or a rejected upload would reserve
        # nothing yet still leak a file on disk.
        if dest is not None:
            dest.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail=_conflict_payload(e)) from e
    except UploadTooLargeError:
        if dest is not None:
            dest.unlink(missing_ok=True)
        raise _too_large()
    except HTTPException:
        if dest is not None:
            dest.unlink(missing_ok=True)
        raise
    except (ValueError, FileNotFoundError) as e:
        # ``load`` removes its own cache dir; the retained upload copy has to go
        # with it or every rejected file leaks a permanent copy on disk.
        if dest is not None:
            dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        _slots.release()


@router.delete("/datasets/{ds_id}")
def delete_dataset(ds_id: str, user_id: str = Depends(_require_user)):
    """Drop a dataset and every byte it owns on disk.

    Nothing else in the app ever deletes a dataset, so a rejected or abandoned
    import keeps its cache directory and upload copy forever.
    """
    if not PermissionService.is_system_admin(user_id):
        raise HTTPException(status_code=403, detail="insufficient role")
    try:
        deleted = DatasetService.delete_dataset(ds_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="dataset not found")
    return {"status": "deleted"}


@router.get("/datasets/{ds_id}/rows/{index}")
def get_row(ds_id: str, index: int):
    try:
        row = DatasetService.get_row(ds_id, index)
        return {"index": index, "row": row}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/datasets/{ds_id}/rows/{index}/columns/{column}")
def get_binary_column(ds_id: str, index: int, column: str):
    try:
        data, content_type = DatasetService.get_binary_column(ds_id, index, column)
        return Response(content=data, media_type=content_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
