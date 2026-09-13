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

## DSPy LLM Backend

Instead of hosting your own model server, a project can use the built-in **DSPy** backend:
the annotation template is compiled into a DSPy program and run against any OpenAI-compatible
LLM endpoint. Pick *DSPy LLM* under **ML Backend** on the project settings page.

### Server configuration

| Env var | Purpose | Default |
| --- | --- | --- |
| `FYNDNOTE_LLM_API_KEY` | API key sent to the endpoint | — (Test/Tune disabled until set) |
| `FYNDNOTE_LLM_API_BASE` | OpenAI-compatible base URL (per-project override available) | provider default |
| `FYNDNOTE_LLM_MODEL` | Default model string (per-project override available) | `openai/gpt-4o-mini` |

Compiled prompt state is stored per project under `data/dspy/<project-id>.json`.

### Prompt Studio

On the project settings page, *Prompt Studio* exposes the compiled program so you can
inspect and edit exactly what runs:

- **Instruction** — the prompt instruction; fully transparent and editable. Saving rewrites
  the tuned program state with your text.
- **Input / output fields** — derived from the annotation template (`{data.…}` references
  become inputs, widget fields become typed outputs: select, multi-select, rating, text, list).
  Toggle fields on/off; edits persist until you click *Re-derive from template*.
- **Test row 0** — dry-run the program on a dataset row without writing an AI annotation.
- **Tune** — run DSPy optimization (`bootstrap` = BootstrapFewShot, `mipro` = MIPROv2) over
  rows you have already annotated; shows score / demos / train-val split. *Reset tuning*
  drops the compiled state but keeps your instruction edits.
- **Clear predictions** — delete all cached AI annotations for the project.

### Endpoints

- `GET /projects/{pid}/dspy` — current compiled config (auto-derived from the template on first read).
- `PUT /projects/{pid}/dspy` — save instruction / field edits.
- `POST /projects/{pid}/dspy/derive` — re-derive config from the current template (discards field edits + tuning).
- `POST /projects/{pid}/dspy/test` — dry-run `{ "row_index": n }`.
- `POST /projects/{pid}/dspy/train` — `{ "optimizer": "bootstrap" | "mipro", "max_examples": n }`.
- `POST /projects/{pid}/dspy/reset` — clear tuning state.

Prefill/batch (`ml-prefill`, `ml-batch`) dispatch to DSPy when the project's `ml_type` is `dspy`;
`ml_type: "external"` keeps using the classic `ml_url` POST backend.
