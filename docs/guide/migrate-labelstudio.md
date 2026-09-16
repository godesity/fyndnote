# Import from Label Studio

`fyndnote migrate` imports a **Label Studio export** and recreates it inside
fyndnote: one dataset (a row per task, in task order), one generated template,
one project, and every human annotation.

It talks to a running server **over the HTTP API only** — it never opens the
database. Point it at any fyndnote instance you can reach.

## Quick start

```bash
# start a server (if you do not already have one)
fyndnote serve --port 8000

# import
fyndnote migrate --input export.json --user alice --project-name my-import
```

Equivalent as a module, from a source checkout:

```bash
uv run python -m fyndnote.tools.migrate_labelstudio \
    --input export.json --base-url http://localhost:8000 --user alice
```

With `fyndnote migrate`, `--base-url` defaults to the `--host`/`--port` you pass
(so `fyndnote migrate --input export.json --user alice --port 8000` just works).

## Input format

A Label Studio export in either shape:

- a **JSON array** of tasks (`export.json`)
- **JSON Lines** (`.jsonl` / `.jsonls`)

Each task needs `data` (the row content) and optionally `annotations[]` /
`predictions[]`. Exports that embed `json+metrics` or CSV payloads are not
supported.

## Flags

| Flag | Meaning |
| --- | --- |
| `--input` | Label Studio export (required) |
| `--user` | fyndnote user every imported annotation is attributed to (required) |
| `--base-url` | server base URL (default `http://localhost:8000`; under `fyndnote migrate` it follows `--host`/`--port`) |
| `--project-name` | project name (default: input filename stem) |
| `--dataset-name` | dataset upload filename stem |
| `--config` | Label Studio labeling config — project JSON (its `labeling` key) or raw XML |
| `--color` | project colour (default `#1976d2`) |
| `--instructions` | project instructions text |
| `--allow-partial` | drop unsupported controls instead of failing |
| `--report-predictions` | validate and count `predictions[]` in the summary |
| `--dry-run` | print the plan, generated template and first annotation without POSTing |
| `--media-column` | force which data column holds image/audio URLs |
| `--media-url-base` | prefix added to `/data/...` media paths so the browser can load them |
| `--timeout` | per-request timeout in seconds (default 30) |

Always start with `--dry-run`: it shows the generated template and the first
converted annotation before anything is written.

## Provide the labeling config

`--config` is optional but strongly recommended. Without it the tool infers
controls from the annotation results it can see, which loses label options that
no annotator ever picked and cannot know about controls nobody used. With it,
the config is authoritative for the tag, the object column (`$text`,
`$image_url`, …), the label palette and `choice="multiple"` / `maxRating`.

```bash
fyndnote migrate --input export.json --user alice --config project.json
```

## Control mapping

| Label Studio control | fyndnote widget | stored value |
| --- | --- | --- |
| `Choices` (single), `Labels` (single) | `SelectField` | `string` |
| `Choices` (multiple), `Labels` (multiple), `Taxonomy`, `Tag` | `CheckboxGroup` | `string[]` |
| `TextArea`, `Number` | `TextField` | `string` |
| `Rating` | `RatingField` | `number` |
| `RectangleLabels`, `Rectangle` | `BBoxField` | `[{x,y,w,h,category}]`, normalized 0–1 |
| `PolygonLabels`, `Polygon`, `PolyLineLabels`, `KeyPointLabels` | `PolygonField` | `[{id,category,type,points}]`, normalized 0–1 |
| `Labels` / `Choices` on text | `NERField` | `[{start,end,entity}]`, absolute character offsets |
| `Choices` / `Labels` on audio with `start`/`end` | `AudioSegmentField` | `[{start,end,label}]` seconds |

Label Studio stores image geometry as percentages of 100; they are divided by
100 so the fyndnote widgets receive 0–1 coordinates. NER offsets are re-based
against the full text column, because Label Studio stores them relative to the
selected snippet.

Controls fyndnote cannot represent at all — `TimeSeriesLabels`,
`ParagraphLabels`, `Paragraph2Labels`, `Table`, `Header`, `BrushLabels`, `All`,
`Pairwise`, `Relations`, `Requirements` — abort the run with the offending tag
and task ids. Pass `--allow-partial` to drop them and continue; the summary
lists what was dropped.

## What is not imported

Two things are lost, both because no HTTP endpoint exists for them:

- **Timestamps.** `/annotate` stamps `created_at`/`updated_at` server-side, so
  the original Label Studio times are not preserved.
- **ML predictions.** `predictions[]` are counted, and validated against the
  plan with `--report-predictions`, but never written — fyndnote only populates
  its AI store from a live ML backend, so importing them would require a direct
  database write, which this tool deliberately avoids.

Every Label Studio annotator is also collapsed onto the single `--user`, and
`annotations[]` with `was_cancelled` (or empty `result`) are skipped.

## Media URLs

Image/audio columns are detected from the values, including Label Studio's
local-files storage form (`/data/local-files/?d=img/photo.jpg`). Those paths
resolve against the *Label Studio* host, so pass `--media-url-base` to rewrite
them into something the fyndnote browser can reach:

```bash
fyndnote migrate --input export.json --user alice \
    --media-url-base http://labelstudio.internal:8080
```

If detection picks the wrong column, override it with `--media-column image_url`.
