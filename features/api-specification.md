# API Specification

**Date:** 2026-08-13
**Status:** Draft

## Base URL

All endpoints are prefixed with `/api/v1`.

## Authentication

### Login

```
POST /api/v1/auth/login
```

Validates the user ID against the `users` table in SQLite. Unknown IDs
are rejected.

```json
// Request
{ "user_id": "alice" }

// Response (200 OK)
{
  "user_id": "alice",
  "name": "Alice",
  "global_role": "system_admin",
  "project_roles": null
}

// Response (200 OK, non-admin)
{
  "user_id": "bob",
  "name": "Bob",
  "global_role": "annotator",
  "project_roles": {
    "proj-1": "project_admin",
    "proj-2": "annotator"
  }
}

// Response (401 Unauthorized)
{ "error": "unknown_user", "message": "User ID not found" }
```

The frontend stores the returned user info for the session. All subsequent
requests include the `user_id` as a query parameter or header.

## Datasets

### List datasets

```
GET /api/v1/datasets
```

Returns datasets loaded in the backend.

```json
{
  "datasets": [
    {
      "id": "ds-uuid",
      "name": "imdb-sentiment",
      "source": "imdb",
      "num_rows": 50000,
      "columns": [
        { "name": "text", "type": "string" },
        { "name": "events", "type": "object" },
        { "name": "label", "type": "int64" }
      ],
      "created_at": "2026-08-13T00:00:00Z"
    }
  ]
}
```

### Load a dataset

```
POST /api/v1/datasets/load
```

```json
{
  "source": "imdb",
  "split": "train",
  "name": null
}
```

Supports any source HF `datasets` supports: Hugging Face hub ID, local path,
CSV/JSONL/Parquet file path, etc.

### Get dataset row

```
GET /api/v1/datasets/:id/rows/:index
```

Binary columns (Image, Audio) are replaced with serving URLs in the response.
Object columns are returned as-is (nested JSON).

```json
{
  "index": 42,
  "row": {
    "text": "This movie was fantastic!",
    "events": [
      {"type": "click", "timestamp": 1.2, "target": "play"},
      {"type": "pause", "timestamp": 15.0, "target": "pause"}
    ],
    "label": 1,
    "image": "/api/v1/datasets/ds-uuid/rows/42/columns/image",
    "audio": "/api/v1/datasets/ds-uuid/rows/42/columns/audio"
  }
}
```

### Get binary column content

```
GET /api/v1/datasets/:id/rows/:index/columns/:column_name
```

Returns raw binary content for Image, Audio, or other non-text columns.
Content-Type is set appropriately (image/jpeg, audio/wav, etc.).

## Templates

### List templates

```
GET /api/v1/templates
```

### Get template

```
GET /api/v1/templates/:id
```

```json
{
  "id": "template-uuid",
  "name": "sentiment-v1",
  "source": "function TextClassification({ row }) { ... }",
  "project_id": "proj-uuid",
  "validated": true,
  "created_at": "2026-08-13T00:00:00Z",
  "updated_at": "2026-08-13T00:00:00Z"
}
```

### Create template

```
POST /api/v1/templates
```

```json
{
  "name": "sentiment-v1",
  "source": "function TextClassification({ row }) { ... }",
  "validated": false
}
```

### Update template

```
PUT /api/v1/templates/:id
```

```json
{
  "source": "function TextClassification({ row }) { ... updated ... }"
}
```

## Projects

### List projects

```
GET /api/v1/projects?user_id=alice
```

For `system_admin`, returns all projects. For other users, only projects where
the user has a `project_roles` entry. Returns the user's role for each project.

### Create project

```
POST /api/v1/projects
```

```json
{
  "name": "IMDB Sentiment Labeling",
  "dataset_id": "ds-uuid",
  "template_id": "template-uuid"
}
```

### Get project details

```
GET /api/v1/projects/:id
```

```json
{
  "id": "proj-uuid",
  "name": "IMDB Sentiment Labeling",
  "dataset_id": "ds-uuid",
  "template_id": "template-uuid",
  "template_source": "function TextClassification(...) { ... }",
  "num_rows": 50000,
  "progress": {
    "total": 50000,
    "annotated_by_me": 142,
    "any_annotation": 3800
  }
}
```

### Browse rows

```
GET /api/v1/projects/:id/rows?page=1&per_page=50&status=all&user_id=user-1&include_annotations=1
```

Status options: `all`, `annotated_by_me`, `annotated_by_any`, `unannotated`

`annotation_status` is always present. `annotations` is only included when
`include_annotations=1` — otherwise it's `null`.

```json
{
  "rows": [
    {
      "index": 42,
      "preview": { "text": "This movie was..." },
      "annotations": [
        {"author_id": "user-1", "created_at": "2026-08-13T00:00:00Z" , "data": {"sentiment": "negative"}}
      ],
      "annotation_status": {
        "by_me": true,
        "by_any": true,
        "annotators": ["user-1"]
      }
    }
  ],
  "total": 50000,
  "page": 1,
  "per_page": 50
}
```

### Get next row to label

```
GET /api/v1/projects/:id/next-row?user_id=user-1
```

Returns the first unlabeled row in the user's deterministic ordering.

```json
{
  "index": 8733,
  "row": {
    "text": "A masterpiece of cinema",
    "label": 1
  }
}
```

### Submit annotation

```
POST /api/v1/projects/:id/annotate
```

```json
{
  "row_index": 8733,
  "user_id": "user-1",
  "data": {
    "sentiment": "positive"
  }
}
```

The `data` field accepts arbitrary JSON — flat values, lists, or nested objects:

```json
{
  "row_index": 42,
  "user_id": "moderator-1",
  "data": {
    "verdict": "rejected",
    "flags": ["spam", "misinformation"],
    "notes": "Clear spam with false claims"
  }
}
```

Returns `201 Created`.

### Get annotation for a row

```
GET /api/v1/projects/:id/annotations/:row_index?user_id=user-1
```

```json
{
  "row_index": 8733,
  "user_id": "user-1",
  "data": { "sentiment": "positive" },
  "created_at": "2026-08-13T00:00:00Z"
}
```

The `data` field supports arbitrary nesting (lists, objects, or flat values).

### Get all annotations (export)

```
GET /api/v1/projects/:id/annotations/export?format=parquet
```

Returns the full annotation file. Supported formats: `parquet`, `jsonl`.

## Row Ordering

The deterministic row order for a user is computed as:

```python
import hashlib

def row_order(user_id: str, project_salt: str, num_rows: int) -> list[int]:
    indices = list(range(num_rows))
    seed = hashlib.sha256(f"{user_id}:{project_salt}".encode()).hexdigest()
    rng = random.Random(seed)
    rng.shuffle(indices)
    return indices
```

The `project_salt` is generated at project creation time and stored alongside it.
