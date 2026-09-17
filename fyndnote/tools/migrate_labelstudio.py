"""Migrate a Label Studio export into fyndnote via the public HTTP API.

Reads a Label Studio export (JSON array of tasks, a single task object, or
JSON Lines ``.jsonl``/``.jsonls``), then recreates it in fyndnote by calling the
HTTP API only -- no database connection:

    1. upload a dataset built from ``task.data`` (one row per task, task order)
    2. create a react-live template generated from the Label Studio controls
    3. create the project (grants the target user ``project_admin``)
    4. submit every human annotation via the upserting ``/annotate`` endpoint

Label Studio annotators all collapse onto a single ``--user``. Controls fyndnote
cannot represent hard-fail with the offending tags/task ids unless
``--allow-partial`` is passed, in which case they are dropped and reported.

Two fidelity losses, both imposed by the API surface:
  * ``created_at`` / ``updated_at`` are server-side (``now()``) -- the original
    Label Studio timestamps are not preserved.
  * ``predictions[]`` are validated and counted but never written: there is no
    HTTP endpoint that inserts ``fyndnote_ml_annotations`` rows (only the
    live-ML-backend prefill path writes them), so importing them would require
    a direct DB write, which this tool deliberately avoids.

Run from the repo root::

    uv run python -m fyndnote.tools.migrate_labelstudio \\
        --input export.json --base-url http://localhost:8000 --user alice
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any
from xml.etree import ElementTree


class MigrationError(Exception):
    """Fatal, user-facing migration error."""


# --------------------------------------------------------------------------- #
# Widget contract -- mirrors frontend/src/widgets/*.tsx prop shapes.          #
# --------------------------------------------------------------------------- #
SELECT = "SelectField"
CHECKBOX = "CheckboxGroup"
TEXT = "TextField"
RATING = "RatingField"
BBOX = "BBoxField"
POLYGON = "PolygonField"
NER = "NERField"
AUDIO = "AudioSegmentField"

# Label Studio control tag -> (fyndnote widget, is self-rendering media widget)
# Self-rendering widgets paint the media (image/audio/text) themselves, so the
# generated template does not need a separate preview element for that column.
_STATIC = "static"

# Tag names fyndnote cannot represent at all.
UNMAPPABLE = {
    "timeserieslabels",
    "paragraphlabels",
    "paragraph2labels",
    "table",
    "header",
    "brushlabels",
    "all",
    "pairwise",
    "relations",
    "requirements",
}

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg")
AUDIO_EXTS = (".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus")


def _norm(v: float) -> float:
    """Label Studio stores image geometry as percent of 100 -> 0..1."""
    return round(float(v) / 100.0, 6)


# --------------------------------------------------------------------------- #
# Input parsing                                                               #
# --------------------------------------------------------------------------- #
def load_tasks(path: str) -> list[dict]:
    """Return the task list from a JSON array, single object, or JSONL file."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    if not raw.strip():
        raise MigrationError(f"input file is empty: {path}")
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return [parsed]
        if isinstance(parsed, list):
            if not parsed:
                raise MigrationError(f"input file has no tasks: {path}")
            return parsed
        raise MigrationError("expected a JSON array or object of Label Studio tasks")
    except json.JSONDecodeError:
        pass  # fall through to JSONL
    tasks: list[dict] = []
    for lineno, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MigrationError(f"{path}:{lineno}: invalid JSON line: {exc}") from exc
        if not isinstance(obj, dict):
            raise MigrationError(f"{path}:{lineno}: expected an object per line")
        tasks.append(obj)
    if not tasks:
        raise MigrationError(f"input file has no tasks: {path}")
    return tasks


def _iter_regions(task: dict, key: str):
    """Yield ``(annotation_index, result_list)`` skipping cancelled/skipped ones."""
    for ai, ann in enumerate(task.get(key) or []):
        if ann.get("was_cancelled") or ann.get("skipped"):
            continue
        result = ann.get("result")
        if not result:
            continue
        yield ai, result


# --------------------------------------------------------------------------- #
# Media-column detection                                                      #
# --------------------------------------------------------------------------- #
def _looks_media(value: Any) -> str | None:
    """Classify a data value as an 'image'/'audio' URL, else None.

    Handles Label Studio local-files storage (``/data/local-files/?d=img/a.jpg``)
    where the filename, and therefore the extension, lives in the query string.
    """
    if not isinstance(value, str) or not value:
        return None
    low = value.lower()
    path = low.split("?")[0]
    if not path.startswith(("http://", "https://", "/data/", "/static/")):
        return None
    # Extension may sit in the path or in the query (local-files storage).
    tail = low.rsplit("/", 1)[-1].split("?")[-1].split("#")[0]
    if "." not in tail and "?" in low:
        tail = low.split("?")[-1].split("=")[-1].rsplit("/", 1)[-1]
    if "." in tail:
        ext = "." + tail.rsplit(".", 1)[-1]
        if ext in AUDIO_EXTS:
            return "audio"
        if ext in IMAGE_EXTS:
            return "image"
    if "audio" in low or "sound" in low:
        return "audio"
    if "image" in low or "img" in low or "photo" in low:
        return "image"
    return None


