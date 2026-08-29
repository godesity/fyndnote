# Dynamic Datasets (add-only rows + annotation removal)

**Date:** 2026-08-25
**Status:** Draft

## Overview

The frontend needs to (a) **add rows/tasks** to a project's dataset and (b) **remove
annotations and ML predictions** for existing rows. Rows themselves are **append-only** —
existing rows are never deleted, edited, or reordered. This is the key simplification:
there is no tombstone/compaction machinery because nothing is ever removed from the
data.

## Canonical split

1. **Row data** lives in **append-only Parquet fragment files** on disk, one folder per
   project, unique per project once modified.
2. **Annotations / ML predictions** live in **SQLite/PostgreSQL** and are deleted with
   plain `DELETE` statements. Nothing in the DB tracks row existence beyond a row count.

Because rows are only ever appended, their **positional `row_index` is stable** (no row is
ever removed, so no index shifts). Annotations and ML predictions keep referencing
`row_index` — no `row_id` migration is needed.

## Storage layout

```
data/datasets/{project_id}/
  fragments/
    frag_{N}.parquet      # immutable append-only row data, schema in the file
  media/                   # image/audio files, referenced by path columns
```

The logical dataset for a project is the **concatenation of all fragments in order**.
`num_rows` and the next fragment number are tracked so appends know where to start and
reads know how many rows exist without scanning every file.

## Database schema

### `fyndnot_datasets` (unchanged)

Source dataset seed metadata (`source`, `num_rows`, `columns`, ...). A project's *own*
dataset is tracked separately once it is modified.

### `dataset_meta` (new) — per-project dataset metadata

```sql
CREATE TABLE dataset_meta (
    project_id   TEXT PRIMARY KEY,
    num_rows     INTEGER NOT NULL DEFAULT 0, -- logical row count (append-only, only grows)
    next_fragment INTEGER NOT NULL DEFAULT 0,
    schema       TEXT,                        -- serialized Arrow schema
    created_at   TEXT NOT NULL
);
```

Named `dataset_meta` (not a `deleted` tombstone table) so future metadata can be added as
columns without a structural change. There is **no deleted/tombstone state** — rows are
never removed.

### `fyndnot_annotations` / `fyndnot_ml_annotations` (unchanged)

Existing tables keyed by `(project_id, row_index, user_id)` / `(project_id, row_index)`.
Deletion is a plain `DELETE`. No cascade needed (no row deletion).

## Operations

### Add rows (import)

1. Read incoming data (Parquet / CSV / JSON / JSONL) into an Arrow `Table`.
2. Assign row indices starting at current `num_rows` (append order preserved).
3. Write the batch to `frag_{next_fragment}.parquet`.
4. Materialize image/audio columns to `media/` and rewrite those columns to path strings.
5. Update `dataset_meta`: bump `num_rows`, `next_fragment`, and record/verify the schema.

Appends are atomic per batch (write fragment file, then update `dataset_meta`). Because
rows are never removed, appends never invalidate existing `row_index` references.

### Read / browse

- `pyarrow.parquet.ParquetDataset` over `fragments/*.parquet` with memory mapping — lazy,
  columnar; labeling pages rows via row ranges and reads only needed columns.
- `data.*` filter expressions apply pyarrow compute over fragments (pattern already in
  `annotation_service.py:247`).
- `num_rows` comes from `dataset_meta` (no per-read scan).

### Remove annotations / ML predictions

Plain SQLite/PostgreSQL `DELETE` keyed by `project_id` (+ `row_index` / `user_id` for
annotations). Since rows are never deleted, there is no requirement to cascade or
re-index anything.

## API surface

```
POST   /api/v1/projects/{pid}/rows/bulk      # add/import rows (parquet/csv/json/jsonl)
DELETE /api/v1/projects/{pid}/annotations/{row_index}          # remove one annotation
DELETE /api/v1/projects/{pid}/annotations                     # remove all annotations
DELETE /api/v1/projects/{pid}/ml-annotations/{row_index}      # remove ML prediction(s)
DELETE /api/v1/projects/{pid}/ml-annotations                  # remove all ML predictions
```

No row-deletion endpoint exists. Rows are add-only.

## Migration

- Existing projects keep their current dataset; when a project is first modified, a
  `dataset_meta` row is created (seed `num_rows` from the source dataset, `next_fragment=0`).
- No `row_id` migration — annotations/ML keep `row_index` keying (stable because rows are
  never removed).

## Efficiency notes

- No tombstone/compaction/cascade machinery — nothing is ever removed from the data.
- `num_rows` + `next_fragment` tracked in `dataset_meta` avoid scans for metadata/append.
- Optional `POST .../compact` (merge small fragments) is a pure optimization; it preserves
  order and `row_index`, so it never affects annotation references.
