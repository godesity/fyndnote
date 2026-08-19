import glob
import json
import logging
import shutil
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import BytesIO
from pathlib import Path

import requests
from datasets import Audio, Dataset, Image as HfImage, load_dataset
from PIL import Image as PILImage

from config import (
    DATASETS_DIR,
    DATASETS_UPLOAD_DIR,
    DISK_USAGE_THRESHOLD,
    MAX_CACHED_DATASETS,
    S3_CACHE_BUCKET,
    S3_CACHE_ENABLED,
    S3_CACHE_PREFIX,
    S3_ENDPOINT_URL,
)
from database import get_db
from services.s3_cache import S3BackedCache

logger = logging.getLogger(__name__)

DATASET_SOURCE_TYPES = {
    "csv": "csv",
    "json": "json",
    "jsonl": "json",
    "parquet": "parquet",
}

EXT_BY_FORMAT = {v: k for k, v in DATASET_SOURCE_TYPES.items()}

_upload_executor = ThreadPoolExecutor(max_workers=2)


def _extract_extension(path: str) -> str:
    return Path(path.split("?")[0]).suffix.lower().lstrip(".")


def _detect_source(source: str) -> tuple[str, str, str]:
    """Returns (source_type, format, clean_source)."""
    if source.startswith("http://") or source.startswith("https://"):
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
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    suffix = f".{fmt}"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        for chunk in resp.iter_content(chunk_size=8192):
            tmp.write(chunk)
        tmp_path = tmp.name
    try:
        ds = _load_from_format(tmp_path, fmt, cache_dir)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return ds


def _cache_dir_for(ds_id: str) -> Path:
    return DATASETS_DIR / ds_id / "hf_cache"


class DatasetService:
    _instances: dict[str, Dataset] = {}
    _access_times: dict[str, float] = {}
    _s3_cache: S3BackedCache | None = None

    @classmethod
    def _s3(cls) -> S3BackedCache | None:
        if cls._s3_cache is None and S3_CACHE_ENABLED:
            if S3_CACHE_BUCKET:
                cls._s3_cache = S3BackedCache(bucket=S3_CACHE_BUCKET, prefix=S3_CACHE_PREFIX, endpoint_url=S3_ENDPOINT_URL)
            else:
                logger.warning("S3_CACHE_ENABLED is True but S3_CACHE_BUCKET is not set")
        return cls._s3_cache if S3_CACHE_ENABLED else None

    @classmethod
    def _evict_lru(cls, active_id: str | None = None) -> None:
        """Evict datasets from _instances when above MAX_CACHED_DATASETS."""
        if len(cls._instances) <= MAX_CACHED_DATASETS:
            return
        candidates = [(ds_id, cls._access_times.get(ds_id, 0))
                      for ds_id in cls._instances
                      if ds_id != active_id]
        if not candidates:
            return
        candidates.sort(key=lambda x: x[1])
        for ds_id, _ in candidates[:len(cls._instances) - MAX_CACHED_DATASETS]:
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
        logger.info("Disk usage %.1f%% exceeds threshold %.1f%%", ratio * 100, DISK_USAGE_THRESHOLD * 100)
        db = get_db()
        rows = db.execute(
            "SELECT id FROM datasets WHERE s3_uploaded = 1 ORDER BY created_at ASC"
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
    def load(cls, source: str, split: str = "train", name: str = None) -> dict:
        source_type, source_format, clean_source = _detect_source(source)
        ds_id = str(uuid.uuid4())
        cache_dir = _cache_dir_for(ds_id)
        cache_dir.mkdir(parents=True, exist_ok=True)

        if source_type == "huggingface":
            ds = load_dataset(clean_source, name, split=split, cache_dir=str(cache_dir))
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

        cls._instances[ds_id] = ds
        cls._access_times[ds_id] = time.monotonic()

        meta = {
            "id": ds_id,
            "source": source,
            "source_type": source_type,
            "source_format": source_format,
            "name": name,
            "split": split,
            "num_rows": len(ds),
            "columns": [{"name": col, "type": str(ds.features[col])} for col in ds.column_names],
            "created_at": datetime.utcnow().isoformat(),
        }

        # Upload to S3 immediately (synchronous) — fail if S3 is configured and upload fails
        s3 = cls._s3()
        if s3 is not None:
            try:
                s3.upload(ds_id, cache_dir)
            except Exception as e:
                shutil.rmtree(cache_dir, ignore_errors=True)
                cls._instances.pop(ds_id, None)
                cls._access_times.pop(ds_id, None)
                raise ValueError(f"Failed to upload dataset to S3: {e}") from e

        # Write to database
        s3_uploaded = 1 if s3 is not None else 0
        db = get_db()
        db.execute(
            """INSERT INTO datasets (id, source, source_type, source_format, hf_name, hf_split, num_rows, columns, created_at, s3_uploaded)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ds_id, source, source_type, source_format, name, split, len(ds),
             json.dumps(meta["columns"]), meta["created_at"], s3_uploaded),
        )
        db.commit()
        db.close()

        cls._evict_lru(ds_id)
        meta["s3_uploaded"] = bool(s3_uploaded)
        return meta

    @classmethod
    def list_datasets(cls) -> list[dict]:
        db = get_db()
        rows = db.execute("SELECT * FROM datasets ORDER BY created_at DESC").fetchall()
        db.close()
        result = []
        for row in rows:
            meta = {
                "id": row["id"],
                "source": row["source"],
                "source_type": row["source_type"],
                "source_format": row["source_format"],
                "name": row["hf_name"],
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
    def _load_ds(cls, ds_id: str) -> Dataset:
        ds = cls._instances.get(ds_id)
        if ds is not None:
            cls._access_times[ds_id] = time.monotonic()
            return ds

        # Read metadata from database
        db = get_db()
        row = db.execute("SELECT * FROM datasets WHERE id = ?", (ds_id,)).fetchone()
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
                ds = load_dataset(source, row["hf_name"],
                                  split=row["hf_split"],
                                  cache_dir=str(cache_dir))
            elif source_type == "http":
                fmt = row["source_format"] or "csv"
                ds = _load_http(source, fmt, cache_dir=str(cache_dir))
            elif source_type == "file":
                clean = source[7:] if source.startswith("file://") else source
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
            if isinstance(val, PILImage.Image):
                serialized[col] = f"/api/v1/datasets/{ds_id}/rows/{index}/columns/{col}"
            elif isinstance(val, Audio):
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
    def get_binary_column(cls, ds_id: str, index: int, column: str) -> tuple[bytes, str]:
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
    def load_upload(cls, filename: str, content: bytes) -> dict:
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext not in DATASET_SOURCE_TYPES:
            raise ValueError(
                f"Unsupported format: .{ext}. Supported: .csv, .json, .jsonl, .parquet"
            )
        fmt = DATASET_SOURCE_TYPES[ext]
        DATASETS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        dest = DATASETS_UPLOAD_DIR / f"{uuid.uuid4()}.{ext}"
        dest.write_bytes(content)
        return cls.load(f"file://{dest}")