def _column_kind(tasks: list[dict], col: str) -> str:
    """Classify a data column as 'image', 'audio', 'text' or 'scalar'.

    Any string column counts as 'text' (a short question is still content worth
    rendering); media wins over text when both appear in the column.
    """
    saw_string = False
    for t in tasks:
        v = (t.get("data") or {}).get(col)
        media = _looks_media(v)
        if media:
            return media
        if isinstance(v, str):
            saw_string = True
    return "text" if saw_string else "scalar"


# --------------------------------------------------------------------------- #
# Control plan                                                                #
# --------------------------------------------------------------------------- #
class Control:
    def __init__(
        self,
        name: str,
        widget: str,
        *,
        column: str | None = None,
        labels: list[str] | None = None,
        max_rating: int = 5,
        multiple: bool = False,
        media_kind: str | None = None,
    ):
        self.name = name
        self.widget = widget
        self.column = column
        self.labels = labels or []
        self.max_rating = max_rating
        self.multiple = multiple
        self.media_kind = media_kind  # "image" | "audio" | "text" | None


class Plan:
    def __init__(self):
        self.controls: dict[str, Control] = {}  # keyed by fyndnote field name
        self.preview_columns: list[tuple[str, str]] = []  # (column, kind) to render
        self.dropped: dict[str, set] = {}  # tag -> set of task ids


_OBJECT_TAGS = {
    "text",
    "audio",
    "audiobullets",
    "image",
    "hypertext",
    "timeseries",
    "paragraphs",
    "video",
    "chat",
    "knowledgebase",
}

_CONTROL_TAGS = {
    "choices",
    "labels",
    "taxonomy",
    "tag",
    "textarea",
    "number",
    "rating",
    "rectanglelabels",
    "rectangle",
    "polygonlabels",
    "polygon",
    "polylinelabels",
    "keypointlabels",
    "brushlabels",
    "timeserieslabels",
    "paragraphlabels",
    "paragraph2labels",
    "table",
    "header",
    "relations",
    "requirements",
    "pairwise",
}


def _parse_ls_xml(xml: str) -> dict[str, dict]:
    """Read a Label Studio labeling config into a per-control descriptor.

    Returns ``{from_name: {"tag", "toName", "multiple", "maxRating",
    "object_value", "labels"}}``. ``object_value`` is the data column the
    control's object reads (``$col`` stripped). Parses as XML, falling back to a
    lenient regex scan for configs that are not strictly well-formed.
    """
    try:
        return _parse_ls_xml_tree(xml)
    except ElementTree.ParseError:
        return _parse_ls_xml_regex(xml)


def _parse_ls_xml_tree(xml: str) -> dict[str, dict]:
    root = ElementTree.fromstring(xml.strip())
    objects: dict[str, str] = {}
    for el in root.iter():
        if el.tag.lower() in _OBJECT_TAGS and "name" in el.attrib:
            value = el.attrib.get("value", "")
            if value.startswith("$"):
                objects[el.attrib["name"]] = value[1:]

    controls: dict[str, dict] = {}
    for el in root.iter():
        tag = el.tag.lower()
        if tag not in _CONTROL_TAGS or "name" not in el.attrib:
            continue
        to_name = el.attrib.get("toName", "")
        multiple = (
            el.attrib.get("choice", "").lower() == "multiple"
            or el.attrib.get("multiple", "false").lower() == "true"
        )
        labels: list[str] = []
        for child in el:
            if child.tag.lower() not in ("choice", "label", "region", "taxonomy"):
                continue
            val = child.attrib.get("value") or child.attrib.get("label")
            if val and val not in labels:
                labels.append(val)
        try:
            max_rating = int(el.attrib.get("maxRating", 5) or 5)
        except ValueError:
            max_rating = 5
        controls[el.attrib["name"]] = {
            "tag": tag,
            "toName": to_name,
            "multiple": multiple,
            "maxRating": max_rating,
            "object_value": objects.get(to_name),
            "labels": labels,
        }
    return controls


