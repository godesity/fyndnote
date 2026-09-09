import hashlib
import json
import random
import re
import uuid
from datetime import datetime, timedelta, timezone

import pyarrow as pa
import pyarrow.compute as pc

from config import DATABASE_TYPE
from database import get_db
from services.dataset_service import DatasetService


def _apply_row_index_filter(indices: list[int], expr) -> list[int]:
    val = int(expr.value)
    match expr.operator:
        case "=":
            return [i for i in indices if i == val]
        case "!=":
            return [i for i in indices if i != val]
        case ">":
            return [i for i in indices if i > val]
        case ">=":
            return [i for i in indices if i >= val]
        case "<":
            return [i for i in indices if i < val]
        case "<=":
            return [i for i in indices if i <= val]
        case _:
            return indices


def _apply_annotation_meta_filter(
    db, project_indices: list[int], expr, user_id: str, pid: str
) -> list[int]:
    if not project_indices:
        return []

    if expr.field == "annotations.count":
        op = expr.operator
        val = int(expr.value)
        placeholders = ",".join("?" * len(project_indices))
        # For = 0, < 1, <= 0: find rows NOT in annotations table
        if (
            (op == "=" and val == 0)
            or (op == "<" and val == 1)
            or (op == "<=" and val == 0)
        ):
            sql_annotated = f"""
                SELECT DISTINCT row_index FROM fyndnote_annotations
                WHERE project_id = ? AND row_index IN ({placeholders})
            """
            annotated = {
                r[0]
                for r in db.execute(sql_annotated, [pid] + project_indices).fetchall()
            }
            return [i for i in project_indices if i not in annotated]
        # For > 0, >= 1: find rows IN annotations with the given count condition
        sql = f"""
            SELECT row_index FROM fyndnote_annotations
            WHERE project_id = ?
              AND row_index IN ({placeholders})
            GROUP BY row_index
            HAVING COUNT(*) {op} ?
        """
        params = [pid] + project_indices + [val]
        matched = {r[0] for r in db.execute(sql, params).fetchall()}
        return [i for i in project_indices if i in matched]

    elif expr.field == "annotations.annotated_by":
        val = expr.value
        if val == "me":
            val = user_id
        placeholders = ",".join("?" * len(project_indices))
        sql = f"""
            SELECT DISTINCT row_index FROM fyndnote_annotations
            WHERE project_id = ?
              AND user_id = ?
              AND row_index IN ({placeholders})
        """
        params = [pid, val] + project_indices
        matched = {r[0] for r in db.execute(sql, params).fetchall()}
        return [i for i in project_indices if i in matched]

    elif expr.field in ("annotations.created_at", "annotations.updated_at"):
        val = _parse_time_value(expr.value)
        op = expr.operator
        col = expr.field.split(".")[1]  # created_at or updated_at
        placeholders = ",".join("?" * len(project_indices))
        sql = f"""
            SELECT DISTINCT row_index FROM fyndnote_annotations
            WHERE project_id = ?
              AND row_index IN ({placeholders})
              AND {col} {op} ?
        """
        params = [pid] + project_indices + [val]
        matched = {r[0] for r in db.execute(sql, params).fetchall()}
        return [i for i in project_indices if i in matched]

    return project_indices


RELATIVE_TIME_RE = re.compile(r"^(\d+)([mhdMY])$")


def _parse_time_value(val: str) -> str:
    m = RELATIVE_TIME_RE.match(val)
    if m:
        amount = int(m.group(1))
        unit = m.group(2)
        now = datetime.now(timezone.utc)
        if unit == "m":
            threshold = now - timedelta(minutes=amount)
        elif unit == "h":
            threshold = now - timedelta(hours=amount)
        elif unit == "d":
            threshold = now - timedelta(days=amount)
        elif unit == "M":
            threshold = now - timedelta(days=amount * 30)
        elif unit == "Y":
            threshold = now - timedelta(days=amount * 365)
        return threshold.isoformat()
    return val


