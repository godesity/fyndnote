# Stage 1: Build frontend
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 1b: Build docs site
FROM node:20-alpine AS docs
WORKDIR /app
COPY package.json package-lock.json ./
COPY docs/ ./docs/
RUN npm ci && npm run docs:build

# Stage 2: Build the fyndnote wheel (assets arrive from the node stages)
FROM python:3.11-slim AS package
WORKDIR /app

RUN pip install --no-cache-dir uv

# Built assets land where tools/build_wheel.py expects them.
COPY --from=frontend /app/frontend/dist ./frontend/dist
COPY --from=docs /app/docs/.vitepress/dist ./docs/.vitepress/dist

COPY pyproject.toml LICENSE README.md .python-version hatch_build.py ./
COPY fyndnote/ ./fyndnote/
COPY tools/ ./tools/

# Inline the asset-sync step of tools/build_wheel.py (no npm/node here).
RUN rm -rf ./fyndnote/web && \
  mkdir -p ./fyndnote/web && \
  cp -r ./frontend/dist ./fyndnote/web/frontend && \
  cp -r ./docs/.vitepress/dist ./fyndnote/web/docs

RUN uv build

# Stage 3: Runtime — install the wheel, serve API + SPA + docs
FROM python:3.11-slim
WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential \
  && rm -rf /var/lib/apt/lists/*

# Create a non-root user to run the app.
# UID/GID 1000 matches the host user so the bind-mounted ./data dir stays writable.
RUN addgroup --gid 1000 app && adduser --uid 1000 --gid 1000 --disabled-password --gecos "" app

COPY --from=package /app/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl psycopg[binary] && rm /tmp/*.whl

# Runtime data dir (SQLite DB, datasets, templates) — bind-mounted in compose.
ENV FYNDNOTE_HOME=/app
RUN mkdir -p /app/data && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["fyndnote", "--host", "0.0.0.0", "--port", "8000"]
