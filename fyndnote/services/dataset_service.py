import glob
import json
import logging
import os
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import requests
from datasets import Audio, Dataset, load_dataset
from datasets import Image as HfImage
from PIL import Image as PILImage
from sqlalchemy.exc import IntegrityError

from ..config import (
    DATASETS_DIR,
    DATASETS_UPLOAD_DIR,
    DISK_USAGE_THRESHOLD,
    MAX_CACHED_DATASETS,
    MAX_UPLOAD_BYTES,
    S3_CACHE_BUCKET,
    S3_CACHE_ENABLED,
    S3_CACHE_PREFIX,
    S3_ENDPOINT_URL,
)
from ..database import derive_display_name, get_db, name_variant
from .s3_cache import S3BackedCache

logger = logging.getLogger(__name__)

DATASET_SOURCE_TYPES = {
    "csv": "csv",
    "json": "json",
    "jsonl": "json",
    "parquet": "parquet",
}

EXT_BY_FORMAT = {v: k for k, v in DATASET_SOURCE_TYPES.items()}


def _safe_filename(filename: str) -> str:
    """The basename of an uploaded file, usable as a display name.

    Browsers disagree about what ``UploadFile.filename`` holds: Chrome sends a
    basename, IE/older Safari send a full path (``C:\\\\fakepath\\\\x.csv``). It
    is never touched by the filesystem — the original is stored under a uuid —
    so this is about not showing the user someone's directory tree.
    """
    tail = filename.replace("\\", "/").rsplit("/", 1)[-1]
    return "".join(c for c in tail if c.isprintable() and c not in '<>:"|?*').strip()


class DatasetNameConflict(Exception):
    """A dataset already owns the display name a load was asked to use."""

    def __init__(self, name: str, suggested: str) -> None:
        self.name = name
        self.suggested = suggested
        super().__init__(f"A dataset named {name!r} already exists")


def _is_unique_violation(exc: Exception) -> bool:
    """True for the display-name unique index firing on commit."""
    return isinstance(exc, IntegrityError) and "name" in str(exc)


class UploadTooLargeError(ValueError):
    """Raised when a stream exceeds the configured upload budget."""


def _extract_extension(path: str) -> str:
    return Path(path.split("?")[0]).suffix.lower().lstrip(".")


def _detect_source(source: str) -> tuple[str, str, str]:
    """Returns (source_type, format, clean_source)."""
    if source.startswith(("http://", "https://")):
        ext = _extract_extension(source)
        if ext not in DATASET_SOURCE_TYPES:
            raise ValueError(
                f"Unsupported format: .{ext}. Supported: .csv, .json, .jsonl, .parquet"
            )
        return ("http", DATASET_SOURCE_TYPES[ext], source)
    elif source.startswith("file://"):
        path = source[7:]
        if Path(path).is_dir():
            for ext, fmt in DATASET_SOURCE_TYPES.items():
                if any(p.suffix == f".{ext}" for p in Path(path).iterdir()):
                    return ("file", fmt, path)
            raise ValueError(f"No supported data files in directory: {path}")
        ext = _extract_extension(path)
        if ext not in DATASET_SOURCE_TYPES:
            raise ValueError(
                f"Unsupported format: .{ext}. Supported: .csv, .json, .jsonl, .parquet"
            )
        return ("file", DATASET_SOURCE_TYPES[ext], path)
    else:
        return ("huggingface", None, source)


def _load_from_format(path, fmt: str, cache_dir: str | None = None) -> Dataset:
    load_kwargs = {"data_files": path, "split": "train"}
    if cache_dir is not None:
        load_kwargs["cache_dir"] = cache_dir
    if fmt == "csv":
        return load_dataset("csv", **load_kwargs)
    elif fmt == "json" or fmt == "jsonl":
        return load_dataset("json", **load_kwargs)
    elif fmt == "parquet":
        return load_dataset("parquet", **load_kwargs)
    else:
        raise ValueError(f"Unsupported format: {fmt}")


