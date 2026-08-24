# Export

Annotations can be exported from a project as a **Parquet** file.

## Endpoint

`GET /projects/{pid}/annotations/export?format=parquet`

The response is a Parquet file (`application/octet-stream`) with a `Content-Disposition` attachment filename like `annotations.parquet`.

## What's included

Each row of the export contains:

- `row_index` — the row's index in the dataset.
- `user_id` — the annotating user.
- `data` — the annotation JSON (bytes).
- `created_at` / `updated_at` — timestamps.

## Notes

- Only **parquet** is currently supported.
- AI prefill annotations are not part of this export (they live in the separate AI store).
