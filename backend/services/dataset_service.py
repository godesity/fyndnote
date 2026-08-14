import uuid
import json
import requests
import tempfile
from io import BytesIO
from datetime import datetime
from pathlib import Path
from datasets import load_dataset, Dataset, Image as HfImage, Audio
from config import DATASETS_DIR

DATASET_SOURCE_TYPES = {
    "csv": "csv",
    "json": "json",
    "jsonl": "json",
    "parquet": "parquet",
}


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
        ext = _extract_extension(path)
        if ext not in DATASET_SOURCE_TYPES:
            raise ValueError(
                f"Unsupported format: .{ext}. Supported: .csv, .json, .jsonl, .parquet"
            )
        return ("file", DATASET_SOURCE_TYPES[ext], path)
    else:
        return ("huggingface", None, source)


def _load_from_format(path: str, fmt: str) -> Dataset:
    format_map = {
        "csv": lambda p: load_dataset("csv", data_files=p, split="train"),
        "json": lambda p: load_dataset("json", data_files=p, split="train"),
        "jsonl": lambda p: load_dataset("json", data_files=p, split="train"),
        "parquet": lambda p: load_dataset("parquet", data_files=p, split="train"),
    }
    loader = format_map.get(fmt)
    if not loader:
        raise ValueError(f"Unsupported format: {fmt}")
    return loader(path)


def _load_file(path: str, fmt: str) -> Dataset:
    if not Path(path).exists():
        raise FileNotFoundError(f"File not found: {path}")
    return _load_from_format(path, fmt)


def _load_http(url: str, fmt: str) -> Dataset:
    resp = requests.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    suffix = f".{fmt}"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        for chunk in resp.iter_content(chunk_size=8192):
            tmp.write(chunk)
        tmp_path = tmp.name
    try:
        ds = _load_from_format(tmp_path, fmt)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return ds


class DatasetService:
    _instances: dict[str, Dataset] = {}

    @classmethod
    def load(cls, source: str, split: str = "train", name: str = None) -> dict:
        source_type, source_format, clean_source = _detect_source(source)
        ds_id = str(uuid.uuid4())

        if source_type == "huggingface":
            ds = load_dataset(clean_source, name, split=split)
        elif source_type == "http":
            ds = _load_http(clean_source, source_format)
            split = None
            name = None
        elif source_type == "file":
            ds = _load_file(clean_source, source_format)
            split = None
            name = None
        else:
            raise ValueError(f"Unknown source type: {source_type}")

        cls._instances[ds_id] = ds
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
        meta_dir = DATASETS_DIR / ds_id
        meta_dir.mkdir(parents=True, exist_ok=True)
        with open(meta_dir / "meta.json", "w") as f:
            json.dump(meta, f, indent=2)
        return meta

    @classmethod
    def list_datasets(cls) -> list[dict]:
        if not DATASETS_DIR.exists():
            return []
        result = []
        for d in DATASETS_DIR.iterdir():
            meta_file = d / "meta.json"
            if meta_file.exists():
                with open(meta_file) as f:
                    result.append(json.load(f))
        return result

    @classmethod
    def _load_ds(cls, ds_id: str) -> Dataset:
        ds = cls._instances.get(ds_id)
        if ds is not None:
            return ds
        meta_path = DATASETS_DIR / ds_id / "meta.json"
        if not meta_path.exists():
            raise ValueError("Dataset not found")
        with open(meta_path) as f:
            meta = json.load(f)
        source_type = meta.get("source_type", "huggingface")
        source = meta["source"]
        if source_type == "huggingface":
            ds = load_dataset(meta.get("source"), meta.get("name"), split=meta.get("split", "train"))
        elif source_type == "http":
            fmt = meta.get("source_format", "csv")
            ds = _load_http(source, fmt)
        elif source_type == "file":
            clean = source[7:] if source.startswith("file://") else source
            fmt = meta.get("source_format", "csv")
            ds = _load_file(clean, fmt)
        else:
            raise ValueError(f"Unknown source type: {source_type}")
        cls._instances[ds_id] = ds
        return ds

    @classmethod
    def get_row(cls, ds_id: str, index: int) -> dict:
        ds = cls._load_ds(ds_id)
        row = ds[index]
        serialized = {}
        for col, val in row.items():
            if isinstance(val, HfImage):
                serialized[col] = f"/api/v1/datasets/{ds_id}/rows/{index}/columns/{col}"
            elif isinstance(val, Audio):
                serialized[col] = f"/api/v1/datasets/{ds_id}/rows/{index}/columns/{col}"
            elif isinstance(val, dict) or isinstance(val, list):
                serialized[col] = val
            else:
                serialized[col] = val
        return serialized

    @classmethod
    def get_binary_column(cls, ds_id: str, index: int, column: str) -> tuple[bytes, str]:
        ds = cls._load_ds(ds_id)
        val = ds[index][column]
        content_type = "application/octet-stream"
        if isinstance(val, HfImage):
            buf = BytesIO()
            val.save(buf, format="JPEG")
            buf.seek(0)
            content_type = "image/jpeg"
            return buf.read(), content_type
        if isinstance(val, Audio):
            raw = val["array"].tobytes()
            content_type = "audio/wav"
            return raw, content_type
        return str(val).encode(), content_type
