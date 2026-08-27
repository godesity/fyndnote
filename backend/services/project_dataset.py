import json
from datetime import UTC, datetime

import pyarrow as pa
import pyarrow.parquet as pq

from config import PROJECTS_DIR
from database import get_db
from services.annotation_service import AnnotationService
from services.dataset_service import DatasetService


def _project_dir(pid: str):
    return PROJECTS_DIR / pid


def _frag_dir(pid: str):
    return _project_dir(pid) / "fragments"


def _media_dir(pid: str):
    return _project_dir(pid) / "media"


class ProjectDatasetService:
    """Storage for dynamically appended rows ("fragments") per project.

    The project's SOURCE dataset lives in its HuggingFace-backed dataset; rows
    appended at runtime are persisted as parquet fragments under PROJECTS_DIR.
    ``num_rows`` reports the combined total (source + fragments), while
    ``load_table`` returns only the fragment rows (concatenated in order).
    """

    @staticmethod
    def get_meta(pid: str) -> dict | None:
        db = get_db()
        row = db.execute(
            "SELECT * FROM dataset_meta WHERE project_id = ?", (pid,)
        ).fetchone()
        db.close()
        return dict(row) if row else None

    @staticmethod
    def ensure_meta(pid: str) -> dict:
        meta = ProjectDatasetService.get_meta(pid)
        if meta is not None:
            return meta
        project = AnnotationService.get_project(pid)
        if project is None:
            raise ValueError("Project not found")
        ds = DatasetService._load_ds(project["dataset_id"])
        schema = json.dumps(
            {
                "columns": [
                    {"name": c, "type": str(ds.features[c])} for c in ds.column_names
                ]
            }
        )
        db = get_db()
        db.execute(
            """INSERT INTO dataset_meta (project_id, num_rows, next_fragment, schema, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (pid, len(ds), 0, schema, datetime.now(UTC).isoformat()),
        )
        db.commit()
        db.close()
        return ProjectDatasetService.get_meta(pid)

    @staticmethod
    def append_rows(pid: str, rows: list[dict]) -> int:
        ProjectDatasetService.ensure_meta(pid)
        meta = ProjectDatasetService.get_meta(pid)
        table = pa.Table.from_pylist(rows)
        frag_dir = _frag_dir(pid)
        frag_dir.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, frag_dir / f"frag_{meta['next_fragment']}.parquet")

        schema_json = json.dumps([str(c) for c in table.schema])
        db = get_db()
        db.execute(
            """UPDATE dataset_meta
               SET num_rows = num_rows + ?, next_fragment = next_fragment + 1, schema = ?
               WHERE project_id = ?""",
            (len(rows), schema_json, pid),
        )
        db.commit()
        db.close()
        return len(rows)

    @staticmethod
    def load_table(pid: str) -> pa.Table:
        frag_dir = _frag_dir(pid)
        if not frag_dir.exists():
            return pa.Table.from_pylist([])
        files = sorted(
            frag_dir.glob("frag_*.parquet"),
            key=lambda p: int(p.stem[len("frag_") :]),
        )
        if not files:
            return pa.Table.from_pylist([])
        tables = [pq.read_table(f) for f in files]
        return pa.concat_tables(tables)

    @staticmethod
    def get_row(pid: str, i: int) -> dict | None:
        project = AnnotationService.get_project(pid)
        if project is None:
            return None
        ds = DatasetService._load_ds(project["dataset_id"])
        src_n = len(ds)
        if i < src_n:
            return DatasetService.get_row(project["dataset_id"], i)
        frag_i = i - src_n
        table = ProjectDatasetService.load_table(pid)
        if frag_i >= table.num_rows:
            return None
        row = table.slice(frag_i, 1).to_pylist()[0]
        return {k: ProjectDatasetService._json_safe(v) for k, v in row.items()}

    @staticmethod
    def num_rows(pid: str) -> int:
        meta = ProjectDatasetService.get_meta(pid)
        if meta is not None:
            return meta["num_rows"]
        project = AnnotationService.get_project(pid)
        if project is None:
            return 0
        return len(DatasetService._load_ds(project["dataset_id"]))

    @staticmethod
    def _json_safe(val):
        return DatasetService._json_safe(val)
