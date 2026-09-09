# fyndnot

A general-purpose ML dataset annotation tool. Define labeling interfaces via restricted React component templates rendered in `react-live`. Supports text, image (bounding box), and audio annotation through reusable widgets.

## Tech Stack

| Layer              | Technology                |
|--------------------|---------------------------|
| Backend            | Python + FastAPI + uvicorn|
| Data Loading       | Hugging Face `datasets`   |
| Storage            | SQLite + JSON files       |
| Export             | Parquet (PyArrow)         |
| Frontend           | React 19 + TypeScript 6   |
| Templating         | react-live sandbox        |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- `uv` package manager (`pip install uv`)

### 1. Seed users

```bash
cat > data/users.json << 'EOF'
{
  "users": [
    { "id": "alice", "name": "Alice", "global_role": "system_admin" },
    { "id": "bob",   "name": "Bob",   "global_role": "annotator",
      "project_roles": { "proj-1": "project_admin", "proj-2": "annotator" } }
  ]
}
EOF
```

### 2. Start the backend

```bash
cd backend
uv sync
uv run uvicorn main:app --reload --port 8000
```

The API is served at `http://localhost:8000/api/v1`. Open `http://localhost:8000/docs` for Swagger.

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173`.

### 4. Use it

1. Login as `alice` (system admin)
2. Click **New Project**
3. Load a dataset (e.g., `stanfordnlp/imdb`)
4. Edit the template or use the default
5. Save the template, name your project, and create it
6. Click **Label** to start annotating rows

## Single Sign-On (Keycloak, MinIO-style OIDC)

fyndnot can authenticate through Keycloak using the standard OpenID Connect
Authorization Code flow — the same pattern MinIO uses for its web console.
The backend validates Keycloak-issued JWTs **statelessly** against the realm's
JWKS endpoint (public keys fetched and cached), so no per-request call to
Keycloak is needed once keys are cached.

### Enabling SSO

1. Start Keycloak in development mode:

   ```bash
   docker compose --profile sso up -d keycloak
   ```

   Console: `http://localhost:8080` (admin / admin).

2. In the Keycloak admin console create a realm named `fyndnot`, then a client:
   - Client ID: `fyndnot-app`
   - Access Type: `confidential`
   - Valid redirect URIs: `http://localhost:5173/callback`
   - (optional) Client roles `system_admin` and `annotator` mapped to users.

3. Set the env vars (see `config.py`):

   ```bash
   SSO_ENABLED=true
   KEYCLOAK_URL=http://localhost:8080
   KEYCLOAK_REALM=fyndnot
   KEYCLOAK_CLIENT_ID=fyndnot-app
   KEYCLOAK_CLIENT_SECRET=<client secret>
   SSO_REDIRECT_URI=http://localhost:5173
   ```

4. Restart the backend. The login screen becomes **Sign in with SSO**, which
   redirects to Keycloak and back to `/callback`.

### How it maps roles

- Keycloak **realm roles** map onto `global_role`:
  - `system_admin` → `system_admin`
  - anything else (or none) → `annotator` (least privilege)
- **Project permissions** are still sourced from the local `fyndnot_project_permissions`
  table (seeded via `data/users.json`), so realm roles govern only the global role.

### SSO endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/v1/sso/login` | Redirect to Keycloak authorize |
| GET    | `/api/v1/sso/callback` | Exchange code → JWT + local user |
| GET    | `/api/v1/sso/logout` | Redirect to Keycloak logout |
| GET    | `/api/v1/sso/me` | Decode Bearer JWT → local user |

The frontend stores the JWT in `localStorage` (`fyndnot_sso_token`) so refreshes
stay signed in, and resolves it via `/sso/me` when needed.

## Documentation site

The docs live in `docs/` and are built with [VitePress](https://vitepress.dev/).

- **Standalone dev:** `npm run docs:dev` → `http://localhost:5173/fyndnote/`
- **In the app:** `npm run docs:build` once, then open `/fyndnote/` inside the
  running app (dev server or Docker — the Docker image builds the docs
  automatically and sets `DOCS_DIST`).

## Project Structure

```
backend/
  main.py                     # FastAPI entry point, CORS, lifespan
  config.py                   # Path constants
  database.py                 # SQLite schema init + seeding
  schemas.py                  # Pydantic models
  routers/
    auth.py                   # POST /auth/login
    datasets.py               # Dataset loading + row access
    templates.py              # Template CRUD
    projects.py               # Projects, annotation, export
  services/
    dataset_service.py        # HF datasets load + cache
    template_service.py       # JSON file CRUD
    annotation_service.py     # SQLite queries
frontend/
  src/
    api/client.ts             # API client
    context/
      AuthContext.tsx          # Login state
      AnnotationContext.tsx    # Widget state registration
    widgets/                   # 6 annotation widgets
    views/
      LoginView.tsx
      ProjectListView.tsx      # List + routing
      SetupView.tsx            # Admin: create projects
      LabelView.tsx            # Annotate rows
      BrowseView.tsx           # Browse + inspect rows
    components/                # Shared UI components
data/
  users.json                  # Seed users (tracked in git)
  labeling.db                 # SQLite DB (ignored, auto-created)
  datasets/                   # HF dataset meta (ignored)
  templates/                  # Template JSON files (ignored)
```

## API Overview

All endpoints under `/api/v1`:

| Method | Path | Description |
|--------|------|-------------|
| POST   | `/auth/login` | Login by user ID |
| GET    | `/datasets` | List loaded datasets |
| POST   | `/datasets/load` | Load a HF dataset |
| GET    | `/datasets/{id}/rows/{idx}` | Get a row |
| GET    | `/datasets/{id}/rows/{idx}/columns/{col}` | Get binary column (image/audio) |
| POST   | `/templates` | Create template |
| GET    | `/templates/{id}` | Get template |
| PUT    | `/templates/{id}` | Update template |
| GET    | `/templates` | List templates |
| GET    | `/projects` | List projects (role-aware) |
| POST   | `/projects` | Create project |
| GET    | `/projects/{id}` | Project detail + progress |
| GET    | `/projects/{id}/next-row` | Next unannotated row |
| POST   | `/projects/{id}/annotate` | Submit annotation |
| GET    | `/projects/{id}/annotations/{row}` | Get annotation |
| GET    | `/projects/{id}/annotations/export` | Export as Parquet |
| DELETE | `/projects/{id}` | Delete project |

## Running Tests

```bash
cd backend
rm -f ../data/labeling.db
uv run python -m pytest ../tests/backend/ -v
```

## Development

Hot-reload is built in:

- **Backend:** `uv run uvicorn main:app --reload --port 8000` (auto-restarts on changes)
- **Frontend:** `npm run dev` (Vite HMR — instant updates in browser)
