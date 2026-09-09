# API Overview

The fyndnote backend exposes a REST API under the base path **`/api/v1`**. The full OpenAPI/Swagger schema is rendered interactively on the [Swagger page](/api/swagger).

## Endpoints

### Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/login` | Login by user ID. Returns the user's global role and project roles. |

### Datasets

| Method | Path | Description |
|--------|------|-------------|
| GET | `/datasets` | List loaded datasets. |
| POST | `/datasets/load` | Load a dataset from a source string. |
| POST | `/datasets/upload` | Upload and load a dataset file. |
| GET | `/datasets/{id}/rows/{index}` | Get a row. |
| GET | `/datasets/{id}/rows/{index}/columns/{column}` | Get a binary column (image/audio). |

### Templates

| Method | Path | Description |
|--------|------|-------------|
| GET | `/templates` | List templates. |
| GET | `/templates/{id}` | Get a template. |
| POST | `/templates` | Create a template. |
| PUT | `/templates/{id}` | Update a template. |

### Projects

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects` | List projects (role-aware). |
| POST | `/projects` | Create a project. |
| GET | `/projects/{id}` | Project detail + progress. |
| PUT | `/projects/{id}` | Update a project. |
| DELETE | `/projects/{id}` | Delete a project. |
| GET | `/projects/{id}/next-row` | Next unannotated row. |
| POST | `/projects/{id}/annotate` | Submit an annotation. |
| GET | `/projects/{id}/annotations/{row}` | Read an annotation. |
| GET | `/projects/{id}/annotations/export` | Export annotations (parquet). |

### AI prefill

| Method | Path | Description |
|--------|------|-------------|
| POST | `/projects/{id}/ml-prefill` | Prefill one row. |
| POST | `/projects/{id}/ml-batch` | Prefill a batch of rows. |
| GET | `/projects/{id}/ml-annotations/{row}` | Read an AI annotation. |

> The authoritative, machine-readable schema is `openapi.json`. The exact routes, request bodies, and response models are shown in the interactive viewer.
