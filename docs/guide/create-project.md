# Admin: Create a Project

Creating a project is a four-part workflow: **load a dataset**, **pick or edit a template**, **configure the project**, then **create it**.

## 1. Load a dataset

Datasets can come from several sources. The "Load New" dialog in the setup view accepts a source string or a file upload:

- **Hugging Face** — e.g. `stanfordnlp/imdb`, `split=train`.
- **HTTP URL** — a `.csv`, `.json`, `.jsonl`, or `.parquet` file.
- **Local file** — a `file://` path to a supported file or directory.
- **Browser upload** — upload a `.csv`, `.json`, `.jsonl`, or `.parquet` file directly.

Supported formats: `.csv`, `.json`, `.jsonl`, `.parquet`. After loading, the dataset appears in the list with its row count and columns.

## 2. Pick or edit a template

Choose an existing template or edit one. Templates are restricted React component source rendered in a `react-live` sandbox. They contain the widgets that annotators will use. Templates are grouped by modality (e.g. NLP, image, audio) and can be previewed live before saving.

## 3. Configure the project

Give the project a name and optionally set:

- **Color** — a project accent color.
- **Tags** — comma-separated tags for organizing projects.
- **Instructions** — guidance shown to annotators.
- **AI prefill** — enable an optional AI backend (see [AI Prefill](/guide/ai-prefill)).

## 4. Create

Save the project. It now appears in the project list with its progress. Click **Label** to start annotating rows.

## Screenshot

> **Screenshot needed:** capture the setup view — the "Load New" dialog, the template picker, and the project-name/color/tags/instructions form.

![Setup view](../public/images/setup.png)
