# ML Backend Auto-Prefill

## Goal
Add a project-level ML backend setting that automatically prefill-annotates data rows by calling an external ML model API. Two modes: auto-prefill on row navigation, and batch prefill on the entire dataset.

## Settings (per project)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ml_enabled` | bool | false | Master toggle |
| `ml_url` | str | "" | ML backend HTTP(S) URL |
| `ml_annotator` | str | "" | Model name stored as annotator (e.g. "gpt-4o") |
| `ml_mode` | str | "on_navigate" | One of: "on_navigate", "batch", "both" |

Stored as new columns on the `projects` table (migration).

## API Contract with ML Backend

- **Request:** `POST <ml_url>` with JSON body `{"data": { ... }}` (full data row)
- **Response:** `{"annotation": { ... }}` matching the template annotation schema
- **Timeout:** 15s constant; on failure/error the prefill is silently skipped

## Database

### New table: `ml_annotations`

```sql
CREATE TABLE IF NOT EXISTS ml_annotations (
    project_id  TEXT NOT NULL REFERENCES projects(id),
    row_index   INTEGER NOT NULL,
    annotator   TEXT NOT NULL,
    data        TEXT NOT NULL,       -- JSON string of the annotation
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, row_index)
);
```

One AI annotation per row per project. Separate from human `annotations` table so AI annotations don't affect human annotation progress counts.

### Migration: New columns on `projects`

```sql
ALTER TABLE projects ADD COLUMN ml_enabled INTEGER DEFAULT 0;
ALTER TABLE projects ADD COLUMN ml_url TEXT DEFAULT '';
ALTER TABLE projects ADD COLUMN ml_annotator TEXT DEFAULT '';
ALTER TABLE projects ADD COLUMN ml_mode TEXT DEFAULT 'on_navigate';
```

## Backend API

| Method | Path | Description |
|--------|------|-------------|
| POST | `/projects/{pid}/ml-prefill` | Prefill one row — calls ML backend, stores result |
| POST | `/projects/{pid}/ml-batch` | Batch prefill all rows without ML annotations |
| GET | `/projects/{pid}/ml-annotations/{row_index}` | Get cached ML annotation for a row |

### POST /ml-prefill

**Request body:** `{ "row_index": int }`

**Flow:**
1. Check `ml_annotations` for existing cached annotation — return it if found
2. Load row data from dataset
3. POST `{"data": row_data}` to `ml_url` with 15s timeout
4. Parse `{"annotation": {...}}` from response
5. Upsert into `ml_annotations` table
6. Return `{ "row_index": int, "annotation": {...}, "annotator": str }`

**Error handling:** If ML backend is unreachable, times out, or returns invalid JSON, return `{ "row_index": int, "annotation": null }` (HTTP 200 with null annotation). No exceptions thrown.

### POST /ml-batch

**Request body:** `{ "row_indices": [int] | null }` — if null, iterate all dataset rows.

**Flow:**
1. Determine target rows (all rows in dataset, or the provided subset)
2. For each row without an existing ML annotation (sequential, not parallel):
   - Call ML backend (same contract as ml-prefill) with 15s timeout per row
   - Store result on success; count as failed on any error
3. Return `{ "total": int, "succeeded": int, "failed": int }`

### GET /ml-annotations/{row_index}

Returns cached ML annotation if it exists, else 404.

### Project detail (GET /projects/{pid})

Include the 4 ML settings fields in the response (they were already part of the project row after migration).

## Frontend

### SetupView — ML Backend section

New collapsible section after "Create Project" step:

- **Enable ML Backend** toggle switch
- **ML Backend URL** text input (shown when enabled)
- **Annotator Name** text input (e.g. "gpt-4o")
- **Mode** radio group: "Auto-prefill on navigate", "Batch only", "Both"

On project creation, these fields are sent alongside the existing project payload.

### LabelView — Auto-prefill on navigate

Only fires when `ml_enabled=true` and `ml_mode` is `"on_navigate"` or `"both"`.

When a row loads:
1. Load row immediately (don't block)
2. Fire `POST /projects/{pid}/ml-prefill` with `{ row_index }`
3. Show a small pulsing dot/spinner on the submit button area while loading
4. On success, populate annotation form fields with the AI result
5. On failure/timeout, leave form empty (silent)

### BrowseView — Batch prefill button

A **"AI Prefill"** button in the toolbar. Visible only when `ml_enabled=true` and `ml_mode` is `"batch"` or `"both"`.

On click:
1. Calls `POST /projects/{pid}/ml-batch`
2. Shows a result banner: "Prefilled X/Y rows (Z failed)"
3. Refreshes the row listing

## Annotations table comparison

| | `annotations` (human) | `ml_annotations` (AI) |
|---|---|---|
| PK | `(project_id, row_index, user_id)` | `(project_id, row_index)` |
| Identity | `user_id` FK → `users` | `annotator` text (model name) |
| Multiple per row | Yes (different users) | No (one AI annotation) |
| Affects progress | Yes | No |