def _parse_ls_xml_regex(xml: str) -> dict[str, dict]:
    # name -> column for object tags (<Text name="x" value="$y"/> etc.)
    objects: dict[str, str] = {}
    for m in re.finditer(
        r"<(Text|Audio|Image|HyperText|TimeSeries|Paragraphs)\b([^>]*?)/?>",
        xml,
        re.IGNORECASE,
    ):
        attrs = _xml_attrs(m.group(2))
        if "name" in attrs and attrs.get("value", "").startswith("$"):
            objects[attrs["name"]] = attrs["value"][1:]

    controls: dict[str, dict] = {}
    for m in re.finditer(
        r"<(\w+)\b([^>]*?)/?>",
        xml,
    ):
        tag = m.group(1).lower()
        if tag not in _CONTROL_TAGS:
            continue
        attrs = _xml_attrs(m.group(2))
        if "name" not in attrs:
            continue
        to_name = attrs.get("toName", "")
        controls[attrs["name"]] = {
            "tag": tag,
            "toName": to_name,
            "multiple": attrs.get("choice", "").lower() == "multiple"
            or attrs.get("multiple", "false").lower() == "true",
            "maxRating": _safe_int(attrs.get("maxRating"), 5),
            "object_value": objects.get(to_name),
            "labels": [],
        }
    return controls


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _xml_attrs(blob: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in re.finditer(r'(\w+)\s*=\s*"([^"]*)"', blob):
        out[m.group(1)] = m.group(2)
    return out


def _decide_widget(tag: str, sample_value: dict, column_kind: str | None) -> str:
    """Pick the fyndnote widget for an LS control tag, using one sampled result.

    ``column_kind`` is the media type of the object column the control points
    at; ``start``/``end`` alone do not imply audio (NER regions carry character
    offsets too), so the audio decision requires an audio column.
    """
    tag = tag.lower()
    has_span = "start" in sample_value or "end" in sample_value
    if tag in UNMAPPABLE:
        raise MigrationError(f"unmappable tag: {tag}")
    if tag == "choices":
        if column_kind == "audio" and has_span:
            return AUDIO
        multiple = (
            isinstance(sample_value.get("choices"), list)
            and len(sample_value.get("choices", [])) > 1
        )
        return CHECKBOX if multiple else SELECT
    if tag == "labels":
        if column_kind == "audio" and has_span:
            return AUDIO
        if "start" in sample_value or "end" in sample_value or "text" in sample_value:
            return NER
        multiple = (
            isinstance(sample_value.get("labels"), list)
            and len(sample_value.get("labels", [])) > 1
        )
        return CHECKBOX if multiple else SELECT
    if tag in ("taxonomy", "tag"):
        return CHECKBOX
    if tag in ("textarea", "number"):
        return TEXT
    if tag == "rating":
        return RATING
    if tag in ("rectanglelabels", "rectangle"):
        return BBOX
    if tag in ("polygonlabels", "polygon", "polylinelabels", "keypointlabels"):
        return POLYGON
    raise MigrationError(f"unmappable tag: {tag}")


def build_plan(
    tasks: list[dict],
    config_xml: str | None,
    allow_partial: bool,
    media_column: str | None = None,
) -> Plan:
    """Derive the control plan and preview columns from tasks (+ optional XML).

    Controls come from two sources: the labeling config (authoritative for tag,
    object column, label palette, multiplicity) and the annotation results
    themselves. A control declared in the config is planned even if no task
    carries a region for it; a control seen only in results is inferred.
    """
    plan = Plan()

    # Collect every control seen in results, keyed by lower-cased from_name.
    samples: dict[str, dict] = {}
    for t in tasks:
        for _ai, result in _iter_regions(t, "annotations"):
            for region in result:
                if region.get("type") == "relations":
                    continue
                from_name = region.get("from_name")
                if not from_name:
                    continue
                fn = from_name.lower()
                if fn in samples:
                    continue
                samples[fn] = {
                    "tag": (region.get("tag") or region.get("type") or "").lower(),
                    "type": (region.get("type") or "").lower(),
                    "value": region.get("value") or {},
                    "toName": region.get("to_name") or "",
                }

    ls_controls = _parse_ls_xml(config_xml) if config_xml else {}
    ls_controls = {k.lower(): v for k, v in ls_controls.items()}

    data_columns = _union_columns(tasks)
    # Config order first (it is the intended UI order), then result-only controls.
    order = list(ls_controls)
    order += [k for k in samples if k not in ls_controls]

    for fn in order:
        cfg = ls_controls.get(fn, {})
        info = samples.get(fn) or {}
        tag = (cfg.get("tag") or info.get("type") or info.get("tag") or "").lower()
        if not tag:
            continue
        sample_value = info.get("value") or {}
        if tag in UNMAPPABLE:
            if not allow_partial:
                _fail_unmappable(tag, fn, tasks)
            _record_dropped(plan, tag, tasks)
            continue
        column = cfg.get("object_value") or _infer_media_column(
            tasks,
            info.get("toName") or cfg.get("toName", ""),
            sample_value,
            data_columns,
            media_column,
        )
        kind = _column_kind(tasks, column) if column in data_columns else None
        try:
            widget = _decide_widget(tag, sample_value, kind)
        except MigrationError:
            if not allow_partial:
                _fail_unmappable(tag, fn, tasks)
            _record_dropped(plan, tag, tasks)
            continue
        if widget in (BBOX, POLYGON, NER, AUDIO) and not column:
            # The widget paints media/text itself and cannot render without it.
            if not allow_partial:
                raise MigrationError(
                    f"control '{fn}' (<{tag}>) needs the {widget} widget but no "
                    f"image/audio/text data column could be resolved from toName="
                    f"{info.get('toName') or cfg.get('toName') or '?'}. Pass "
                    f"--media-column, or --allow-partial to drop this control."
                )
            _record_dropped(plan, tag, tasks)
            continue
        labels = cfg.get("labels") or []
        if widget in (SELECT, CHECKBOX, BBOX, POLYGON, NER, AUDIO):
            labels = _merge_labels(
                labels, _collect_labels(tasks, fn, sample_value, tag)
            )
        plan.controls[fn] = Control(
            fn,
            widget,
            column=column,
            labels=labels,
            max_rating=cfg.get("maxRating", 5),
            multiple=cfg.get("multiple", False),
            media_kind=kind,
        )

    if not plan.controls:
        raise MigrationError("no annotatable controls found in the Label Studio export")

    plan.preview_columns = _preview_columns(plan, tasks, data_columns)
    return plan


def _fail_unmappable(tag: str, fn: str, tasks: list[dict]) -> None:
    ids = sorted({str(t.get("id")) for t in tasks if _task_has_tag(t, tag)})
    raise MigrationError(
        f"Label Studio control <{tag}> (field '{fn}') cannot be represented in "
        f"fyndnote. Offending task ids: {', '.join(ids) or 'n/a'}. "
        f"Re-run with --allow-partial to drop it."
    )


def _record_dropped(plan: Plan, tag: str, tasks: list[dict]) -> None:
    ids = {t.get("id") for t in tasks if _task_has_tag(t, tag)}
    plan.dropped.setdefault(tag, set()).update(x for x in ids if x is not None)


def _merge_labels(primary: list[str], extra: list[str]) -> list[str]:
    """Config palette wins; observed-only labels are appended."""
    out = list(primary)
    for x in extra:
        if x not in out:
            out.append(x)
    return out


def _task_has_tag(task: dict, tag: str) -> bool:
    tag = tag.lower()
    for key in ("annotations", "predictions"):
        for _ai, result in _iter_regions(task, key):
            for region in result:
                rtag = (region.get("tag") or region.get("type") or "").lower()
                if rtag == tag or (region.get("type") or "").lower() == tag:
                    return True
    return False


def _union_columns(tasks: list[dict]) -> list[str]:
    cols: list[str] = []
    seen = set()
    for t in tasks:
        for k in t.get("data") or {}:
            if k not in seen:
                seen.add(k)
                cols.append(k)
    return cols


def _infer_media_column(
    tasks: list[dict],
    to_name: str,
    value: dict,
    data_columns: list[str],
    hint: str | None,
) -> str | None:
    """Resolve which data column a control's object reads from.

    Precedence: explicit ``--media-column`` hint, then the LS ``toName`` object
    name (LS convention makes it equal to the data column), then a value-key
    match (``value.image``/``value.audio``/``value.text``), then the single
    unambiguous media/text column in the dataset.
    """
    if hint:
        return hint
    low = (to_name or "").lower()
    if low:
        for col in data_columns:
            if col.lower() == low:
                return col
        for col in data_columns:
            c = col.lower()
            if c.startswith(low) or low.startswith(c):
                return col
    for key in ("image", "audio", "text"):
        v = value.get(key)
        if not isinstance(v, str):
            continue
        for col in data_columns:
            if col.lower() in (key, f"{key}_url", f"{key}s", f"{key}_path"):
                return col
        for t in tasks:
            for col, tv in (t.get("data") or {}).items():
                if isinstance(tv, str) and tv == v:
                    return col
    kinds = {c: _column_kind(tasks, c) for c in data_columns}
    for want in ("image", "audio", "text"):
        hits = [c for c, k in kinds.items() if k == want]
        if len(hits) == 1:
            return hits[0]
    return None


def _collect_labels(
    tasks: list[dict], fn: str, sample_value: dict, tag: str
) -> list[str]:
    labels: list[str] = []
    seen = set()
    tag = tag.lower()

    def add(x):
        if isinstance(x, str) and x not in seen:
            seen.add(x)
            labels.append(x)

    if tag in (
        "rectanglelabels",
        "polygonlabels",
        "polylinelabels",
        "keypointlabels",
    ):
        source_keys = (
            "rectanglelabels",
            "polygonlabels",
            "polylinelabels",
            "keypointlabels",
        )
    elif tag == "labels":
        source_keys = ("labels",)
    elif tag == "choices":
        source_keys = ("choices",)
    elif tag in ("taxonomy", "tag"):
        source_keys = ("taxonomy", "tags")
    elif tag in ("textarea", "number", "rating"):
        return []
    else:
        source_keys = ()
    for t in tasks:
        for _ai, result in _iter_regions(t, "annotations"):
            for region in result:
                if (region.get("from_name") or "").lower() != fn:
                    continue
                val = region.get("value") or {}
                for sk in source_keys:
                    lst = val.get(sk)
                    if isinstance(lst, list):
                        for x in lst:
                            add(x)
    return labels


def _preview_columns(
    plan: Plan, tasks: list[dict], data_columns: list[str]
) -> list[tuple[str, str]]:
    """Columns to render as content the widgets do not themselves paint."""
    consumed = {
        c.column
        for c in plan.controls.values()
        if c.widget in (BBOX, POLYGON, NER, AUDIO)
    }
    out: list[tuple[str, str]] = []
    for col in data_columns:
        if col in consumed:
            continue
        kind = _column_kind(tasks, col)
        if kind in ("image", "audio", "text"):
            out.append((col, kind))
    return out


# --------------------------------------------------------------------------- #
# Template generation                                                         #
# --------------------------------------------------------------------------- #
def _jsx_array(labels: list[str]) -> str:
    return "[" + ", ".join(json.dumps(l) for l in labels) + "]"


def _jsx(value: str) -> str:
    return "{" + value + "}"


def render_template(plan: Plan, heading: str | None = None) -> str:
    """Generate a react-live JSX template body from the plan.

    Every widget that consumes a dataset column is guarded by a truthiness
    check on that column, mirroring the hand-written templates in
    ``frontend/src/predefinedTemplates.ts``. LS rows are sparse (an image task
    has no audio), so an unguarded widget receives ``null`` props and blows up
    react-live's render, leaving the whole preview blank.
    """
    lines: list[str] = []
    lines.append("<div style={{ padding: 20 }}>")
    title = heading or "Label Studio import"
    lines.append(f"  <h3>{title}</h3>")

    def emit(guard: str | None, body: str) -> None:
        if guard is None:
            lines.append(f"  {body}")
        else:
            lines.append(f"  {{{guard} && (")
            lines.append(f"    {body}")
            lines.append("  )}")

    for col, kind in plan.preview_columns:
        acc = f"data.{_safe(col)}"
        if kind == "image":
            emit(
                acc,
                f'<img src={_jsx(acc)} style={{{{maxWidth: "100%"}}}} />',
            )
        elif kind == "audio":
            emit(acc, f"<AudioPlayer url={_jsx(acc)} />")
        elif kind == "text":
            emit(acc, f"<p style={{{{fontSize: 16}}}}>{{{_jsx(acc)}}}</p>")

    for ctrl in plan.controls.values():
        dv = f"defaultValue={{annotations?.{_safe(ctrl.name)}}}"
        if ctrl.widget == SELECT:
            emit(
                None,
                f"<SelectField name={json.dumps(ctrl.name)} "
                f"labels={_jsx(_jsx_array(ctrl.labels))} {dv} />",
            )
        elif ctrl.widget == CHECKBOX:
            emit(
                None,
                f"<CheckboxGroup name={json.dumps(ctrl.name)} "
                f"labels={_jsx(_jsx_array(ctrl.labels))} {dv} />",
            )
        elif ctrl.widget == TEXT:
            emit(None, f"<TextField name={json.dumps(ctrl.name)} multiline {dv} />")
        elif ctrl.widget == RATING:
            emit(
                None,
                f"<RatingField name={json.dumps(ctrl.name)} "
                f"max={_jsx(str(ctrl.max_rating))} {dv} />",
            )
        elif ctrl.widget in (BBOX, POLYGON):
            widget = BBOX if ctrl.widget == BBOX else POLYGON
            src = f"data.{_safe(ctrl.column)}"
            emit(
                src,
                f"<{widget} name={json.dumps(ctrl.name)} "
                f"imageUrl={_jsx(src)} "
                f"categories={_jsx(_jsx_array(ctrl.labels))} {dv} />",
            )
        elif ctrl.widget == NER:
            src = f"data.{_safe(ctrl.column)}"
            emit(
                src,
                f"<{NER} name={json.dumps(ctrl.name)} "
                f"text={_jsx(src)} "
                f"entityTypes={_jsx(_jsx_array(ctrl.labels))} {dv} />",
            )
        elif ctrl.widget == AUDIO:
            src = f"data.{_safe(ctrl.column)}"
            emit(
                src,
                f"<{AUDIO} name={json.dumps(ctrl.name)} "
                f"url={_jsx(src)} "
                f"labels={_jsx(_jsx_array(ctrl.labels))} {dv} />",
            )
    lines.append("</div>")
    return "\n".join(lines)


def _safe(name: str) -> str:
    """Identifier fragment for brace expressions; LS names are ASCII-safe."""
    return "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in name)


# --------------------------------------------------------------------------- #
# Annotation conversion                                                       #
# --------------------------------------------------------------------------- #
def convert_annotations(
    task: dict, plan: Plan, full_texts: dict[str, str] | None = None
) -> dict[str, Any] | None:
    """Merge every human annotation of a task into one fyndnote data dict."""
    data: dict[str, Any] = {}
    text_cache = full_texts or {}
    for _ai, result in _iter_regions(task, "annotations"):
        for region in result:
            fn = (region.get("from_name") or "").lower()
            ctrl = plan.controls.get(fn)
            if ctrl is None:
                continue  # dropped control
            val = region.get("value") or {}
            _apply_region(data, ctrl, val, task, text_cache)
    return data if data else None


def _apply_region(
    data: dict, ctrl: Control, val: dict, task: dict, text_cache: dict[str, str]
) -> None:
    w = ctrl.widget
    if w == SELECT:
        for key in ("choices", "labels"):
            lst = val.get(key)
            if isinstance(lst, list) and lst:
                data[ctrl.name] = lst[0]
                return
    elif w == CHECKBOX:
        acc = data.setdefault(ctrl.name, [])
        for key in ("choices", "labels", "taxonomy", "tags"):
            lst = val.get(key)
            if isinstance(lst, list):
                for x in lst:
                    if x not in acc:
                        acc.append(x)
    elif w == TEXT:
        txt = val.get("text")
        if isinstance(txt, list) and txt:
            data[ctrl.name] = str(txt[0])
        elif "number" in val:
            data[ctrl.name] = str(val.get("number"))
    elif w == RATING:
        r = val.get("rating")
        if r is not None:
            data[ctrl.name] = float(r)
    elif w == BBOX:
        boxes = data.setdefault(ctrl.name, [])
        for cat in val.get("rectanglelabels", []) or [""]:
            boxes.append(
                {
                    "x": _norm(val.get("x", 0)),
                    "y": _norm(val.get("y", 0)),
                    "w": _norm(val.get("width", 0)),
                    "h": _norm(val.get("height", 0)),
                    "category": cat,
                }
            )
    elif w == POLYGON:
        shapes = data.setdefault(ctrl.name, [])
        pts = _polygon_points(val)
        ptype = "closed"
        if val.get("closed") is False:
            ptype = "open"
        if val.get("keypointlabels") is not None:
            ptype = "point"
        for cat in val.get(
            "polygonlabels",
            val.get("polylinelabels", val.get("keypointlabels", [""])),
        ) or [""]:
            shapes.append(
                {
                    "id": f"{ctrl.name}-{len(shapes)}",
                    "category": cat,
                    "type": ptype,
                    "points": pts,
                }
            )
    elif w == NER:
        ents = data.setdefault(ctrl.name, [])
        labels = val.get("labels") or val.get("choices") or []
        entity = labels[0] if labels else ""
        snippet = val.get("text", "")
        col = ctrl.column
        full = text_cache.get(ctrl.name) or (task.get("data") or {}).get(col, "")
        start = val.get("start")
        end = val.get("end")
        start, end = _rebaseline(full, snippet, start, end)
        ents.append({"start": start, "end": end, "entity": entity})
    elif w == AUDIO:
        segs = data.setdefault(ctrl.name, [])
        labels = val.get("labels", val.get("choices", []))
        label = labels[0] if labels else ""
        segs.append(
            {
                "start": float(val.get("start", 0)),
                "end": float(val.get("end", 0)),
                "label": label,
            }
        )


def _polygon_points(val: dict) -> list[dict]:
    raw = val.get("allpoints") or val.get("points")
    pts: list[dict] = []
    if isinstance(raw, list) and raw and isinstance(raw[0], list):
        for p in raw:
            if len(p) >= 2:
                pts.append({"x": _norm(p[0]), "y": _norm(p[1])})
    return pts


def _rebaseline(full: str, snippet: str, start, end) -> tuple[int, int]:
    """LS offsets are relative to ``value.text``; convert to full-text offsets."""
    if start is None or end is None:
        idx = full.find(snippet) if snippet else -1
        if idx < 0:
            return 0, len(snippet or "")
        return idx, idx + len(snippet)
    s, e = int(start), int(end)
    if full and 0 <= s <= e <= len(full) and full[s:e] == snippet:
        return s, e  # already absolute
    if snippet:
        idx = full.find(snippet)
        if idx >= 0:
            return idx, idx + len(snippet)
    return s, e


# --------------------------------------------------------------------------- #
# Dataset row normalization                                                   #
# --------------------------------------------------------------------------- #
def normalize_rows(tasks: list[dict], media_url_base: str | None = None) -> list[dict]:
    """Union all ``task.data`` keys; fill missing with None; stringify nestings.

    Nested dict/list values are JSON-encoded so the uploaded JSONL has one
    scalar type per column -- Hugging Face's Arrow inferrer otherwise fails on
    ragged/ heterogeneous structures. ``media_url_base`` is prepended to
    server-relative Label Studio media paths (``/data/...``) so the generated
    template can load them from a reachable host.
    """
    cols = _union_columns(tasks)
    base = (media_url_base or "").rstrip("/")
    rows: list[dict] = []
    for t in tasks:
        d = t.get("data") or {}
        row: dict[str, Any] = {}
        for c in cols:
            v = d.get(c)
            if isinstance(v, (dict, list)):
                v = json.dumps(v)
            if base and isinstance(v, str) and v.startswith("/data/"):
                v = base + v
            row[c] = v
        rows.append(row)
    return rows


def validate_predictions(tasks: list[dict], plan: Plan) -> tuple[int, int]:
    """Count prediction regions that map to a planned control vs. those that do not."""
    mapped = unmapped = 0
    for t in tasks:
        for _ai, result in _iter_regions(t, "predictions"):
            for region in result:
                fn = (region.get("from_name") or "").lower()
                if fn in plan.controls:
                    mapped += 1
                else:
                    unmapped += 1
    return mapped, unmapped


# --------------------------------------------------------------------------- #
# HTTP client                                                                 #
# --------------------------------------------------------------------------- #
class Client:
    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
        session=None,
    ):
        self.base = base_url.rstrip("/") + "/api/v1"
        self.timeout = timeout
        if session is None:
            import requests

            session = requests.Session()
        self.session = session

    def _request(self, method: str, path: str, **kw):
        kw.setdefault("timeout", self.timeout)
        resp = self.session.request(method, self.base + path, **kw)
        if resp.status_code >= 400:
            detail = _detail(resp)
            raise MigrationError(f"{method} {path} -> {resp.status_code}: {detail}")
        return resp

    def check_user(self, user_id: str) -> None:
        resp = self.session.post(
            self.base + "/auth/login", json={"user_id": user_id}, timeout=self.timeout
        )
        if resp.status_code == 401:
            raise MigrationError(
                f"user '{user_id}' does not exist (POST /auth/login 401)"
            )
        if resp.status_code >= 400:
            raise MigrationError(f"user check failed: {_detail(resp)}")

    def upload_dataset(self, filename: str, content: bytes) -> str:
        """Upload the export; a re-run adopts a suffixed name instead of failing."""
        resp = self._post_upload(filename, content)
        if resp.status_code == 409:
            # Importing the same export twice: the display name is taken, and
            # aborting here would leave a half-created project behind.
            suggested = _suggested_name(resp)
            if not suggested:
                raise MigrationError(f"POST /datasets/upload -> 409: {_detail(resp)}")
            resp = self._post_upload(filename, content, alias=suggested)
        if resp.status_code >= 400:
            raise MigrationError(
                f"POST /datasets/upload -> {resp.status_code}: {_detail(resp)}"
            )
        return resp.json()["id"]

    def _post_upload(self, filename: str, content: bytes, alias: str | None = None):
        return self.session.post(
            self.base + "/datasets/upload",
            files={"file": (filename, content, "application/x-ndjson")},
            data={"alias": alias} if alias else None,
            timeout=self.timeout,
        )

    def create_template(self, name: str, source: str) -> str:
        resp = self._request(
            "POST",
            "/templates",
            json={"name": name, "source": source, "validated": False},
        )
        return resp.json()["id"]

    def create_project(
        self,
        name: str,
        dataset_id: str,
        template_id: str,
        user_id: str,
        color: str,
        instructions: str,
    ) -> str:
        body = {
            "name": name,
            "dataset_id": dataset_id,
            "template_id": template_id,
            "color": color,
            "tags": "",
            "instructions": instructions,
            "ml_enabled": False,
            "ml_url": "",
            "ml_annotator": "",
            "ml_mode": "on_navigate",
            "user_id": user_id,
        }
        resp = self._request("POST", "/projects", json=body)
        return resp.json()["id"]

    def annotate(self, pid: str, row_index: int, user_id: str, data: dict) -> None:
        self._request(
            "POST",
            f"/projects/{pid}/annotate",
            json={"row_index": row_index, "user_id": user_id, "data": data},
        )