def _apply_annotation_data_filter(
    db, project_indices: list[int], expr, pid: str
) -> list[int]:
    if not project_indices or not expr.field.startswith("annotation."):
        return project_indices
    field_name = expr.field[len("annotation.") :]
    json_path = f"$.{field_name}"
    op = expr.operator
    val = expr.value
    placeholders = ",".join("?" * len(project_indices))
    pg_path = "{" + field_name.replace(".", ",") + "}"

    # SQLite: json_extract returns the typed JSON value. PG: #>> returns text, so numeric
    # comparisons need an explicit cast to match SQLite's implicit affinity coercion.
    if DATABASE_TYPE == "postgres":
        if op == "~=":
            sql = f"""
                SELECT DISTINCT row_index FROM fyndnote_annotations
                WHERE project_id = ?
                  AND row_index IN ({placeholders})
                  AND data::jsonb #>> ? LIKE ?
            """
            params = [pid] + project_indices + [pg_path, f"%{val}%"]
        elif op == "=":
            try:
                num_val = float(val) if "." in val else int(val)
                sql = f"""
                    SELECT DISTINCT row_index FROM fyndnote_annotations
                    WHERE project_id = ?
                      AND row_index IN ({placeholders})
                      AND CAST(data::jsonb #>> ? AS NUMERIC) = ?
                """
                params = [pid] + project_indices + [pg_path, num_val]
            except (ValueError, TypeError):
                sql = f"""
                    SELECT DISTINCT row_index FROM fyndnote_annotations
                    WHERE project_id = ?
                      AND row_index IN ({placeholders})
                      AND data::jsonb #>> ? = ?
                """
                params = [pid] + project_indices + [pg_path, val]
        elif op == "!=":
            try:
                num_val = float(val) if "." in val else int(val)
                sql = f"""
                    SELECT DISTINCT row_index FROM fyndnote_annotations
                    WHERE project_id = ?
                      AND row_index IN ({placeholders})
                      AND CAST(data::jsonb #>> ? AS NUMERIC) != ?
                """
                params = [pid] + project_indices + [pg_path, num_val]
            except (ValueError, TypeError):
                sql = f"""
                    SELECT DISTINCT row_index FROM fyndnote_annotations
                    WHERE project_id = ?
                      AND row_index IN ({placeholders})
                      AND data::jsonb #>> ? != ?
                """
                params = [pid] + project_indices + [pg_path, val]
        elif op in (">", ">=", "<", "<="):
            sql = f"""
                SELECT DISTINCT row_index FROM fyndnote_annotations
                WHERE project_id = ?
                  AND row_index IN ({placeholders})
                  AND CAST(data::jsonb #>> ? AS NUMERIC) {op} ?
            """
            params = [pid] + project_indices + [pg_path, float(val)]
        else:
            return project_indices
        matched = {r[0] for r in db.execute(sql, params).fetchall()}
        return [i for i in project_indices if i in matched]

    if op == "~=":
        sql = f"""
            SELECT DISTINCT row_index FROM fyndnote_annotations
            WHERE project_id = ?
              AND row_index IN ({placeholders})
              AND json_extract(data, ?) LIKE ?
        """
        params = [pid] + project_indices + [json_path, f"%{val}%"]
    elif op == "=":
        sql = f"""
            SELECT DISTINCT row_index FROM fyndnote_annotations
            WHERE project_id = ?
              AND row_index IN ({placeholders})
              AND json_extract(data, ?) = ?
        """
        try:
            num_val = float(val) if "." in val else int(val)
            params = [pid] + project_indices + [json_path, num_val]
        except (ValueError, TypeError):
            params = [pid] + project_indices + [json_path, val]
    elif op == "!=":
        sql = f"""
            SELECT DISTINCT row_index FROM fyndnote_annotations
            WHERE project_id = ?
              AND row_index IN ({placeholders})
              AND json_extract(data, ?) != ?
        """
        try:
            num_val = float(val) if "." in val else int(val)
            params = [pid] + project_indices + [json_path, num_val]
        except (ValueError, TypeError):
            params = [pid] + project_indices + [json_path, val]
    elif op in (">", ">=", "<", "<="):
        sql = f"""
            SELECT DISTINCT row_index FROM fyndnote_annotations
            WHERE project_id = ?
              AND row_index IN ({placeholders})
              AND CAST(json_extract(data, ?) AS REAL) {op} ?
        """
        params = [pid] + project_indices + [json_path, float(val)]
    else:
        return project_indices

    matched = {r[0] for r in db.execute(sql, params).fetchall()}
    return [i for i in project_indices if i in matched]


