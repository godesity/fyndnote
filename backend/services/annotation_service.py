import uuid
import hashlib
import random
import json
from datetime import datetime
from database import get_db

class AnnotationService:
    @staticmethod
    def create_project(name: str, dataset_id: str, template_id: str, color: str = '#1976d2', tags: str = '', instructions: str = '') -> dict:
        db = get_db()
        pid = str(uuid.uuid4())
        salt = hashlib.sha256(f"{pid}:{name}".encode()).hexdigest()[:16]
        db.execute(
            "INSERT INTO projects (id, name, dataset_id, template_id, salt, color, tags, instructions) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (pid, name, dataset_id, template_id, salt, color, tags, instructions)
        )
        db.commit()
        proj = db.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        db.close()
        return dict(proj)

    @staticmethod
    def update_project(pid: str, name: str, color: str = None, tags: str = None, instructions: str = None) -> dict | None:
        db = get_db()
        sets = "name = ?"
        params = [name]
        if color is not None:
            sets += ", color = ?"
            params.append(color)
        if tags is not None:
            sets += ", tags = ?"
            params.append(tags)
        if instructions is not None:
            sets += ", instructions = ?"
            params.append(instructions)
        params.append(pid)
        db.execute(f"UPDATE projects SET {sets} WHERE id = ?", tuple(params))
        db.commit()
        p = db.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        db.close()
        return dict(p) if p else None

    @staticmethod
    def get_project(pid: str) -> dict | None:
        db = get_db()
        p = db.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        db.close()
        return dict(p) if p else None

    @staticmethod
    def list_projects(user_id: str) -> list[dict]:
        db = get_db()
        user = db.execute("SELECT global_role FROM users WHERE id = ?", (user_id,)).fetchone()
        if user and user["global_role"] == "system_admin":
            rows = db.execute("SELECT * FROM projects").fetchall()
        else:
            rows = db.execute("""
                SELECT p.*, pp.role FROM projects p
                JOIN project_permissions pp ON pp.project_id = p.id
                WHERE pp.user_id = ?
            """, (user_id,)).fetchall()
        db.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_progress(pid: str, user_id: str) -> dict:
        db = get_db()
        any_ann = db.execute(
            "SELECT COUNT(DISTINCT row_index) FROM annotations WHERE project_id = ?", (pid,)
        ).fetchone()[0]
        by_me = db.execute(
            "SELECT COUNT(DISTINCT row_index) FROM annotations WHERE project_id = ? AND user_id = ?",
            (pid, user_id)
        ).fetchone()[0]
        total = db.execute(
            "SELECT COUNT(*) FROM annotations WHERE project_id = ?", (pid,)
        ).fetchone()[0]
        db.close()
        return {"annotated_rows": any_ann, "annotated_by_me": by_me, "total_annotations": total}

    @staticmethod
    def next_row(pid: str, user_id: str, num_rows: int) -> int | None:
        db = get_db()
        salt = db.execute("SELECT salt FROM projects WHERE id = ?", (pid,)).fetchone()
        if not salt:
            db.close()
            return None
        salt = salt[0]
        indices = list(range(num_rows))
        seed = hashlib.sha256(f"{user_id}:{salt}".encode()).hexdigest()
        rng = random.Random(seed)
        rng.shuffle(indices)

        annotated = {
            r[0] for r in db.execute(
                "SELECT row_index FROM annotations WHERE project_id = ? AND user_id = ?",
                (pid, user_id)
            ).fetchall()
        }
        db.close()
        for idx in indices:
            if idx not in annotated:
                return idx
        return None

    @staticmethod
    def submit_annotation(pid: str, row_index: int, user_id: str, data: dict):
        db = get_db()
        now = datetime.utcnow().isoformat()
        db.execute("""
            INSERT INTO annotations (project_id, row_index, user_id, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, row_index, user_id)
            DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at
        """, (pid, row_index, user_id, json.dumps(data), now, now))
        db.commit()
        db.close()

    @staticmethod
    def get_annotation(pid: str, row_index: int, user_id: str) -> dict | None:
        db = get_db()
        row = db.execute(
            "SELECT * FROM annotations WHERE project_id = ? AND row_index = ? AND user_id = ?",
            (pid, row_index, user_id)
        ).fetchone()
        db.close()
        if not row:
            return None
        return {
            "row_index": row["row_index"],
            "user_id": row["user_id"],
            "data": json.loads(row["data"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def browse_rows(pid: str, user_id: str, page: int, per_page: int, status: str, include_annotations: bool) -> tuple:
        from services.dataset_service import DatasetService
        db = get_db()
        project = db.execute("SELECT dataset_id FROM projects WHERE id = ?", (pid,)).fetchone()
        if not project:
            db.close()
            return [], 0

        ds_id = project["dataset_id"]
        total_rows = len(DatasetService._load_ds(ds_id))

        # Annotations by current user
        annotated_by_me = {
            r[0] for r in db.execute(
                "SELECT row_index FROM annotations WHERE project_id = ? AND user_id = ?",
                (pid, user_id)
            ).fetchall()
        }

        # Annotations by any user
        all_annotations = db.execute(
            "SELECT row_index, user_id FROM annotations WHERE project_id = ?",
            (pid,)
        ).fetchall()

        any_annotated: dict[int, set[str]] = {}
        for r in all_annotations:
            any_annotated.setdefault(r["row_index"], set()).add(r["user_id"])

        db.close()

        all_indices = list(range(total_rows))

        if status == "annotated_by_me":
            indices = sorted(i for i in all_indices if i in annotated_by_me)
        elif status == "unannotated":
            indices = sorted(i for i in all_indices if i not in any_annotated)
        else:
            indices = all_indices

        total = len(indices)
        start = (page - 1) * per_page
        page_indices = indices[start:start + per_page]

        rows_data = []
        for idx in page_indices:
            row = DatasetService.get_row(ds_id, idx)
            annotators = list(any_annotated.get(idx, []))
            entry = {
                "index": idx,
                "preview": row,
                "annotation_status": {
                    "by_me": idx in annotated_by_me,
                    "by_any": idx in any_annotated,
                    "annotators": annotators,
                },
            }
            if include_annotations and idx in annotated_by_me:
                db2 = get_db()
                ann = db2.execute(
                    "SELECT data FROM annotations WHERE project_id = ? AND row_index = ? AND user_id = ?",
                    (pid, idx, user_id)
                ).fetchone()
                db2.close()
                if ann:
                    entry["annotation"] = json.loads(ann["data"])
            rows_data.append(entry)

        return rows_data, total

    @staticmethod
    def export_annotations(pid: str, format: str = "parquet"):
        if format != "parquet":
            raise ValueError(f"Unsupported export format: {format}")
        db = get_db()
        rows = db.execute(
            "SELECT row_index, user_id, data, created_at, updated_at FROM annotations WHERE project_id = ?",
            (pid,)
        ).fetchall()
        db.close()
        import pyarrow as pa
        import pyarrow.parquet as pq
        table = pa.Table.from_pylist([
            {
                "row_index": r["row_index"],
                "user_id": r["user_id"],
                "data": r["data"].encode(),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ])
        buf = pa.BufferOutputStream()
        pq.write_table(table, buf)
        return buf.getvalue().to_pybytes()
