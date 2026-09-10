# Install

fyndnote ships as a Docker image that serves both the backend and the built frontend from one container. You can run it with **Docker Compose** (recommended, includes an optional MinIO S3 cache) or with the **plain Docker CLI**.

## Prerequisites

- Docker Engine 20.10+ and Docker Compose v2 (`docker compose version`)
- 4 GB free RAM recommended (the image builds the frontend, then runs uvicorn)

## Architecture

The install runs two main pieces: the **fyndnote app container** (backend + built frontend) and, optionally, a **MinIO** S3-compatible cache. Persistent state lives on the host via a bind-mount of `./data`.

```mermaid
flowchart LR
  subgraph host[Host]
    data[./data - volume map]
    browser[Browser - localhost:8000]
  end

  subgraph app[fyndnote container :8000]
    frontend[React frontend]
    backend[FastAPI backend]
    sqlite[(Database - sqlite or postgres)]
  end

  subgraph s3[MinIO container]
    minio[(label-tool-cache bucket)]
  end

  browser -->|HTTP| frontend
  frontend -->|API /api/v1| backend
  backend <--> sqlite
  backend <-->|S3 cache| minio
  data <-->|bind mount /app/data| sqlite
```

- The **frontend** talks to the **backend** over `/api/v1`.
- The **backend** reads/writes the SQLite DB, which persists to the host `./data` volume.
- When S3 is enabled, the **backend** uploads/downloads cold datasets to/from the **MinIO** bucket.

## Option A — Docker Compose (recommended)

The compose file (`docker-compose.yml`) runs the app together with an optional MinIO S3 cache and a bucket-setup job:

```bash
docker compose up --build
```

This:

1. Builds the image.
2. Starts MinIO (S3-compatible storage) and creates the `label-tool-cache` bucket.
3. Runs the app with `network_mode: host`, so the API is at **`http://localhost:8000`** (Swagger at `/docs`) and the frontend at the same address.
4. Mounts `./data` into `/app/data` so your SQLite DB, datasets, and templates persist on the host.

### Env vars used by compose

| Var                     | Default                 | Purpose                                |
| ----------------------- | ----------------------- | -------------------------------------- |
| `S3_CACHE_ENABLED`      | `true`                  | Enable the S3-backed dataset cache     |
| `S3_CACHE_BUCKET`       | `label-tool-cache`      | MinIO bucket name                      |
| `S3_CACHE_PREFIX`       | `datasets-cache`        | Object key prefix                      |
| `S3_ENDPOINT_URL`       | `http://localhost:9000` | MinIO endpoint                         |
| `AWS_ACCESS_KEY_ID`     | `minioadmin`            | MinIO root user                        |
| `AWS_SECRET_ACCESS_KEY` | `minioadmin`            | MinIO root password                    |
| `MAX_CACHED_DATASETS`   | `1`                     | LRU cache size                         |
| `DISK_USAGE_THRESHOLD`  | `0.1`                   | Evict cold cache above this disk ratio |

## Option B — Plain Docker CLI

Build the image:

```bash
docker build -t fyndnote .
```

Run without S3 (local-only mode):

```bash
docker run -d --name fyndnote \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  -e S3_CACHE_ENABLED=false \
  fyndnote
```

Open **`http://localhost:8000`** — the built frontend is served at `/`, and the Swagger UI is at `/docs`.

### Run with MinIO S3 cache

```bash
docker run -d --name minio \
  -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"

docker run -d --name fyndnote \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  -e S3_CACHE_ENABLED=true \
  -e S3_CACHE_BUCKET=label-tool-cache \
  -e S3_CACHE_PREFIX=datasets-cache \
  -e S3_ENDPOINT_URL=http://localhost:9000 \
  -e AWS_ACCESS_KEY_ID=minioadmin \
  -e AWS_SECRET_ACCESS_KEY=minioadmin \
  fyndnote
```

## Data persistence

- `data/labeling.db` — SQLite database (auto-created on first start).
- `data/users.json` — seed users (you must provide this on the host).
- `data/datasets/` — Hugging Face dataset cache / uploads.
- `data/templates/` — template JSON files.

The wheel ships a default seed user file inside the package (`fyndnote/_data/users.json`), used only when no `users.json` exists in the data dir. With the bind-mount (`./data:/app/data`), put your own `users.json` on the host before first run (see [Quick Start](/guide/)).

## Stopping

```bash
# compose
docker compose down

# cli
docker stop fyndnote
```

To reset everything, delete the `data/` folder and run again — the DB is recreated from `users.json`.

## Install from PyPI

```bash
pipx install fyndnote    # or: pip install fyndnote
fyndnote --port 8000
```

The wheel bundles the built web app and the docs site, so one install serves the
SPA at `/`, the API at `/api/v1` and the docs at `/fyndnote` — no Docker or Node
required. Data (SQLite DB, datasets, templates) lives in `~/.fyndnote` by
default; choose another location with `--data-dir <path>` or the `FYNDNOTE_HOME`
environment variable. PostgreSQL support comes from the `fyndnote[postgres]`
extra plus a `DATABASE_URL` env var.

## Install from a git URL

```bash
pip install "git+https://github.com/godesity/fyndnote.git"          # public
pip install "git+ssh://git@github.com/godesity/fyndnote.git@main"   # private (ssh key)
```

A PEP 517 build hook builds the SPA and the docs site with npm during the wheel
build, so a git install ships the same UI as the PyPI wheel. Requirements on the
installing machine: `git`, `node` and `npm` on PATH. Builds take a few minutes
the first time (`npm ci`). On a machine without Node, set
`FYNDNOTE_SKIP_WEB_BUILD=1` to build an API-only package, or install a
pre-built wheel from a release instead.