def _apply_ml_annotation_data_filter(
    db, project_indices: list[int], expr, pid: str
) -> list[int]:
    """Filter rows by values inside the ML annotation (prediction) JSON data."""
    if not project_indices or not expr.field.startswith("prediction."):
        return project_indices
    field_name = expr.field[len("prediction.") :]
    json_path = f"$.{field_name}"
    op = expr.operator
    val = expr.value
    placeholders = ",".join("?" * len(project_indices))
    pg_path = "{" + field_name.replace(".", ",") + "}"

    if DATABASE_TYPE == "postgres":
        if op == "~=":
            sql = f"""
                SELECT DISTINCT row_index FROM fyndnote_ml_annotations
                WHERE project_id = ?
                  AND row_index IN ({placeholders})
                  AND data::jsonb #>> ? LIKE ?
            """
            params = [pid] + project_indices + [pg_path, f"%{val}%"]
        elif op == "=":
            try:
                num_val = float(val) if "." in val else int(val)
                sql = f"""
                    SELECT DISTINCT row_index FROM fyndnote_ml_annotations
                    WHERE project_id = ?
                      AND row_index IN ({placeholders})
                      AND CAST(data::jsonb #>> ? AS NUMERIC) = ?
                """
                params = [pid] + project_indices + [pg_path, num_val]
            except (ValueError, TypeError):
                sql = f"""
                    SELECT DISTINCT row_index FROM fyndnote_ml_annotations
                    WHERE project_id = ?
                      AND row_index IN ({placeholders})
                      AND data::jsonb #>> ? = ?
                """
                params = [pid] + project_indices + [pg_path, val]
        elif op in (">", ">=", "<", "<="):
            sql = f"""
                SELECT DISTINCT row_index FROM fyndnote_ml_annotations
                WHERE project_id = ?
                  AND row_index IN ({placeholders})
                  AND CAST(data::jsonb #>> ? AS NUMERIC) {op} ?
            """
            params = [pid] + project_indices + [pg_path, float(val)]
        else:
            return project_indices
    else:
        if op == "~=":
            sql = f"""
                SELECT DISTINCT row_index FROM fyndnote_ml_annotations
                WHERE project_id = ?
                  AND row_index IN ({placeholders})
                  AND json_extract(data, ?) LIKE ?
            """
            params = [pid] + project_indices + [json_path, f"%{val}%"]
        elif op == "=":
            try:
                num_val = float(val) if "." in val else int(val)
                sql = f"""
                    SELECT DISTINCT row_index FROM fyndnote_ml_annotations
                    WHERE project_id = ?
                      AND row_index IN ({placeholders})
                      AND json_extract(data, ?) = ?
                """
                params = [pid] + project_indices + [json_path, num_val]
            except (ValueError, TypeError):
                sql = f"""
                    SELECT DISTINCT row_index FROM fyndnote_ml_annotations
                    WHERE project_id = ?
                      AND row_index IN ({placeholders})
                      AND json_extract(data, ?) = ?
                """
                params = [pid] + project_indices + [json_path, val]
        elif op in (">", ">=", "<", "<="):
            sql = f"""
                SELECT DISTINCT row_index FROM fyndnote_ml_annotations
                WHERE project_id = ?
                  AND row_index IN ({placeholders})
                  AND CAST(json_extract(data, ?) AS REAL) {op} ?
            """
            params = [pid] + project_indices + [json_path, float(val)]
        else:
            return project_indices

    matched = {r[0] for r in db.execute(sql, params).fetchall()}
    return [i for i in project_indices if i in matched]


