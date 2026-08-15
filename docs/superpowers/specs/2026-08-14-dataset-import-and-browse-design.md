# Dataset Import & Browse View — Design Spec

## Goals

1. **Unified dataset import** — single input field that accepts HuggingFace dataset IDs, HTTP URLs to raw files, `file://` paths, and browser file uploads.
2. **Format support** — CSV, JSON, JSONL, Parquet (beyond existing HuggingFace-only).
3. **Error messages** — clear explanation when format is unsupported or source is invalid.
4. **Browse view** — implement the stubbed `browse_rows` so users can browse all rows in a project with pagination and status filtering.

---

## 1. Source Type Detection

A single text input on the frontend. The backend inspects the value on `POST /api/v1/datasets/load`:

| Pattern | `source_type` | Example |
|---|---|---|
| `http://*` or `https://*` | `http` | `https://example.com/data.csv` |
| `file://*` | `file` | `file:///home/user/data.parquet` |
| `*/*` (contains `/`, not a URL scheme) | `huggingface` | `stanfordnlp/imdb` |
| anything else | `huggingface` (pass-through to HF `load_dataset`) | — |

**Error flow:** If the resolved source is not a supported format, return `400` with `{"detail": "Unsupported format: .xlsx. Supported: .csv, .json, .jsonl, .parquet"}`.

---

## 2. Dataset Loading

### HuggingFace (`source_type=huggingface`)

Same as current implementation — calls `datasets.load_dataset(source, name, split=split)`.

### HTTP (`source_type=http`)

1. Determine format from URL extension + `Content-Type` header fallback.
2. Download the file to a local cache directory (`data/datasets/cache/`).
3. Load into a HuggingFace `Dataset` using the format-specific reader:
   - `.csv` → `load_dataset("csv", data_files=path)`
   - `.json` / `.jsonl` → `load_dataset("json", data_files=path)`
   - `.parquet` → `load_dataset("parquet", data_files=path)`

### File (`source_type=file`)

Same as HTTP, but read directly from the local path instead of downloading.

### Browser Upload

Separate multipart upload endpoint (`POST /api/v1/datasets/upload`). The file is saved to `data/datasets/uploads/`, then loaded the same way as `file://`. The meta.json stores the original filename as `source`.

---

## 3. Meta Storage

Add a `source_type` field to `meta.json` so `_load_ds` knows how to rehydrate:

```json
{
  "id": "uuid",
  "source": "https://example.com/data.csv",
  "source_type": "http",
  "source_format": "csv",
  "name": null,
  "split": null,
  "num_rows": 1000,
  "columns": [...],
  "original_file": "data/datasets/cache/abc123.csv",
  "created_at": "..."
}
```

The `_load_ds` method reads `meta["source_type"]` and uses the appropriate loader path.

---

## 4. Frontend: Load Dialog

In `SetupView.tsx`, replace the dead "Load New" button stub with:

- A text input for typed sources (HF ID, HTTP URL, `file://` path)
- A file upload button (opens native file picker, sends multipart to `/api/v1/datasets/upload`)
- Loading state + error message display below the input
- On success, refresh the dataset dropdown

---

## 5. Browse View Fix

`AnnotationService.browse_rows()` is currently stubbed (`return [], 0`).

### Logic

1. Look up `project.dataset_id`
2. Load the dataset via `DatasetService._load_ds(ds_id)`
3. Build list of all row indices `[0..num_rows)`
4. Query annotations for the user/project to determine annotated set
5. Filter by `status`:
   - `all` — no filter
   - `annotated_by_me` — only indices in the annotated set
   - `unannotated` — only indices NOT in the annotated set
6. Paginate with `page` / `per_page`
7. If `include_annotations`, attach annotation data to each row entry
8. Return `(rows_list, total_count)`

### Return shape

```json
{
  "rows": [
    {"index": 0, "annotations": null},
    {"index": 1, "annotations": {"sentiment": "positive"}}
  ],
  "total": 25000,
  "page": 1,
  "per_page": 50
}
```

### BrowseView frontend

Already correctly calls `api.browseRows()` and renders via `RowGrid`. No frontend changes needed — the stub was the only blocker.

---

## 6. Backend API Changes

| Endpoint | Change |
|---|---|
| `POST /api/v1/datasets/load` | Accept any source type, detect + validate format |
| `POST /api/v1/datasets/upload` | New — multipart file upload |
| `GET /api/v1/projects/{pid}/rows` | No change (router already calls `browse_rows`) |

## 7. Files to Change

| File | Change |
|---|---|
| `backend/services/dataset_service.py` | Source detection, format dispatch, `_load_ds` rehydration |
| `backend/routers/datasets.py` | Add upload endpoint, new body schema for load |
| `backend/services/annotation_service.py` | Implement `browse_rows` |
| `frontend/src/views/SetupView.tsx` | Load dialog UI (input + upload + errors) |
| `frontend/src/api/client.ts` | Add uploadDataset method |

## 8. Error Handling

- Invalid format → `400` with supported formats listed
- Download failure → `400` with connection error message
- Malformed file (parse error) → `400` with parser error detail
- Missing file (`file://` or upload) → `404` / `400`
