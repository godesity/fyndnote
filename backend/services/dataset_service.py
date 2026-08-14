import uuid
import json
from io import BytesIO
from datetime import datetime
from pathlib import Path
from datasets import load_dataset, Dataset, Image as HfImage, Audio
from config import DATASETS_DIR

class DatasetService:
    _instances: dict[str, Dataset] = {}

    @classmethod
    def load(cls, source: str, split: str = "train", name: str = None) -> dict:
        ds = load_dataset(source, name, split=split)
        ds_id = str(uuid.uuid4())
        cls._instances[ds_id] = ds

        meta = {
            "id": ds_id,
            "source": source,
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
        ds = load_dataset(meta["source"], meta["name"], split=meta["split"])
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
