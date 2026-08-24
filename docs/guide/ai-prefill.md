# AI Prefill

Projects can optionally be backed by an **AI backend** that suggests annotations automatically. This is configured on the project (enabled flag, AI URL, annotator name, and mode).

## Endpoints

- **Prefill one row** — `POST /projects/{pid}/ml-prefill` with `{ "row_index": n }`. Returns a suggested `annotation` and `annotator`.
- **Prefill a batch** — `POST /projects/{pid}/ml-batch` with optional `{ "row_indices": [...] }`. Returns `total`, `succeeded`, `failed`.
- **Read an AI annotation** — `GET /projects/{pid}/ml-annotations/{row_index}`.

## Behavior

- AI annotations are cached per `(project, row)` and stored separately from human annotations (the AI store).
- Already-prefilled rows are skipped during a batch.
- If AI is disabled or the backend is unreachable, prefill returns an empty result instead of failing the project.

## Mode

The `ml_mode` setting (default `on_navigate`) controls when prefill is triggered during annotation.