def _detail(resp) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])
        return str(body)
    except (ValueError, AttributeError):
        return getattr(resp, "text", "?")


def _suggested_name(resp) -> str | None:
    """The free display name offered by a 409 body, when the server sent one."""
    try:
        detail = resp.json().get("detail")
    except (ValueError, AttributeError):
        return None
    return detail.get("suggested_name") if isinstance(detail, dict) else None


# --------------------------------------------------------------------------- #
# Orchestration                                                               #
# --------------------------------------------------------------------------- #
def _config_xml(args) -> str | None:
    if not getattr(args, "config", None):
        return None
    with open(args.config, "r", encoding="utf-8") as fh:
        raw = fh.read().strip()
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return obj.get("labeling") or obj.get("labeling_settings")
    except json.JSONDecodeError:
        pass
    return raw  # caller passed the XML directly


def migrate(args, client: Client | None = None) -> dict:
    tasks = load_tasks(args.input)
    plan = build_plan(tasks, _config_xml(args), args.allow_partial, args.media_column)
    template_src = render_template(plan)
    rows = normalize_rows(tasks, args.media_url_base)

    summary = {
        "tasks": len(tasks),
        "controls": {c.name: c.widget for c in plan.controls.values()},
        "dropped": {k: sorted(str(x) for x in v) for k, v in plan.dropped.items()},
        "predictions": sum(
            len(p or []) for t in tasks for p in (t.get("predictions"),)
        ),
        "annotations": 0,
        "skipped_annotations": 0,
        "project_id": None,
        "template_id": None,
        "dataset_id": None,
    }
    if args.report_predictions:
        mapped, unmapped = validate_predictions(tasks, plan)
        summary["predictions_mapped"] = mapped
        summary["predictions_unmapped"] = unmapped

    if args.dry_run:
        converted = [convert_annotations(t, plan) for t in tasks]
        summary["annotations"] = sum(1 for a in converted if a)
        summary["skipped_annotations"] = len(tasks) - summary["annotations"]
        summary["dry_run"] = True
        summary["template"] = template_src
        summary["first_annotation"] = next((a for a in converted if a), None)
        summary["rows"] = len(rows)
        return summary

    client = client or Client(base_url=args.base_url, timeout=args.timeout)
    client.check_user(args.user)

    jsonl = "\n".join(json.dumps(r) for r in rows).encode("utf-8")
    ds_name = (args.dataset_name or args.project_name or "labelstudio").rsplit(
        ".json", 1
    )[0]
    summary["dataset_id"] = client.upload_dataset(f"{ds_name}.jsonl", jsonl)
    summary["template_id"] = client.create_template(args.project_name, template_src)
    summary["project_id"] = client.create_project(
        args.project_name,
        summary["dataset_id"],
        summary["template_id"],
        args.user,
        args.color,
        args.instructions,
    )

    for idx, t in enumerate(tasks):
        ann = convert_annotations(t, plan)
        if ann is None:
            summary["skipped_annotations"] += 1
            continue
        client.annotate(summary["project_id"], idx, args.user, ann)
        summary["annotations"] += 1
    return summary


