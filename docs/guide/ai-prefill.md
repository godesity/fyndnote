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

Versioned prompt state lives in the database (`fyndnote_dspy_prompts`, one row per
saved/tuned prompt, plus a pending candidate table). `data/dspy/<project-id>.json`
holds only the derived field schema.

### Prompt Studio

On the project settings page, *Prompt Studio* exposes the compiled program so you can
inspect and edit exactly what runs:

- **Instruction** — the prompt that actually runs; fully transparent and editable.
  Saving creates a new prompt *version* and rewrites its embedded instruction so the
  tuned demos can't silently override your text.
- **Input / output fields** — derived from the annotation template (`{data.…}` references
  become inputs, widget fields become typed outputs: select, multi-select, rating, text, list).
  Toggle fields on/off; edits persist until you click *Re-derive from template*.
- **Test row 0** — dry-run the program on a dataset row without writing an AI annotation.
- **Tune (candidate)** — run DSPy optimization (`bootstrap` = BootstrapFewShot,
  `mipro` = MIPROv2) over rows you have already annotated. Tuning never goes live on
  its own: the result is parked as a *pending* candidate with its score / demos /
  train-val split, and predictions keep using the current prompt until you
  **Accept & make live** (new tuned version) or **Discard** it.
- **History** — every prompt version, newest first, with optimizer, score, demo count
  and parent version. *Use this* reverts predictions to that version (instruction and
  demos travel together); the current version stays in history.
- **Reset tuning** — drops the tuned demos but keeps your instruction text.
- **Clear predictions** — delete all cached AI annotations for the project.

### Endpoints

- `GET /projects/{pid}/dspy` — current compiled config, including `active_version`, `kind` and `pending`.
- `PUT /projects/{pid}/dspy` — save instruction / field edits (new version).
- `POST /projects/{pid}/dspy/derive` — re-derive the field schema from the template (keeps your prompt text, drops tuning state).
- `POST /projects/{pid}/dspy/test` — dry-run `{ "row_index": n }`.
- `POST /projects/{pid}/dspy/train` — `{ "optimizer": "bootstrap" | "mipro", "max_examples": n }`; stores a pending candidate.
- `POST /projects/{pid}/dspy/accept` — promote the candidate (`{ "label": "..." }` optional).
- `POST /projects/{pid}/dspy/reject` — discard the candidate.
- `GET /projects/{pid}/dspy/versions` — version history + active pointer.
- `POST /projects/{pid}/dspy/revert` — `{ "version": n }` point predictions at an older version.
- `POST /projects/{pid}/dspy/reset` — drop tuning state.
Prefill/batch (`ml-prefill`, `ml-batch`) dispatch to DSPy when the project's `ml_type` is `dspy`;
`ml_type: "external"` keeps using the classic `ml_url` POST backend.
