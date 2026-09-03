# Docs Home Page + In-App Embedding — Design

Date: 2026-09-03
Status: Approved

## Context

Two goals:

1. Rework the docs landing page (`docs/index.md`, VitePress home layout) into a
   problem-first landing page: hook, goal, reason to choose the tool, screenshots.
2. Bake the built VitePress site into the app so users reach the docs from the
   running application instead of a separate external deployment.

The docs site currently builds standalone under `base: '/fyndnote/'` (see
`docs/.vitepress/config.mts`). The in-app URL therefore becomes **`/fyndnote/`**
— same base path, no doc-side config changes. The external `/fyndnote/`
deployment is dropped; docs live in the app.

## Prerequisite (already done, verified)

The dev server crashed at load with
`SyntaxError: .../fastdom/fastdom.js does not provide an export named 'default'`.

Root cause: `mermaid@11.17.0` (dep of `vitepress-plugin-mermaid`) ships raw ESM
dist chunks that default-import `fastdom`, but `fastdom@1.0.12` only ships a
UMD build (no ESM exports). In dev, Vite served the raw UMD file via `@fs`,
which as an ES module provides no `default` export.

Fix landed in `docs/.vitepress/config.mts` (uncommitted at spec-writing time):

```ts
vite: {
  optimizeDeps: {
    include: ['fastdom', 'fastdom/extensions/fastdom-promised.js'],
  },
},
```

Verified: the dev server rewrites the imports to prebundled
`.vitepress/cache/deps/fastdom.js` modules that export a proper default
(`export default require_fastdom()`).

## Part 1 — Docs home page

Rewrite `docs/index.md` keeping the `layout: home` frontmatter, with these
blocks in VitePress home order: hero → features → markdown content.

### Hero

| Field     | Value                                                                  |
|-----------|------------------------------------------------------------------------|
| name      | `fyndnot` (unchanged)                                                   |
| text      | `ML dataset annotation tool` (unchanged)                               |
| tagline   | `Every new dataset has meant a new labeling app. Not anymore.`         |
| actions   | unchanged: `User Guide` → `/guide/`, `API Reference` → `/api/`         |

### Features (the "reason to choose")

Four problem→value cards, replacing the current four:

1. **No per-dataset frontend work** — labeling UIs are templates with a live
   preview; the UI adapts to the dataset, not the other way around.
2. **Reusable widgets** — text, image boxes/polygons, and audio annotation
   through six widgets with no glue code.
3. **Bring your own data** — Hugging Face, HTTP URLs, local files, or direct
   browser upload; no ETL layer in between.
4. **Fast review, clean output** — a filter DSL over data/annotations/metadata,
   optional AI prefill, and Parquet export.

### Markdown content below the features

Three sections:

1. **Goal** — 2–3 sentences defining the product:
   "fyndnot turns any dataset into an annotation project: load your data,
   define the labeling UI from reusable widgets with a live preview, collect
   annotations from annotators, and export labeled rows as Parquet — without
   writing frontend code."
   Followed by the condensed 8-step end-to-end flow from
   `docs/guide/index.md` ("An annotation project moves through a fixed
   sequence — dataset → template → label → browse → export"), linking to the
   guide for details.
2. **Screenshots** — 3-column grid of `setup.png`, `label.png`, `browse.png`
   (from `docs/public/images/`) with captions:
   *Admin creates a project*, *Annotator labels rows*, *Review & filter
   results*. `docs/index.md` uses a small markdown/CSS grid; `theme/index.css`
   gains the utility classes (rounded corners, shadow, brand spacing).
   `overview.png` and the two widget shots are NOT used on the home page
   (they belong to the guide).
3. **Quick start** — three steps: sign in → **New Project** → load a dataset.
   Links out to `/install` (Docker) and `/guide/create-project`.

No new images are generated; only existing screenshots are used.

## Part 2 — Embedding in the app

### URL scheme

Docs are served by the FastAPI app at **`/fyndnote/`** (matching the existing
`base: '/fyndnote/'`). Public, no auth — docs contain no secrets, and app SSO
stays SPA-level as today.

### Dockerfile

Add a third build stage before the final one:

- Stage `docs` on `node:20-alpine`: copy root `package.json` +
  `package-lock.json` + `docs/`, run `npm ci && npm run docs:build`, then copy
  `docs/.vitepress/dist` to `/app/docs/dist`.
- Final stage: `ENV DOCS_DIST=/app/docs/dist`.

### backend/main.py

Follow the existing optional-frontend pattern:

```python
repo_root = Path(__file__).resolve().parent.parent  # same pattern as frontend_dist
docs_dist = Path(os.getenv("DOCS_DIST", repo_root / "docs" / ".vitepress" / "dist"))
if docs_dist.is_dir():
    app.mount("/fyndnote", StaticFiles(directory=str(docs_dist), html=True), name="docs")
```

- `html=True` serves `index.html` for `/` and clean-URL directories
  (`/fyndnote/guide/` → `guide/index.html`).
- The mount is registered before the SPA 404 fallback, so any hit under
  `/fyndnote/*` that the mount resolves never falls through to the app shell.
- The SPA fallback's 404 exclusion list gains `/fyndnote`, so unknown docs
  paths return a real 404 instead of the SPA shell.

### App → docs link

`BreadcrumbNav` (rendered by all five in-app views) gains a persistent
**Docs** link → `/fyndnote/`, placed beside the existing crumbs. `LoginView`
gains a small "Read the docs" link under the SSO button.

### Docs → app link

`docs/.vitepress/config.mts` `themeConfig.nav` gains one item: `Open the app`
→ `/`.

### Dev workflow

- `npm run docs:build` (once) produces `docs/.vitepress/dist`; the app then
  serves `/fyndnote/` in dev.
- `npm run docs:dev` still works standalone (and no longer crashes, see
  Prerequisite).
- README gains a short "Documentation site" section covering both entry
  points.

## Testing

- **Backend (TestClient):** point `DOCS_DIST` at a fixture directory containing
  a stub `index.html` and `install/index.html`; assert:
  - `GET /fyndnote/` → 200, body is the docs index stub
  - `GET /fyndnote/install` → 200 (clean URL via `html=True`)
  - `GET /` still serves the SPA shell index.html
  - `GET /fyndnote/nope` → 404 (not the SPA shell)
- **Frontend:** `tsc`/build stays clean after adding the BreadcrumbNav +
  LoginView links.
- **Docker smoke:** `docker compose build` runs the new `docs` stage;
  `GET /fyndnote/` returns the real docs page.

## Out of scope

- Rewriting docs content beyond `index.md` (guide/ API/ install pages keep
  their structure).
- Auth-gating the docs URL.
- Keeping the external `/fyndnote/` deployment working.
- A custom VitePress theme beyond the existing `theme/index.css` brand layer
  (the home layout + slotless markdown is sufficient).