def _load_file(path: str, fmt: str, cache_dir: str | None = None) -> Dataset:
    p = Path(path)
    if p.is_dir():
        ext = EXT_BY_FORMAT[fmt]
        pattern = str(p / f"*.{ext}")
        if not glob.glob(pattern):
            raise FileNotFoundError(f"No .{ext} files in directory: {path}")
        return _load_from_format(pattern, fmt, cache_dir)
    if any(c in path for c in "*?["):
        if not glob.glob(path):
            raise FileNotFoundError(f"No files match pattern: {path}")
        return _load_from_format(path, fmt, cache_dir)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return _load_from_format(path, fmt, cache_dir)


def _load_http(url: str, fmt: str, cache_dir: str | None = None) -> Dataset:
    # timeout is (connect, read); the read timeout is per chunk, so a slow but
    # steady gigabyte download survives while a stalled one still fails.
    resp = requests.get(url, stream=True, timeout=(10, 120))
    resp.raise_for_status()
    suffix = f".{fmt}"
    downloaded = 0
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            downloaded += len(chunk)
            # Remote servers are not trusted to be honest about Content-Length,
            # and the pyarrow conversion that follows costs RAM per byte.
            if downloaded > MAX_UPLOAD_BYTES:
                raise UploadTooLargeError(
                    f"Download exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB "
                    "upload limit"
                )
            tmp.write(chunk)
    try:
        ds = _load_from_format(tmp_path, fmt, cache_dir)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return ds


def _cache_dir_for(ds_id: str) -> Path:
    return DATASETS_DIR / ds_id / "hf_cache"


def _is_under(path: Path, root: Path) -> bool:
    """True when *path* lives inside *root*, without relying on symlink tricks."""
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


