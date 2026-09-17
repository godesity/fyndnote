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
| GET | `/datasets/config` | Upload limits the SPA should pre-flight against. |
| POST | `/datasets/load` | Load a dataset from a source string (requires `user_id`). |
| POST | `/datasets/upload` | Upload and load a dataset file (requires `user_id`). |
| DELETE | `/datasets/{id}` | Delete a dataset and free its files (system admin; refused with 409 while a project uses it). |
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
| GET | `/projects/{id}` | Project detail + progress + `my_role` / `can_manage` / `can_view`. |
| PUT | `/projects/{id}` | Update a project (requires a project admin). |
| DELETE | `/projects/{id}` | Delete a project (requires a project admin). |
| GET | `/projects/{id}/next-row` | Next unannotated row. |
| POST | `/projects/{id}/annotate` | Submit an annotation. |
| GET | `/projects/{id}/annotations/{row}` | Read an annotation. |
| GET | `/projects/{id}/annotations/export` | Export annotations (parquet). |

### Project members

Membership is managed from the project **Settings** page. `user_id` identifies the
acting user; project admins and global (`system_admin`) users may manage members.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/projects/{id}/members` | List members with their project role (members only). |
| GET | `/projects/{id}/member-candidates` | Search non-members to add (admins only). |
| PUT | `/projects/{id}/members` | Add a user or change their role (admins only). |
| DELETE | `/projects/{id}/members/{user}` | Remove a member (admins only; keeps ≥1 project admin). |

### AI prefill

| Method | Path | Description |
|--------|------|-------------|
| POST | `/projects/{id}/ml-prefill` | Prefill one row. |
| POST | `/projects/{id}/ml-batch` | Prefill a batch of rows. |
| GET | `/projects/{id}/ml-annotations/{row}` | Read an AI annotation. |

### Large uploads

`POST /datasets/upload` streams the multipart body to
`data/datasets/uploads/<uuid>.<ext>` in 1 MiB chunks — the payload never becomes a
single in-memory buffer (a 1.1 GB CSV upload peaks the worker at ~450 MB RSS, and
the event loop keeps answering other requests throughout). Three limits govern it,
all environment-configurable and all advertised by `GET /datasets/config`:

| Variable | Default | Meaning |
|----------|---------|---------|
| `MAX_UPLOAD_BYTES` | 2 GiB | Per-file cap. Enforced twice: from `Content-Length` in a pure-ASGI guard *before any body byte is read*, and again from the streamed copy. Over-budget requests get **413**. |
| `MAX_CONCURRENT_UPLOADS` | 2 | Simultaneous conversions. Each in-flight conversion costs disk for the copy plus RAM proportional to the file, so this is the OOM guard. |
| `MAX_UPLOAD_WAIT_SECONDS` | 900 | How long a request may queue for a free conversion slot before **503**. |

The `Content-Length` check has to sit outside the endpoint: FastAPI parses the whole
multipart body before any handler code runs, so a check inside the function is only
reached after every byte has arrived — and a client that over-claims the header
never reaches the handler at all, because the server is still waiting for bytes that
do not exist.

`user_id` is required on the mutating endpoints and must name an existing account
(**401** `unknown_user` otherwise). `DELETE /datasets/{id}` additionally requires
`system_admin` and removes the row, the arrow cache and the upload copy — that is
the only path in the app that ever frees dataset disk. Files left in
`data/datasets/uploads/` by a crashed or rejected import (nothing in the DB points
at them) are swept at startup once they are older than 30 minutes.

> The authoritative, machine-readable schema is `openapi.json`. The exact routes, request bodies, and response models are shown in the interactive viewer.