def _apply_ml_annotation_meta_filter(
    db, project_indices: list[int], expr, pid: str
) -> list[int]:
    """Filter rows by ML annotation (prediction) metadata. One row per row_index."""
    if not project_indices:
        return []

    if expr.field == "predictions.count":
        op = expr.operator
        val = int(expr.value)
        placeholders = ",".join("?" * len(project_indices))
        present = {
            r[0]
            for r in db.execute(
                f"SELECT DISTINCT row_index FROM fyndnote_ml_annotations WHERE project_id = ? AND row_index IN ({placeholders})",
                [pid] + project_indices,
            ).fetchall()
        }
        # One row per row_index, so count is either 0 or 1.
        if (op == "=" and val == 0) or (op == "<" and val == 1) or (op == "<=" and val == 0):
            return [i for i in project_indices if i not in present]
        if (op == "=" and val == 1) or (op == ">" and val == 0) or (op == ">=" and val == 1):
            return [i for i in project_indices if i in present]
        return project_indices

    elif expr.field == "predictions.name":
        val = expr.value
        placeholders = ",".join("?" * len(project_indices))
        sql = f"""
            SELECT DISTINCT row_index FROM fyndnote_ml_annotations
            WHERE project_id = ?
              AND row_index IN ({placeholders})
              AND annotator = ?
        """
        matched = {r[0] for r in db.execute(sql, [pid] + project_indices + [val]).fetchall()}
        return [i for i in project_indices if i in matched]

    elif expr.field in ("predictions.created_at", "predictions.updated_at"):
        op = expr.operator
        val = expr.value
        col = expr.field.split(".")[1]
        placeholders = ",".join("?" * len(project_indices))
        sql = f"""
            SELECT DISTINCT row_index FROM fyndnote_ml_annotations
            WHERE project_id = ?
              AND row_index IN ({placeholders})
              AND {col} {op} ?
        """
        matched = {r[0] for r in db.execute(sql, [pid] + project_indices + [val]).fetchall()}
        return [i for i in project_indices if i in matched]

    return project_indices


def _apply_data_field_filter(indices: list[int], expr, ds) -> list[int]:
    if not indices or not expr.field.startswith("data."):
        return indices
    field_name = expr.field[len("data.") :]
    col = ds.data.column(field_name)
    col_type = ds.features[field_name].pa_type
    op = expr.operator
    val = expr.value

    try:
        if op == "~=":
            if pa.types.is_string(col_type) or pa.types.is_large_string(col_type):
                mask = pc.match_substring(col, val)
            else:
                str_col = pc.cast(col, pa.large_string())
                mask = pc.match_substring(str_col, val)
        elif op == "=":
            if pa.types.is_integer(col_type):
                mask = pc.equal(col, int(val))
            elif pa.types.is_floating(col_type):
                mask = pc.equal(col, float(val))
            else:
                mask = pc.equal(col, val)
        elif op == "!=":
            if pa.types.is_integer(col_type):
                mask = pc.not_equal(col, int(val))
            elif pa.types.is_floating(col_type):
                mask = pc.not_equal(col, float(val))
            else:
                mask = pc.not_equal(col, val)
        elif op == ">":
            mask = pc.greater(col, float(val))
        elif op == ">=":
            mask = pc.greater_equal(col, float(val))
        elif op == "<":
            mask = pc.less(col, float(val))
        elif op == "<=":
            mask = pc.less_equal(col, float(val))
        else:
            return indices
    except Exception:
        return [i for i in indices if _pyarrow_fallback(col[i].as_py(), op, val)]

    mask_list = mask.to_pylist()
    return [i for i in indices if i < len(mask_list) and mask_list[i]]


def _pyarrow_fallback(py_val, op: str, search_val: str) -> bool:
    try:
        if op == "~=":
            return search_val in str(py_val)
        if op == "=":
            return str(py_val) == search_val
        if op == "!=":
            return str(py_val) != search_val
        num = float(search_val)
        if isinstance(py_val, (int, float)):
            if op == ">":
                return py_val > num
            if op == ">=":
                return py_val >= num
            if op == "<":
                return py_val < num
            if op == "<=":
                return py_val <= num
    except (ValueError, TypeError):
        return False
    return False