class DatasetService:
    _instances: dict[str, Dataset] = {}
    _access_times: dict[str, float] = {}
    _s3_cache: S3BackedCache | None = None
    # Strong refs to in-flight mirror futures; the executor only holds weak ones.
    _pending_s3: set = set()

    @classmethod
    def _s3(cls) -> S3BackedCache | None:
        if cls._s3_cache is None and S3_CACHE_ENABLED:
            if S3_CACHE_BUCKET:
                cls._s3_cache = S3BackedCache(
                    bucket=S3_CACHE_BUCKET,
                    prefix=S3_CACHE_PREFIX,
                    endpoint_url=S3_ENDPOINT_URL,
                )
            else:
                logger.warning(
                    "S3_CACHE_ENABLED is True but S3_CACHE_BUCKET is not set"
                )
        return cls._s3_cache if S3_CACHE_ENABLED else None

    @classmethod
    def _evict_lru(cls, active_id: str | None = None) -> None:
        """Evict datasets from _instances when above MAX_CACHED_DATASETS."""
        if len(cls._instances) <= MAX_CACHED_DATASETS:
            return
        candidates = [
            (ds_id, cls._access_times.get(ds_id, 0))
            for ds_id in cls._instances
            if ds_id != active_id
        ]
        if not candidates:
            return
        candidates.sort(key=lambda x: x[1])
        for ds_id, _ in candidates[: len(cls._instances) - MAX_CACHED_DATASETS]:
            cls._instances.pop(ds_id, None)
            cls._access_times.pop(ds_id, None)

    @classmethod
    def _evict_disk_pressure(cls) -> None:
        """When disk is over threshold, delete local cache of cold S3-backed datasets."""
        s3 = cls._s3()
        if s3 is None:
            return
        try:
            usage = shutil.disk_usage(DATASETS_DIR)
            ratio = usage.used / usage.total
        except OSError:
            return
        if ratio <= DISK_USAGE_THRESHOLD:
            return
        logger.info(
            "Disk usage %.1f%% exceeds threshold %.1f%%",
            ratio * 100,
            DISK_USAGE_THRESHOLD * 100,
        )
        db = get_db()
        rows = db.execute(
            "SELECT id FROM fyndnote_datasets WHERE s3_uploaded = 1 ORDER BY created_at ASC"
        ).fetchall()
        db.close()
        for (ds_id,) in rows:
            if ds_id in cls._instances:
                continue
            cache_dir = _cache_dir_for(ds_id)
            if cache_dir.is_dir():
                shutil.rmtree(cache_dir)
                logger.info("Evicted local cache for %s (disk pressure)", ds_id)

    @classmethod
    def _mirror_to_s3(cls, ds_id: str, cache_dir: Path) -> None:
        """Mirror a dataset's arrow cache to S3 without blocking the caller.

        ``s3_uploaded`` is only set once the mirror has actually been verified, so
        a crash or failure mid-transfer leaves the dataset marked local-only and
        ``requeue_unuploaded()`` picks it up on the next boot. Futures are kept in
        ``_pending_s3`` so the results are collectable and the executor does not
        silently drop them.
        """
        s3 = cls._s3()
        if s3 is None:
            return
        future = s3.upload_async(ds_id, cache_dir)
        cls._pending_s3.add(future)

        def _done(fut) -> None:
            cls._pending_s3.discard(fut)
            try:
                fut.result()
            except Exception as e:
                # Stay local-only: the cache dir on disk is still the source of
                # truth, so the dataset keeps working, it just cannot be evicted.
                logger.warning("S3 mirror failed for %s: %s", ds_id, e)
                return
            db = get_db()
            try:
                db.execute(
                    "UPDATE fyndnote_datasets SET s3_uploaded = 1 WHERE id = ?",
                    (ds_id,),
                )
                db.commit()
            finally:
                db.close()
            logger.info("Mirrored dataset %s to S3", ds_id)

        future.add_done_callback(_done)

    @classmethod
    def requeue_unuploaded(cls) -> int:
        """Re-dispatch mirrors for datasets that never finished uploading."""
        s3 = cls._s3()
        if s3 is None:
            return 0
        db = get_db()
        try:
            rows = db.execute(
                "SELECT id FROM fyndnote_datasets WHERE s3_uploaded = 0"
            ).fetchall()
        finally:
            db.close()
        requeued = 0
        for (ds_id,) in rows:
            cache_dir = _cache_dir_for(ds_id)
            if not cache_dir.is_dir():
                continue
            cls._mirror_to_s3(ds_id, cache_dir)
            requeued += 1
        if requeued:
            logger.info("Re-queued %d dataset(s) for S3 mirroring", requeued)
        return requeued

    @classmethod
    def reap_orphans(cls, max_age_minutes: int = 30) -> int:
        """Delete upload copies no database row references.

        An upload is the canonical source for a ``file://`` dataset, so only files
        older than ``max_age_minutes`` are touched — that grace period keeps an
        in-flight upload (written but not yet inserted) from being swept away.
        Returns the number of files removed.
        """
        if not DATASETS_UPLOAD_DIR.is_dir():
            return 0
        db = get_db()
        try:
            referenced = {
                Path(row["source"].removeprefix("file://")).resolve()
                for row in db.execute(
                    "SELECT source FROM fyndnote_datasets WHERE source LIKE 'file://%'"
                ).fetchall()
            }
        finally:
            db.close()
        cutoff = time.time() - max_age_minutes * 60
        removed = 0
        for candidate in DATASETS_UPLOAD_DIR.iterdir():
            if not candidate.is_file():
                continue
            # A dangling ``.part`` is a write that never completed.
            if candidate.name.endswith(".part"):
                if candidate.stat().st_mtime < cutoff:
                    candidate.unlink(missing_ok=True)
                    removed += 1
                continue
            if candidate.suffix.lstrip(".") not in DATASET_SOURCE_TYPES:
                continue
            if candidate.resolve() in referenced:
                continue
            if candidate.stat().st_mtime < cutoff:
                candidate.unlink(missing_ok=True)
                removed += 1
        if removed:
            logger.info("Reaped %d orphan upload file(s)", removed)
        return removed

    @classmethod
    def default_name(cls, source: str) -> str:
        """The label ``load`` would give ``source`` if no alias is supplied."""
        return derive_display_name(source, _detect_source(source)[0])

    @classmethod
    def _require_free_name(cls, name: str) -> None:
        """Raise ``DatasetNameConflict`` if ``name`` is already taken."""
        db = get_db()
        try:
            taken = db.execute(
                "SELECT 1 FROM fyndnote_datasets WHERE name = ?", (name,)
            ).fetchone()
        finally:
            db.close()
        if taken is not None:
            raise DatasetNameConflict(name, cls.unique_name(name))

    @classmethod
    def unique_name(cls, base: str) -> str:
        """First free display name at or after ``base`` (``base (2)``, ``(3)``…)."""
        db = get_db()
        try:
            taken = {
                r["name"]
                for r in db.execute(
                    "SELECT name FROM fyndnote_datasets WHERE name LIKE ?",
                    (f"{base}%",),
                ).fetchall()
            }
        finally:
            db.close()
        n = 1
        while name_variant(base, n) in taken:
            n += 1
        return name_variant(base, n)

    @classmethod
    def load(
        cls,
        source: str,
        split: str = "train",
        name: str | None = None,
        alias: str | None = None,
    ) -> dict:
        source_type, source_format, clean_source = _detect_source(source)
        display = (alias or "").strip() or derive_display_name(source, source_type)
        ds_id = str(uuid.uuid4())
        cache_dir = _cache_dir_for(ds_id)
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Checked before the (possibly minutes-long) conversion, so a duplicate
        # label fails immediately instead of after the dataset is on disk.
        cls._require_free_name(display)

        try:
            if source_type == "huggingface":
                ds = load_dataset(
                    clean_source, name, split=split, cache_dir=str(cache_dir)
                )
            elif source_type == "http":
                ds = _load_http(clean_source, source_format, cache_dir=str(cache_dir))
                split = None
                name = None
            elif source_type == "file":
                ds = _load_file(clean_source, source_format, cache_dir=str(cache_dir))
                split = None
                name = None
            else:
                raise ValueError(f"Unknown source type: {source_type}")
        except BaseException:
            # A failed conversion leaves a half-written arrow cache behind that no
            # row points at: nothing could ever list or evict it, so it would be a
            # permanent multi-gigabyte leak.
            shutil.rmtree(DATASETS_DIR / ds_id, ignore_errors=True)
            cls._instances.pop(ds_id, None)
            cls._access_times.pop(ds_id, None)
            raise

        cls._instances[ds_id] = ds
        cls._access_times[ds_id] = time.monotonic()

        meta = {
            "id": ds_id,
            "name": display,
            "source": source,
            "source_type": source_type,
            "source_format": source_format,
            "hf_name": name,
            "split": split,
            "num_rows": len(ds),
            "columns": [
                {"name": col, "type": str(ds.features[col])} for col in ds.column_names
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # The row is written with s3_uploaded = 0 and the mirror runs in the
        # background: a gigabyte-scale transfer must not dominate the request that
        # is waiting on it.
        db = get_db()
        try:
            db.execute(
                """INSERT INTO fyndnote_datasets (id, name, source, source_type, source_format, hf_name, hf_split, num_rows, columns, created_at, s3_uploaded)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ds_id,
                    display,
                    source,
                    source_type,
                    source_format,
                    name,
                    split,
                    meta["num_rows"],
                    json.dumps(meta["columns"]),
                    meta["created_at"],
                    0,
                ),
            )
            db.commit()
        except Exception as e:
            # Two concurrent loads can both pass the pre-check; the unique
            # index is what actually decides.
            if _is_unique_violation(e):
                shutil.rmtree(DATASETS_DIR / ds_id, ignore_errors=True)
                cls._instances.pop(ds_id, None)
                cls._access_times.pop(ds_id, None)
                raise DatasetNameConflict(display, cls.unique_name(display)) from e
            raise
        finally:
            db.close()

        cls._mirror_to_s3(ds_id, cache_dir)
        cls._evict_lru(ds_id)
        cls._evict_disk_pressure()
        meta["s3_uploaded"] = False
        return meta

    @classmethod
    def list_datasets(cls) -> list[dict]:
        db = get_db()
        rows = db.execute(
            "SELECT * FROM fyndnote_datasets ORDER BY created_at DESC"
        ).fetchall()
        db.close()
        result = []
        for row in rows:
            meta = {
                "id": row["id"],
                "name": row["name"],
                "source": row["source"],
                "source_type": row["source_type"],
                "source_format": row["source_format"],
                "hf_name": row["hf_name"],
                "split": row["hf_split"],
                "num_rows": row["num_rows"],
                "columns": json.loads(row["columns"]),
                "created_at": row["created_at"],
                "s3_uploaded": bool(row["s3_uploaded"]),
            }
            cache_dir = _cache_dir_for(row["id"])
            meta["cache_available"] = cache_dir.is_dir()
            result.append(meta)
        return result

    @classmethod
    def dataset_details(cls, ds_id: str) -> dict | None:
        db = get_db()
        row = db.execute(
            "SELECT * FROM fyndnote_datasets WHERE id = ?", (ds_id,)
        ).fetchone()
        if not row:
            db.close()
            return None
        projects = db.execute(
            "SELECT id, name, color FROM fyndnote_projects WHERE dataset_id = ? ORDER BY created_at",
            (ds_id,),
        ).fetchall()
        result_projects = []
        total_annotations = 0
        total_predictions = 0
        for p in projects:
            annotated_rows = db.execute(
                "SELECT COUNT(DISTINCT row_index) FROM fyndnote_annotations WHERE project_id = ?",
                (p["id"],),
            ).fetchone()[0]
            annotations = db.execute(
                "SELECT COUNT(*) FROM fyndnote_annotations WHERE project_id = ?",
                (p["id"],),
            ).fetchone()[0]
            predictions = db.execute(
                "SELECT COUNT(*) FROM fyndnote_ml_annotations WHERE project_id = ?",
                (p["id"],),
            ).fetchone()[0]
            total_annotations += annotations
            total_predictions += predictions
            result_projects.append(
                {
                    "id": p["id"],
                    "name": p["name"],
                    "color": p["color"],
                    "annotated_rows": annotated_rows,
                    "annotations": annotations,
                    "predictions": predictions,
                }
            )
        db.close()
        return {
            "dataset": {
                "id": row["id"],
                "name": row["name"],
                "source": row["source"],
                "source_type": row["source_type"],
                "source_format": row["source_format"],
                "hf_name": row["hf_name"],
                "split": row["hf_split"],
                "num_rows": row["num_rows"],
                "created_at": row["created_at"],
            },
            "projects": result_projects,
            "totals": {
                "annotations": total_annotations,
                "predictions": total_predictions,
            },
        }

    @classmethod
    def _load_ds(cls, ds_id: str) -> Dataset:
        ds = cls._instances.get(ds_id)
        if ds is not None:
            cls._access_times[ds_id] = time.monotonic()
            return ds

        # Read metadata from database
        db = get_db()
        row = db.execute(
            "SELECT * FROM fyndnote_datasets WHERE id = ?", (ds_id,)
        ).fetchone()
        db.close()
        if not row:
            raise ValueError("Dataset not found")

        cache_dir = _cache_dir_for(ds_id)

        # If S3-backed, download cache from S3 (never from external source)
        if row["s3_uploaded"]:
            s3 = cls._s3()
            if s3 is None:
                raise ValueError("S3 cache not available but dataset is S3-backed")
            if not cache_dir.is_dir():
                cache_dir.mkdir(parents=True, exist_ok=True)
                if not s3.download(ds_id, cache_dir):
                    shutil.rmtree(cache_dir, ignore_errors=True)
                    raise ValueError("Dataset cache not available on S3")
        else:
            # Local-only dataset — cache must exist
            if not cache_dir.is_dir():
                raise ValueError("Dataset cache not available locally")

        source_type = row["source_type"]
        source = row["source"]
        try:
            if source_type == "huggingface":
                ds = load_dataset(
                    source,
                    row["hf_name"],
                    split=row["hf_split"],
                    cache_dir=str(cache_dir),
                )
            elif source_type == "http":
                fmt = row["source_format"] or "csv"
                ds = _load_http(source, fmt, cache_dir=str(cache_dir))
            elif source_type == "file":
                clean = source.removeprefix("file://")
                fmt = row["source_format"] or "csv"
                ds = _load_file(clean, fmt, cache_dir=str(cache_dir))
            else:
                raise ValueError(f"Unknown source type: {source_type}")
        except Exception:
            shutil.rmtree(DATASETS_DIR / ds_id, ignore_errors=True)
            raise ValueError(f"Failed to load dataset: {ds_id}")

        cls._instances[ds_id] = ds
        cls._access_times[ds_id] = time.monotonic()
        cls._evict_lru(ds_id)
        cls._evict_disk_pressure()
        return ds

    @classmethod
    def get_row(cls, ds_id: str, index: int) -> dict:
        ds = cls._load_ds(ds_id)
        row = ds[index]
        serialized = {}
        for col, val in row.items():
            if isinstance(val, (PILImage.Image, Audio)):
                serialized[col] = f"/api/v1/datasets/{ds_id}/rows/{index}/columns/{col}"
            elif isinstance(val, dict):
                serialized[col] = val
            elif isinstance(val, list):
                serialized[col] = [cls._json_safe(v) for v in val]
            else:
                serialized[col] = cls._json_safe(val)
        return serialized

    @staticmethod
    def _json_safe(val):
        if isinstance(val, (str, int, float, bool, type(None))):
            return val
        if isinstance(val, dict):
            return {k: DatasetService._json_safe(v) for k, v in val.items()}
        if isinstance(val, list):
            return [DatasetService._json_safe(v) for v in val]
        try:
            json.dumps(val)
            return val
        except (TypeError, ValueError):
            return str(val)

    @classmethod
    def get_binary_column(
        cls, ds_id: str, index: int, column: str
    ) -> tuple[bytes, str]:
        ds = cls._load_ds(ds_id)
        val = ds[index][column]
        if isinstance(val, (PILImage.Image, HfImage)):
            buf = BytesIO()
            val.save(buf, format="JPEG")
            buf.seek(0)
            return buf.read(), "image/jpeg"
        if isinstance(val, Audio):
            raw = val["array"].tobytes()
            return raw, "audio/wav"
        return str(val).encode(), "application/octet-stream"

    @classmethod
    def save_upload(cls, filename: str, src, read_bytes: int) -> Path:
        """Copy an upload stream into the managed uploads dir and return its path.

        The caller hands over the raw multipart stream (a spooled file), never a
        ``bytes`` blob: the whole payload is copied in ``read_bytes`` chunks so
        peak RSS stays at one buffer regardless of upload size. The size cap is
        enforced while streaming, so an oversized file is refused before the
        pyarrow conversion ever runs.
        """
        ext = _extract_extension(filename or "")
        if ext not in DATASET_SOURCE_TYPES:
            raise ValueError(
                f"Unsupported format: .{ext}. Supported: .csv, .json, .jsonl, .parquet"
            )
        DATASETS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        dest = DATASETS_UPLOAD_DIR / f"{uuid.uuid4()}.{ext}"
        # ``.part`` first: a half-written file must never look like a committed
        # upload, since the orphan reaper keys off this directory's contents.
        tmp = dest.with_name(dest.name + ".part")
        written = 0
        try:
            with tmp.open("wb") as out:
                while True:
                    chunk = src.read(read_bytes)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > MAX_UPLOAD_BYTES:
                        raise UploadTooLargeError(
                            f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB "
                            "upload limit"
                        )
                    out.write(chunk)
            os.replace(tmp, dest)
        except BaseException:
            tmp.unlink(missing_ok=True)
            dest.unlink(missing_ok=True)
            raise
        return dest

    @classmethod
    def delete_dataset(cls, ds_id: str) -> bool:
        """Remove a dataset's row, its arrow cache, and its upload copy.

        Refuses datasets still referenced by a project: the row is the only thing
        that lets a project re-open its cache after an LRU eviction.
        """
        db = get_db()
        try:
            row = db.execute(
                "SELECT source FROM fyndnote_datasets WHERE id = ?", (ds_id,)
            ).fetchone()
            if row is None:
                return False
            used = db.execute(
                "SELECT 1 FROM fyndnote_projects WHERE dataset_id = ? LIMIT 1", (ds_id,)
            ).fetchone()
            if used is not None:
                raise ValueError("dataset is in use by a project")
            source = row["source"]
            db.execute("DELETE FROM fyndnote_datasets WHERE id = ?", (ds_id,))
            db.commit()
        finally:
            db.close()

        shutil.rmtree(DATASETS_DIR / ds_id, ignore_errors=True)
        cls._instances.pop(ds_id, None)
        cls._access_times.pop(ds_id, None)
        if source.startswith("file://"):
            # Only ever remove our own managed copy, never a user-provided path.
            candidate = Path(source.removeprefix("file://"))
            if candidate.is_file() and _is_under(candidate, DATASETS_UPLOAD_DIR):
                candidate.unlink(missing_ok=True)
        s3 = cls._s3()
        if s3 is not None:
            try:
                s3.delete_prefix(ds_id)
            except Exception as e:  # pragma: no cover - depends on S3 availability
                logger.warning("Failed to purge S3 objects for %s: %s", ds_id, e)
        logger.info("Deleted dataset %s", ds_id)
        return True
