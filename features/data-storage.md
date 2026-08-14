# Data Storage

**Date:** 2026-08-13
**Status:** Approved

## Storage Backend

Two storage strategies: **SQLite** for relational data and **files** for
datasets and templates.

```
data/
  labeling.db             # SQLite: users, projects, annotations
  datasets/
    {dataset_id}/
      meta.json          # dataset metadata + source info
      cache/              # HF datasets cache (optional)
  templates/
    {template_id}.json   # template source + metadata
```

## SQLite Schema

### `users`

```sql
CREATE TABLE users (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    global_role TEXT NOT NULL CHECK(global_role IN ('system_admin', 'annotator')),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `project_permissions`

```sql
CREATE TABLE project_permissions (
    user_id    TEXT NOT NULL REFERENCES users(id),
    project_id TEXT NOT NULL REFERENCES projects(id),
    role       TEXT NOT NULL CHECK(role IN ('project_admin', 'annotator')),
    PRIMARY KEY (user_id, project_id)
);
```

### `projects`

```sql
CREATE TABLE projects (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    dataset_id  TEXT NOT NULL,
    template_id TEXT NOT NULL,
    salt        TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### `annotations`

```sql
CREATE TABLE annotations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL REFERENCES projects(id),
    row_index   INTEGER NOT NULL,
    user_id     TEXT NOT NULL REFERENCES users(id),
    data        TEXT NOT NULL,       -- JSON-serialized annotation payload
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, row_index, user_id)
);
```

The `data` column stores arbitrary JSON — flat values, lists, or nested
objects. The schema does not constrain the structure.

## Common Queries

### Next unlabeled row for a user

```python
import sqlite3, hashlib, random

def next_row(db: sqlite3.Connection, project_id: str, user_id: str, num_rows: int) -> int | None:
    salt = db.execute("SELECT salt FROM projects WHERE id = ?", (project_id,)).fetchone()[0]

    # Deterministic shuffle
    indices = list(range(num_rows))
    seed = hashlib.sha256(f"{user_id}:{salt}".encode()).hexdigest()
    rng = random.Random(seed)
    rng.shuffle(indices)

    # Find annotated rows for this user
    annotated = {
        r[0] for r in db.execute(
            "SELECT row_index FROM annotations WHERE project_id = ? AND user_id = ?",
            (project_id, user_id)
        ).fetchall()
    }

    for idx in indices:
        if idx not in annotated:
            return idx
    return None
```

### Project progress

```sql
SELECT
    (SELECT COUNT(DISTINCT row_index) FROM annotations WHERE project_id = ?) AS any_annotation,
    (SELECT COUNT(DISTINCT row_index) FROM annotations WHERE project_id = ? AND user_id = ?) AS annotated_by_me,
    (SELECT COUNT(*) FROM annotations WHERE project_id = ?) AS total_annotations;
```

### List projects accessible to a user

```sql
SELECT p.*, pp.role
FROM projects p
JOIN project_permissions pp ON pp.project_id = p.id
WHERE pp.user_id = ?;
```

For `system_admin`, all projects are returned (no permission check).

## Dataset Storage

Datasets are loaded via HF `datasets` and are **read-only**. The original data is
never modified. Metadata is cached in `data/datasets/{id}/meta.json`.

```json
{
  "id": "ds-uuid",
  "source": "imdb",
  "name": null,
  "split": "train",
  "num_rows": 50000,
  "columns": [
    {"name": "text", "type": "Value('string')"},
    {"name": "label", "type": "ClassLabel(names=['neg','pos'])"}
  ],
  "created_at": "2026-08-13T00:00:00Z"
}
```

## Template Storage

Templates are stored as individual JSON files:

```json
{
  "id": "template-uuid",
  "name": "sentiment-v1",
  "source": "function TextClassification({ row, annotations }) { ... }",
  "project_id": "proj-uuid",
  "validated": true,
  "created_at": "2026-08-13T00:00:00Z",
  "updated_at": "2026-08-13T00:00:00Z"
}
```

The `validated` flag is set by the frontend when `LiveError` reports no errors
during editing. It is informational — the backend does not enforce it.

## Annotation Export

For ML pipeline consumption, annotations can be exported to Parquet via the
export API endpoint. The exported Parquet file mirrors the `annotations` table
schema, with `data` stored as binary JSON:

```python
import pyarrow as pa
import pyarrow.parquet as pq

rows = db.execute("""
    SELECT row_index, user_id, data, created_at, updated_at
    FROM annotations
    WHERE project_id = ?
""", (project_id,)).fetchall()

table = pa.Table.from_pylist([
    {
        "row_index": r[0],
        "user_id": r[1],
        "data": r[2].encode(),
        "created_at": r[3],
        "updated_at": r[4],
    }
    for r in rows
])
pq.write_table(table, "export.parquet")
```

## Seed Data

A `data/users.json` seed file can be used to bootstrap the database on first
start. The backend reads it once and inserts users into SQLite. After seeding,
the JSON file is ignored — SQLite is the source of truth.

```json
{
  "users": [
    { "id": "alice", "name": "Alice", "global_role": "system_admin" },
    { "id": "bob",   "name": "Bob",   "global_role": "annotator", "project_roles": { "proj-1": "project_admin", "proj-2": "annotator" } },
    { "id": "carol", "name": "Carol", "global_role": "annotator", "project_roles": { "proj-1": "annotator" } }
  ]
}
```