def _resolve_matching_indices(pid: str, user_id: str, filter_exprs: list) -> list[int]:
    """Apply the browse filter pipeline and return the matching row indices."""
    db = get_db()
    project = db.execute(
        "SELECT dataset_id FROM fyndnote_projects WHERE id = ?", (pid,)
    ).fetchone()
    if not project:
        db.close()
        return []

    ds_id = project["dataset_id"]
    ds = DatasetService._load_ds(ds_id)
    from services.project_dataset import ProjectDatasetService

    meta = ProjectDatasetService.get_meta(pid)
    if meta is not None:
        num_rows = ProjectDatasetService.num_rows(pid)
    else:
        num_rows = len(ds)

    current = list(range(num_rows))

    if not filter_exprs:
        db.close()
        return current

    row_index_exprs = [fe for fe in filter_exprs if fe.field == "row_index"]
    for expr in row_index_exprs:
        current = _apply_row_index_filter(current, expr)

    meta_exprs = [
        fe
        for fe in filter_exprs
        if fe.field.startswith("annotations.") and fe.field != "annotations."
    ]
    for expr in meta_exprs:
        current = _apply_annotation_meta_filter(db, current, expr, user_id, pid)

    ann_exprs = [
        fe
        for fe in filter_exprs
        if fe.field.startswith("annotation.") and fe.field != "annotation."
    ]
    for expr in ann_exprs:
        current = _apply_annotation_data_filter(db, current, expr, pid)

    ml_meta_exprs = [
        fe
        for fe in filter_exprs
        if fe.field.startswith("predictions.") and fe.field != "predictions."
    ]
    for expr in ml_meta_exprs:
        current = _apply_ml_annotation_meta_filter(db, current, expr, pid)

    ml_data_exprs = [
        fe
        for fe in filter_exprs
        if fe.field.startswith("prediction.") and fe.field != "prediction."
    ]
    for expr in ml_data_exprs:
        current = _apply_ml_annotation_data_filter(db, current, expr, pid)

    data_exprs = [
        fe
        for fe in filter_exprs
        if fe.field.startswith("data.") and fe.field != "data."
    ]
    for expr in data_exprs:
        current = _apply_data_field_filter(current, expr, ds)

    db.close()
    return current


