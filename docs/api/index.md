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
| GET | `/datasets` | List loaded datasets. Each carries a unique display `name`. |
| GET | `/datasets/name-available` | Pre-flight a display name (`?name=`) or a source (`?source=`); returns `available` plus a free `suggested_name`. |
| POST | `/datasets/load` | Load a dataset from a source string. Optional `alias` sets the display name; a taken one returns `409`. |
| POST | `/datasets/upload` | Upload and load a dataset file. The display name defaults to the original filename (override with `alias`); a taken one returns `409`. |
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

> The authoritative, machine-readable schema is `openapi.json`. The exact routes, request bodies, and response models are shown in the interactive viewer.
