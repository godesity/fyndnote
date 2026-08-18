# Architecture Decision Record — fyndnot

**Date:** 2026-08-13
**Status:** Approved

## Overview

A general-purpose ML dataset annotation tool. Users define labeling interfaces via
restricted React component templates rendered in `react-live`. Backed by Hugging
Face `datasets` for data loading, SQLite for relational data (users, projects,
annotations), and Parquet for annotation export.

## Tech Stack

| Layer              | Choice                      |
|--------------------|-----------------------------|
| Backend            | Python + FastAPI            |
| Data Loading       | Hugging Face `datasets`     |
| Relational Store   | SQLite (swappable)          |
| Annotation Export  | Parquet                     |
| Frontend           | React + TypeScript          |
| Template Engine    | react-live (sandboxed)      |

## Key Decisions

### 1. Template Engine: react-live

**Decision:** Use `react-live` to render user-supplied React components as the
labeling UI.

**Rationale:**
- Users get full layout/styling flexibility inside a template
- react-live provides built-in sandboxing (no arbitrary imports)
- Components are just strings stored in the backend — easy to version and share
- The predefined widget set acts as a natural API boundary

**Imports available inside templates:** Only our predefined annotation widgets
plus basic React hooks (useState, useCallback).

### 2. Dataset Abstraction via HF `datasets`

**Decision:** All data sources are loaded through Hugging Face `datasets`,
providing a uniform `Dataset` object regardless of source format.

**Rationale:**
- Unifies CSV, JSONL, Parquet, image folders, audio folders, etc.
- Handles typed columns (Image, Audio, Value) natively
- Supports indexing, slicing, and metadata introspection
- Streaming support for large datasets

### 3. Relational Store: SQLite

**Decision:** Users, projects, permissions, and annotations are stored in a
single SQLite database (`data/labeling.db`). Datasets and templates remain
file-based (HF `datasets` + JSON).

**Rationale:**
- SQLite handles upserts natively (`INSERT OR REPLACE`) — no overwrite problem
- Efficient queries: "next unlabeled row", progress, filtering by user
- Joins between users, projects, and annotations are trivial
- Single file, no external database server
- Can be swapped for PostgreSQL later without API changes

**Export:** Annotations can be exported to Parquet for consumption by ML
training pipelines.

### 4. Deterministic Row Ordering

**Decision:** Each user sees rows in a unique but consistent order, computed via
`hash(user_id + project_salt + row_index)`.

**Rationale:**
- Reduces annotation collisions between users
- Consistent across refreshes (same user, same order)
- No shared state needed for ordering
- Simple to implement

### 5. Project Model

**Decision:** A project binds exactly one dataset to exactly one template.
Annotations belong to a (project, row_index, user_id) triple.

**Rationale:**
- Clear ownership and scope
- Multiple users can annotate the same row independently
- Progress is tracked per (project, user)
- Template is set at project creation time, immutable for annotators

## User Roles

Two role domains: a single **global role** and per-project **project roles**.

### Global role

| Role            | Permissions                                      |
|-----------------|--------------------------------------------------|
| `system_admin`  | Create/delete projects, manage users, see all projects, full access inside projects |

### Project roles (per-project)

Assigned via the user's `project_roles` map. Users only see projects they have a role in.

| Role             | Permissions                                  |
|------------------|----------------------------------------------|
| `project_admin`  | Edit template, browse data, label rows       |
| `annotator`      | Browse data, label rows                      |

### Capability matrix

| Capability                      | system_admin | project_admin | annotator |
|---------------------------------|:---:|:---:|:---:|
| Create/delete projects          |  ✓  |  ✗  |  ✗  |
| Manage users                    |  ✓  |  ✗  |  ✗  |
| See all projects                |  ✓  |  ✗  |  ✗  |
| Edit template (assigned)        |  ✓  |  ✓  |  ✗  |
| Label rows (assigned)           |  ✓  |  ✓  |  ✓  |
| Browse data (assigned)          |  ✓  |  ✓  |  ✓  |

## Frontend Views

| View        | Role                              | Description                          |
|-------------|-----------------------------------|--------------------------------------|
| Setup View  | system_admin                      | Dataset selector + template editor   |
| Label View  | project_admin, annotator          | Row-by-row labeling via template     |
| Browse View | system_admin, project_admin, annotator | Grid of rows with annotation status  |