class AnnotationService:
    @staticmethod
    def create_project(
        name: str,
        dataset_id: str,
        template_id: str,
        color: str = "#1976d2",
        tags: str = "",
        instructions: str = "",
        ml_enabled: bool = False,
        ml_url: str = "",
        ml_annotator: str = "",
        ml_mode: str = "on_navigate",
        user_id: str | None = None,
    ) -> dict:
        db = get_db()
        pid = str(uuid.uuid4())
        salt = hashlib.sha256(f"{pid}:{name}".encode()).hexdigest()[:16]
        db.execute(
            "INSERT INTO fyndnote_projects (id, name, dataset_id, template_id, salt, color, tags, instructions, ml_enabled, ml_url, ml_annotator, ml_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                pid,
                name,
                dataset_id,
                template_id,
                salt,
                color,
                tags,
                instructions,
                int(ml_enabled),
                ml_url,
                ml_annotator,
                ml_mode,
            ),
        )
        # Grant the creator access to the project so it shows up in /projects
        # for non-admin users (list_projects filters by fyndnote_project_permissions).
        if user_id:
            db.execute(
                "INSERT OR IGNORE INTO fyndnote_project_permissions (user_id, project_id, role) VALUES (?, ?, ?)",
                (user_id, pid, "project_admin"),
            )
        db.commit()
        proj = db.execute(
            "SELECT * FROM fyndnote_projects WHERE id = ?", (pid,)
        ).fetchone()
        db.close()
        return dict(proj)

    @staticmethod
    def update_project(
        pid: str,
        name: str,
        color: str | None = None,
        tags: str | None = None,
        instructions: str | None = None,
        ml_enabled: bool | None = None,
        ml_url: str | None = None,
        ml_annotator: str | None = None,
        ml_mode: str | None = None,
    ) -> dict | None:
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
        if ml_enabled is not None:
            sets += ", ml_enabled = ?"
            params.append(int(ml_enabled))
        if ml_url is not None:
            sets += ", ml_url = ?"
            params.append(ml_url)
        if ml_annotator is not None:
            sets += ", ml_annotator = ?"
            params.append(ml_annotator)
        if ml_mode is not None:
            sets += ", ml_mode = ?"
            params.append(ml_mode)
        params.append(pid)
        db.execute(f"UPDATE fyndnote_projects SET {sets} WHERE id = ?", tuple(params))
        db.commit()
        p = db.execute("SELECT * FROM fyndnote_projects WHERE id = ?", (pid,)).fetchone()
        db.close()
        return dict(p) if p else None

    @staticmethod
    def delete_project(pid: str) -> bool:
        db = get_db()
        row = db.execute("SELECT 1 FROM fyndnote_projects WHERE id = ?", (pid,)).fetchone()
        if not row:
            db.close()
            return False
        db.execute("DELETE FROM fyndnote_annotations WHERE project_id = ?", (pid,))
        db.execute("DELETE FROM fyndnote_ml_annotations WHERE project_id = ?", (pid,))
        db.execute("DELETE FROM fyndnote_project_permissions WHERE project_id = ?", (pid,))
        db.execute("DELETE FROM fyndnote_projects WHERE id = ?", (pid,))
        db.commit()
        db.close()
        return True

    @staticmethod
    def get_project(pid: str) -> dict | None:
        db = get_db()
        p = db.execute("SELECT * FROM fyndnote_projects WHERE id = ?", (pid,)).fetchone()
        db.close()
        return dict(p) if p else None

    @staticmethod
    def list_projects(user_id: str) -> list[dict]:
        db = get_db()
        user = db.execute(
            "SELECT global_role FROM fyndnote_users WHERE id = ?", (user_id,)
        ).fetchone()
        if user and user["global_role"] == "system_admin":
            rows = db.execute("SELECT * FROM fyndnote_projects").fetchall()
        else:
            rows = db.execute(
                """
                SELECT p.*, pp.role FROM fyndnote_projects p
                JOIN fyndnote_project_permissions pp ON pp.project_id = p.id
                WHERE pp.user_id = ?
            """,
                (user_id,),
            ).fetchall()
        db.close()
        return [dict(r) for r in rows]

    @staticmethod
    def get_progress(pid: str, user_id: str) -> dict:
        db = get_db()
        any_ann = db.execute(
            "SELECT COUNT(DISTINCT row_index) FROM fyndnote_annotations WHERE project_id = ?",
            (pid,),
        ).fetchone()[0]
        by_me = db.execute(
            "SELECT COUNT(DISTINCT row_index) FROM fyndnote_annotations WHERE project_id = ? AND user_id = ?",
            (pid, user_id),
        ).fetchone()[0]
        total = db.execute(
            "SELECT COUNT(*) FROM fyndnote_annotations WHERE project_id = ?", (pid,)
        ).fetchone()[0]
        db.close()
        return {
            "annotated_rows": any_ann,
            "annotated_by_me": by_me,
            "total_annotations": total,
        }

    @staticmethod
    def next_row(pid: str, user_id: str, num_rows: int) -> int | None:
        db = get_db()
        salt = db.execute(
            "SELECT salt FROM fyndnote_projects WHERE id = ?", (pid,)
        ).fetchone()
        if not salt:
            db.close()
            return None
        salt = salt[0]
        indices = list(range(num_rows))
        seed = hashlib.sha256(f"{user_id}:{salt}".encode()).hexdigest()
        rng = random.Random(seed)
        rng.shuffle(indices)

        annotated = {
            r[0]
            for r in db.execute(
                "SELECT row_index FROM fyndnote_annotations WHERE project_id = ? AND user_id = ?",
                (pid, user_id),
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
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            """
            INSERT INTO fyndnote_annotations (project_id, row_index, user_id, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id, row_index, user_id)
            DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at
        """,
            (pid, row_index, user_id, json.dumps(data), now, now),
        )
        db.commit()
        db.close()

    @staticmethod
    def get_annotation(pid: str, row_index: int, user_id: str) -> dict | None:
        db = get_db()
        row = db.execute(
            "SELECT * FROM fyndnote_annotations WHERE project_id = ? AND row_index = ? AND user_id = ?",
            (pid, row_index, user_id),
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
    def delete_annotation(pid: str, row_index: int, user_id: str | None = None) -> int:
        db = get_db()
        if user_id is not None:
            cur = db.execute(
                "DELETE FROM fyndnote_annotations WHERE project_id = ? AND row_index = ? AND user_id = ?",
                (pid, row_index, user_id),
            )
        else:
            cur = db.execute(
                "DELETE FROM fyndnote_annotations WHERE project_id = ? AND row_index = ?",
                (pid, row_index),
            )
        db.commit()
        db.close()
        return cur.rowcount

    @staticmethod
    def delete_all_annotations(pid: str) -> int:
        db = get_db()
        cur = db.execute("DELETE FROM fyndnote_annotations WHERE project_id = ?", (pid,))
        db.commit()
        db.close()
        return cur.rowcount

    @staticmethod
    def delete_ml_annotation(pid: str, row_index: int) -> int:
        db = get_db()
        cur = db.execute(
            "DELETE FROM fyndnote_ml_annotations WHERE project_id = ? AND row_index = ?",
            (pid, row_index),
        )
        db.commit()
        db.close()
        return cur.rowcount

    @staticmethod
    def delete_all_ml_annotations(pid: str) -> int:
        db = get_db()
        cur = db.execute("DELETE FROM fyndnote_ml_annotations WHERE project_id = ?", (pid,))
        db.commit()
        db.close()
        return cur.rowcount

    @staticmethod
    def delete_annotations_for_rows(pid: str, row_indices: list[int]) -> int:
        if not row_indices:
            return 0
        db = get_db()
        placeholders = ",".join("?" * len(row_indices))
        cur = db.execute(
            f"DELETE FROM fyndnote_annotations WHERE project_id = ? AND row_index IN ({placeholders})",
            [pid] + row_indices,
        )
        db.commit()
        db.close()
        return cur.rowcount

    @staticmethod
    def delete_ml_annotations_for_rows(pid: str, row_indices: list[int]) -> int:
        if not row_indices:
            return 0
        db = get_db()
        placeholders = ",".join("?" * len(row_indices))
        cur = db.execute(
            f"DELETE FROM fyndnote_ml_annotations WHERE project_id = ? AND row_index IN ({placeholders})",
            [pid] + row_indices,
        )
        db.commit()
        db.close()
        return cur.rowcount

    @staticmethod
    def get_row_annotation_status(pid: str, row_index: int, user_id: str) -> dict:
        db = get_db()
        rows = db.execute(
            "SELECT user_id FROM fyndnote_annotations WHERE project_id = ? AND row_index = ?",
            (pid, row_index),
        ).fetchall()
        db.close()
        annotators = [r[0] for r in rows]
        return {
            "by_me": user_id in annotators,
            "by_any": len(annotators) > 0,
            "annotators": annotators,
        }

    @staticmethod
    def get_project_row(pid: str, row_index: int, user_id: str) -> dict | None:
        project = AnnotationService.get_project(pid)
        if not project:
            return None
        ds_id = project["dataset_id"]
        from services.project_dataset import ProjectDatasetService

        meta = ProjectDatasetService.get_meta(pid)
        if meta is not None:
            row = ProjectDatasetService.get_row(pid, row_index)
        else:
            try:
                row = DatasetService.get_row(ds_id, row_index)
            except IndexError:
                return None
        status = AnnotationService.get_row_annotation_status(pid, row_index, user_id)
        return {"index": row_index, "row": row, "annotation_status": status}

    @staticmethod
    def navigate_row(
        pid: str, user_id: str, current_index: int, direction: int
    ) -> dict | None:
        project = AnnotationService.get_project(pid)
        if not project:
            return None
        ds_id = project["dataset_id"]
        db = get_db()
        salt = db.execute(
            "SELECT salt FROM fyndnote_projects WHERE id = ?", (pid,)
        ).fetchone()
        db.close()
        if not salt:
            return None
        from services.project_dataset import ProjectDatasetService

        meta = ProjectDatasetService.get_meta(pid)
        if meta is not None:
            num_rows = meta["num_rows"]
        else:
            ds = DatasetService._load_ds(ds_id)
            num_rows = len(ds)
        indices = list(range(num_rows))
        seed = hashlib.sha256(f"{user_id}:{salt[0]}".encode()).hexdigest()
        rng = random.Random(seed)
        rng.shuffle(indices)
        try:
            cur = indices.index(current_index)
        except ValueError:
            return None
        new_pos = cur + direction
        if new_pos < 0 or new_pos >= len(indices):
            return None
        new_idx = indices[new_pos]
        if meta is not None:
            row = ProjectDatasetService.get_row(pid, new_idx)
        else:
            row = DatasetService.get_row(ds_id, new_idx)
        status = AnnotationService.get_row_annotation_status(pid, new_idx, user_id)
        return {"index": new_idx, "row": row, "annotation_status": status}

    @staticmethod
    def browse_rows(
        pid: str, user_id: str, page: int, per_page: int, filter_exprs: list
    ) -> tuple:
        db = get_db()
        project = db.execute(
            "SELECT dataset_id FROM fyndnote_projects WHERE id = ?", (pid,)
        ).fetchone()
        if not project:
            db.close()
            return [], 0

        ds_id = project["dataset_id"]
        ds = DatasetService._load_ds(ds_id)
        from services.project_dataset import ProjectDatasetService

        meta = ProjectDatasetService.get_meta(pid)
        if meta is not None:
            num_rows = ProjectDatasetService.num_rows(pid)

            def serve(idx):
                return ProjectDatasetService.get_row(pid, idx)

        else:
            num_rows = len(ds)

            def serve(idx):
                return DatasetService.get_row(ds_id, idx)

        total_rows = num_rows

        # ---- FILTER PIPELINE ----
        current = _resolve_matching_indices(pid, user_id, filter_exprs)

        # ---- PAGINATION ----
        current.sort()
        total = len(current)
        start = (page - 1) * per_page
        page_indices = current[start : start + per_page]

        # ---- BUILD RESPONSE ----
        annotated_by_me = {
            r[0]
            for r in db.execute(
                "SELECT row_index FROM fyndnote_annotations WHERE project_id = ? AND user_id = ?",
                (pid, user_id),
            ).fetchall()
        }
        all_annotations = db.execute(
            "SELECT row_index, user_id FROM fyndnote_annotations WHERE project_id = ?",
            (pid,),
        ).fetchall()
        any_annotated: dict[int, set[str]] = {}
        for r in all_annotations:
            any_annotated.setdefault(r["row_index"], set()).add(r["user_id"])

        # Fetch annotation data for page rows
        annotation_data_by_row: dict[int, list[dict]] = {}
        if page_indices:
            placeholders = ",".join("?" * len(page_indices))
            ann_rows = db.execute(
                f"""
                SELECT row_index, user_id, data, created_at, updated_at FROM fyndnote_annotations
                WHERE project_id = ? AND row_index IN ({placeholders})
            """,
                [pid] + page_indices,
            ).fetchall()
            for ar in ann_rows:
                annotation_data_by_row.setdefault(ar["row_index"], []).append(
                    {
                        "author_id": ar["user_id"],
                        "data": json.loads(ar["data"]),
                        "created_at": ar["created_at"],
                        "updated_at": ar["updated_at"],
                    }
                )
        db.close()

        rows_data = []
        for idx in page_indices:
            row = serve(idx)
            # Merge annotation data into preview so cards show annotation fields
            annotated = annotation_data_by_row.get(idx, [])
            if annotated:
                for ann in annotated:
                    for key, val in ann["data"].items():
                        row[key] = val
            entry = {
                "index": idx,
                "preview": row,
                "annotations": annotated,
                "annotation_status": {
                    "by_me": idx in annotated_by_me,
                    "by_any": idx in any_annotated,
                    "annotators": list(any_annotated.get(idx, [])),
                },
            }
            rows_data.append(entry)

        return rows_data, total

    @staticmethod
    def extract_annotation_fields(template_source: str | None) -> list[str]:
        if not template_source:
            return []
        names = re.findall(
            r"<(?:SelectField|TextField|CheckboxGroup|RatingField|NERField|BBoxField)"
            r'\s[^>]*?name="([^"]+)"',
            template_source,
        )
        return names

    @staticmethod
    def export_annotations(pid: str, format: str = "parquet"):
        if format != "parquet":
            raise ValueError(f"Unsupported export format: {format}")
        db = get_db()
        rows = db.execute(
            "SELECT row_index, user_id, data, created_at, updated_at FROM fyndnote_annotations WHERE project_id = ?",
            (pid,),
        ).fetchall()
        db.close()
        import pyarrow.parquet as pq

        table = pa.Table.from_pylist(
            [
                {
                    "row_index": r["row_index"],
                    "user_id": r["user_id"],
                    "data": r["data"].encode(),
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"],
                }
                for r in rows
            ]
        )
        buf = pa.BufferOutputStream()
        pq.write_table(table, buf)
        return buf.getvalue().to_pybytes()
