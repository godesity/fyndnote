---
layout: home
hero:
  name: fyndnot
  text: ML dataset annotation tool
  tagline: Every new dataset has meant a new labeling app. Not anymore.
  actions:
    - theme: brand
      text: User Guide
      link: /guide/
    - theme: alt
      text: API Reference
      link: /api/
features:
  - title: No per-dataset frontend work
    details: Labeling UIs are templates with a live preview; the UI adapts to the dataset, not the other way around.
  - title: Reusable widgets
    details: Text, image boxes/polygons, and audio annotation through six widgets — no glue code.
  - title: Bring your own data
    details: Hugging Face, HTTP URLs, local files, or direct browser upload; no ETL layer in between.
  - title: Fast review, clean output
    details: A filter DSL over data, annotations, and metadata, optional AI prefill, and Parquet export.
---

## Goal

fyndnot turns any dataset into an annotation project: load your data, define the
labeling UI from reusable widgets with a live preview, collect annotations from
annotators, and export labeled rows as Parquet — without writing frontend code.

## How a project flows

An annotation project moves through a fixed sequence:

1. **Load a dataset** — Hugging Face, HTTP URL, local file, or browser upload.
2. **Pick or edit a template** — the labeling UI, previewed live before saving.
3. **Create the project** — name, color, tags, instructions; optionally enable AI prefill.
4. **Label rows** — annotators work through the dataset one row at a time.
5. **Browse & filter** — check progress and filter by data, annotation, or metadata.
6. **Export as Parquet** — download the annotated dataset.

Full walkthrough: [User Guide](/guide/).

## Screenshots

<div class="fyndnot-screenshots">

<figure>
  <img src="./public/images/setup.png" alt="Admin creates a project" />
  <figcaption>Admin creates a project</figcaption>
</figure>

<figure>
  <img src="./public/images/label.png" alt="Annotator labels rows" />
  <figcaption>Annotator labels rows</figcaption>
</figure>

<figure>
  <img src="./public/images/browse.png" alt="Review and filter results" />
  <figcaption>Review &amp; filter results</figcaption>
</figure>

</div>

## Quick start

1. **Sign in** — SSO (or the seeded dev users).
2. **New Project** — admins load a dataset and pick a template with live preview.
3. **Load a dataset** — e.g. `stanfordnlp/imdb`, then create the project and start labeling.

[Docker installation](/install) · [Create your first project](/guide/create-project)
