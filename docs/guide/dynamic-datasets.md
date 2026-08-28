# Dynamic Datasets — Import Rows & Remove Annotations / Predictions

Projects can grow their dataset at runtime and clean up collected labels, without
rebuilding the source dataset. Two capabilities:

1. **Import rows** — append new rows to a project's own dataset.
2. **Remove annotations / ML predictions** — delete saved labels or model predictions.

## Storage model

Row data is **append-only**. A project's dataset is the concatenation of:

- the original **source dataset** (HuggingFace / HTTP / file), and
- any rows **imported** at runtime, stored as immutable **Parquet fragments** on disk:

```
data/datasets/projects/{project_id}/
  fragments/
    frag_0.parquet      # one file per import batch, in append order
```

A `dataset_meta` row tracks `num_rows` (source + imported) and the next fragment
number. Because rows are only ever appended, their positional `row_index` is stable —
importing never invalidates existing annotation references.

Annotations and ML predictions stay in SQLite/PostgreSQL and are removed with plain
`DELETE` statements. Nothing in the DB tracks row existence beyond a row count, so
there is no tombstone/compaction machinery.

> **Known gap:** image/audio columns in imported rows are not yet materialized to the
> `media/` directory. v1 stores only JSON-serializable scalar/text columns.

## API

### Import rows

```
POST /api/v1/projects/{pid}/rows/bulk
```

Body: `{ "rows": [ { ... }, { ... } ] }` — a JSON array of row objects.

- All rows must share the same columns (else `422`).
- Appends are atomic per batch: write the fragment, then bump `num_rows`/`next_fragment`.
- Returns `{ "status": "ok", "imported": <count> }`.

### Remove annotations

```
DELETE /api/v1/projects/{pid}/annotations/{row_index}?user_id=<user>  # one user's annotation for a row
DELETE /api/v1/projects/{pid}/annotations/{row_index}                # all annotations for a row
DELETE /api/v1/projects/{pid}/annotations                            # all annotations for the project
```

Each returns `{ "status": "deleted", "rows": <deleted-count> }`. Unknown projects → `404`.

### Remove ML predictions

```
DELETE /api/v1/projects/{pid}/ml-annotations/{row_index}   # predictions for one row
DELETE /api/v1/projects/{pid}/ml-annotations               # all predictions for the project
```

## Frontend

- **Import Rows** panel (Edit Project view): paste a JSON array of row objects and
  import; shows the imported count on success.
- **Clear annotation / Clear prediction** buttons in the row-detail panel (Browse
  view): remove the current user's annotation or the ML prediction for a row, then
  refreshes the panel.
