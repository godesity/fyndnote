import uuid
import json
from pathlib import Path
from datetime import datetime
from config import TEMPLATES_DIR

class TemplateService:
    @staticmethod
    def _path(tid: str) -> Path:
        return TEMPLATES_DIR / f"{tid}.json"

    @classmethod
    def create(cls, name: str, source: str, validated: bool = False) -> dict:
        tid = str(uuid.uuid4())
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        now = datetime.utcnow().isoformat()
        data = {
            "id": tid,
            "name": name,
            "source": source,
            "project_id": None,
            "validated": validated,
            "created_at": now,
            "updated_at": now,
        }
        with open(cls._path(tid), "w") as f:
            json.dump(data, f, indent=2)
        return data

    @classmethod
    def get(cls, tid: str) -> dict | None:
        path = cls._path(tid)
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    @classmethod
    def update(cls, tid: str, source: str = None, validated: bool = None) -> dict | None:
        data = cls.get(tid)
        if data is None:
            return None
        if source is not None:
            data["source"] = source
        if validated is not None:
            data["validated"] = validated
        data["updated_at"] = datetime.utcnow().isoformat()
        with open(cls._path(tid), "w") as f:
            json.dump(data, f, indent=2)
        return data

    @classmethod
    def list_all(cls) -> list[dict]:
        if not TEMPLATES_DIR.exists():
            return []
        result = []
        for f in TEMPLATES_DIR.iterdir():
            if f.suffix == ".json":
                with open(f) as fp:
                    result.append(json.load(fp))
        return result
