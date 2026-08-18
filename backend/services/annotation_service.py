import uuid
import hashlib
import random
import json
import re
from datetime import datetime, timedelta
from database import get_db
import pyarrow.compute as pc
import pyarrow as pa
from services.dataset_service import DatasetService


def _apply_row_index_filter(indices: list[int], expr) -> list[int]:
    val = int(expr.value)
    match expr.operator:
        case "=":   return [i for i in indices if i == val]
        case "!=":  return [i for i in indices if i != val]
        case ">":   return [i for i in indices if i > val]
        case ">=":  return [i for i in indices if i >= val]
        case "<":   return [i for i in indices if i < val]
        case "<=":  return [i for i in indices if i <= val]
        case _:     return indices


def _apply_annotation_meta_filter(db, project_indices: list[int], expr, user_id: str, pid: str) -> list[int]:
    if not project_indices:
        return []

    if expr.field == "annotations.count":
        op = expr.operator
        val = int(expr.value)
        placeholders = ",".join("?" * len(project_indices))
        # For = 0, < 1, <= 0: find rows NOT in annotations table
        if (op == "=" and val == 0) or (op == "<" and val == 1) or (op == "<=" and val == 0):
            sql_annotated = f"""
                SELECT DISTINCT row_index FROM annotations
                WHERE project_id = ? AND row_index IN ({placeholders})
            """
            annotated = {r[0] for r in db.execute(sql_annotated, [pid] + project_indices).fetchall()}
            return [i for i in project_indices if i not in annotated]
        # For > 0, >= 1: find rows IN annotations with the given count condition
        sql = f"""
            SELECT row_index FROM annotations
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
            SELECT DISTINCT row_index FROM annotations
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
            SELECT DISTINCT row_index FROM annotations
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
        now = datetime.utcnow()
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


def _apply_annotation_data_filter(db, project_indices: list[int], expr, pid: str) -> list[int]:
    if not project_indices or not expr.field.startswith("annotation."):
        return project_indices
    field_name = expr.field[len("annotation."):]
    json_path = f"$.{field_name}"
    op = expr.operator
    val = expr.value
    placeholders = ",".join("?" * len(project_indices))

    if op == "~=":
        sql = f"""
            SELECT DISTINCT row_index FROM annotations
            WHERE project_id = ?
              AND row_index IN ({placeholders})
              AND json_extract(data, ?) LIKE ?
        """
        params = [pid] + project_indices + [json_path, f"%{val}%"]
    elif op == "=":
        sql = f"""
            SELECT DISTINCT row_index FROM annotations
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
            SELECT DISTINCT row_index FROM annotations
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
            SELECT DISTINCT row_index FROM annotations
            WHERE project_id = ?
              AND row_index IN ({placeholders})
              AND CAST(json_extract(data, ?) AS REAL) {op} ?
        """
        params = [pid] + project_indices + [json_path, float(val)]
    else:
        return project_indices

    matched = {r[0] for r in db.execute(sql, params).fetchall()}
    return [i for i in project_indices if i in matched]


def _apply_data_field_filter(indices: list[int], expr, ds) -> list[int]:
    if not indices or not expr.field.startswith("data."):
        return indices
    field_name = expr.field[len("data."):]
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
            if op == ">":  return py_val > num
            if op == ">=": return py_val >= num
            if op == "<":  return py_val < num
            if op == "<=": return py_val <= num
    except (ValueError, TypeError):
        return False
    return False


class AnnotationService:
    @staticmethod
    def create_project(name: str, dataset_id: str, template_id: str, color: str = '#1976d2', tags: str = '', instructions: str = '',
                       ml_enabled: bool = False, ml_url: str = '', ml_annotator: str = '', ml_mode: str = 'on_navigate') -> dict:
        db = get_db()
        pid = str(uuid.uuid4())
        salt = hashlib.sha256(f"{pid}:{name}".encode()).hexdigest()[:16]
        db.execute(
            "INSERT INTO projects (id, name, dataset_id, template_id, salt, color, tags, instructions, ml_enabled, ml_url, ml_annotator, ml_mode) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (pid, name, dataset_id, template_id, salt, color, tags, instructions, int(ml_enabled), ml_url, ml_annotator, ml_mode)
        )
        db.commit()
        proj = db.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        db.close()
        return dict(proj)

    @staticmethod
    def update_project(pid: str, name: str, color: str = None, tags: str = None, instructions: str = None,
                       ml_enabled: bool = None, ml_url: str = None, ml_annotator: str = None, ml_mode: str = None) -> dict | None:
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
    def get_row_annotation_status(pid: str, row_index: int, user_id: str) -> dict:
        db = get_db()
        rows = db.execute(
            "SELECT user_id FROM annotations WHERE project_id = ? AND row_index = ?",
            (pid, row_index)
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
        row = DatasetService.get_row(ds_id, row_index)
        status = AnnotationService.get_row_annotation_status(pid, row_index, user_id)
        return {"index": row_index, "row": row, "annotation_status": status}

    @staticmethod
    def navigate_row(pid: str, user_id: str, current_index: int, direction: int) -> dict | None:
        project = AnnotationService.get_project(pid)
        if not project:
            return None
        ds_id = project["dataset_id"]
        db = get_db()
        salt = db.execute("SELECT salt FROM projects WHERE id = ?", (pid,)).fetchone()
        db.close()
        if not salt:
            return None
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
        row = DatasetService.get_row(ds_id, new_idx)
        status = AnnotationService.get_row_annotation_status(pid, new_idx, user_id)
        return {"index": new_idx, "row": row, "annotation_status": status}

    @staticmethod
    def browse_rows(pid: str, user_id: str, page: int, per_page: int, filter_exprs: list) -> tuple:
        db = get_db()
        project = db.execute("SELECT dataset_id FROM projects WHERE id = ?", (pid,)).fetchone()
        if not project:
            db.close()
            return [], 0

        ds_id = project["dataset_id"]
        ds = DatasetService._load_ds(ds_id)
        total_rows = len(ds)
        all_indices = list(range(total_rows))

        # ---- FILTER PIPELINE ----
        current = all_indices[:]

        # 1. Row index filters (computational, cheapest)
        row_index_exprs = [fe for fe in filter_exprs if fe.field == "row_index"]
        for expr in row_index_exprs:
            current = _apply_row_index_filter(current, expr)

        # 2. Annotation metadata filters (SQL — annotations.count, annotations.annotated_by)
        meta_exprs = [fe for fe in filter_exprs if fe.field.startswith("annotations.") and fe.field != "annotations."]
        for expr in meta_exprs:
            current = _apply_annotation_meta_filter(db, current, expr, user_id, pid)

        # 3. Annotation data filters (SQL — json_extract on annotation.*)
        ann_exprs = [fe for fe in filter_exprs if fe.field.startswith("annotation.") and fe.field != "annotation."]
        for expr in ann_exprs:
            current = _apply_annotation_data_filter(db, current, expr, pid)

        # 4. Data field filters (Arrow — data.*)
        data_exprs = [fe for fe in filter_exprs if fe.field.startswith("data.") and fe.field != "data."]
        for expr in data_exprs:
            current = _apply_data_field_filter(current, expr, ds)

        # ---- PAGINATION ----
        current.sort()
        total = len(current)
        start = (page - 1) * per_page
        page_indices = current[start:start + per_page]

        # ---- BUILD RESPONSE ----
        annotated_by_me = {
            r[0] for r in db.execute(
                "SELECT row_index FROM annotations WHERE project_id = ? AND user_id = ?",
                (pid, user_id)
            ).fetchall()
        }
        all_annotations = db.execute(
            "SELECT row_index, user_id FROM annotations WHERE project_id = ?",
            (pid,)
        ).fetchall()
        any_annotated: dict[int, set[str]] = {}
        for r in all_annotations:
            any_annotated.setdefault(r["row_index"], set()).add(r["user_id"])

        # Fetch annotation data for page rows
        annotation_data_by_row: dict[int, list[dict]] = {}
        if page_indices:
            placeholders = ",".join("?" * len(page_indices))
            ann_rows = db.execute(f"""
                SELECT row_index, user_id, data, created_at, updated_at FROM annotations
                WHERE project_id = ? AND row_index IN ({placeholders})
            """, [pid] + page_indices).fetchall()
            for ar in ann_rows:
                annotation_data_by_row.setdefault(ar["row_index"], []).append({
                    "author_id": ar["user_id"],
                    "data": json.loads(ar["data"]),
                    "created_at": ar["created_at"],
                    "updated_at": ar["updated_at"],
                })
        db.close()

        rows_data = []
        for idx in page_indices:
            row = DatasetService.get_row(ds_id, idx)
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
            r'<(?:SelectField|TextField|CheckboxGroup|RatingField|NERField|BBoxField)'
            r'\s[^>]*?name="([^"]+)"',
            template_source
        )
        return names

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