def _print_summary(s: dict) -> None:
    dry = bool(s.get("dry_run"))
    rows_label = "rows to upload" if dry else "tasks uploaded"
    ann_label = "annotations planned" if dry else "annotations written"
    print("Label Studio -> fyndnote migration" + ("  (dry run)" if dry else ""))
    print(f"  {rows_label:<21}: {s['tasks']}")
    print(f"  {ann_label:<21}: {s['annotations']}")
    print(f"  {'tasks w/o annotation':<21}: {s['skipped_annotations']}")
    pred = (
        f"  {'predictions reported':<21}: {s['predictions']} "
        "(not imported: no HTTP write endpoint)"
    )
    if "predictions_mapped" in s:
        pred += (
            f" [{s['predictions_mapped']} mappable / "
            f"{s['predictions_unmapped']} unmappable]"
        )
    print(pred)
    if s["dropped"]:
        for tag, ids in s["dropped"].items():
            print(
                f"  dropped <{tag}> from {len(ids)} task(s): {', '.join(ids[:10])}{' ...' if len(ids) > 10 else ''}"
            )
    print("  controls:")
    for name, widget in s["controls"].items():
        print(f"    {name} -> {widget}")
    if s.get("dry_run"):
        print("\n--- generated template ---")
        print(s["template"])
        print("--- first annotation ---")
        print(json.dumps(s["first_annotation"], indent=2, ensure_ascii=False))
    else:
        print(f"  dataset_id  : {s['dataset_id']}")
        print(f"  template_id : {s['template_id']}")
        print(f"  project_id  : {s['project_id']}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="migrate_labelstudio",
        description="Import a Label Studio export into fyndnote over HTTP.",
    )
    p.add_argument(
        "--input",
        required=True,
        help="Label Studio export (.json array or .jsonl/.jsonls)",
    )
    p.add_argument(
        "--base-url", default="http://localhost:8000", help="fyndnote API base URL"
    )
    p.add_argument(
        "--user",
        required=True,
        help="fyndnote user_id all annotations are attributed to",
    )
    p.add_argument(
        "--project-name",
        default=None,
        help="project name (default: input filename stem)",
    )
    p.add_argument("--dataset-name", default=None, help="dataset upload filename stem")
    p.add_argument(
        "--config",
        default=None,
        help="Label Studio project JSON (with labeling XML) or raw XML",
    )
    p.add_argument("--color", default="#1976d2")
    p.add_argument("--instructions", default="")
    p.add_argument(
        "--allow-partial",
        action="store_true",
        help="drop unmappable controls instead of hard-failing",
    )
    p.add_argument(
        "--report-predictions",
        action="store_true",
        help="validate and count predictions[] in the summary",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print the plan, template and first annotation without POSTing",
    )
    p.add_argument(
        "--media-column", default=None, help="data column holding image/audio URLs"
    )
    p.add_argument(
        "--media-url-base", default=None, help="prefix for relative /data/ media paths"
    )
    p.add_argument("--timeout", type=float, default=30.0)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.project_name is None:
        import os

        args.project_name = os.path.splitext(os.path.basename(args.input))[0]
    try:
        summary = migrate(args)
    except MigrationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
