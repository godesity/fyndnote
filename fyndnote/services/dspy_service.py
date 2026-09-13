"""DSPy ML backend: prompt-optimized LLM annotation programs.

Program/prompt state lives in a per-project JSON file under DSPY_DIR
(mirroring the file-based TemplateService pattern). The `dspy` package is
imported lazily so the app boots without the optional extra installed.
"""

import hashlib
import json
import re
import threading
from datetime import UTC, datetime
from pathlib import Path

from ..config import DSPY_DEFAULT_MODEL, DSPY_DIR, LLM_API_BASE, LLM_API_KEY
from .dataset_service import DatasetService
from .template_service import TemplateService

# Every configure+call section is serialized on one module-level lock
# (dspy.configure() mutates global state).
_LM_LOCK = threading.Lock()

DEFAULT_INSTRUCTION = (
    "Given the fields below, produce the annotation values for each output field."
)

VALID_ML_TYPES = ("external", "dspy")
VALID_OPTIMIZERS = ("mipro", "bootstrap")


class DspyNotConfigured(Exception):
    """LLM endpoint credentials are missing (→ 400 from the router)."""


# ---------------------------------------------------------------------------
# dspy lazy import
# ---------------------------------------------------------------------------


def _require_dspy():
    try:
        import dspy
    except ImportError as e:  # pragma: no cover - env-dependent
        raise RuntimeError(
            "dspy extra not installed — run: pip install fyndnote[dspy]"
        ) from e
    return dspy


# ---------------------------------------------------------------------------
# Program store (file-based, one JSON per project)
# ---------------------------------------------------------------------------


class DspyProgramStore:
    @staticmethod
    def _path(pid: str) -> Path:
        return DSPY_DIR / f"{pid}.json"

    @classmethod
    def get(cls, pid: str) -> dict | None:
        path = cls._path(pid)
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    @classmethod
    def save(cls, pid: str, cfg: dict) -> dict:
        DSPY_DIR.mkdir(parents=True, exist_ok=True)
        with open(cls._path(pid), "w") as f:
            json.dump(cfg, f, indent=2)
        return cfg

    @classmethod
    def delete(cls, pid: str) -> None:
        cls._path(pid).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Schema derivation from the react-live template (pure; no dspy import)
# ---------------------------------------------------------------------------

_WIDGET_RE = re.compile(
    r"<(SelectField|CheckboxGroup|RatingField|TextField|NERField|BBoxField|"
    r"PolygonField|AudioSegmentField)\b([^>]*)>"
)
_NAME_RE = re.compile(r'name\s*=\s*"([^"]+)"')
_LABELS_RE = re.compile(r"labels\s*=\s*\{\s*\[([^\]]*)\]")
_ENTITY_RE = re.compile(r"entityTypes\s*=\s*\{\s*\[([^\]]*)\]")
_MAX_RE = re.compile(r"max\s*=\s*\{\s*(\d+)\s*\}")
_STR_RE = re.compile(r'"([^"]+)"')
_DATA_COL_RE = re.compile(r"data\.([a-zA-Z_]\w*)")

_UNSUPPORTED_WIDGETS = ("BBoxField", "PolygonField", "AudioSegmentField")


def _bracket_strings(rx: re.Pattern, attrs: str) -> list[str]:
    m = rx.search(attrs)
    return _STR_RE.findall(m.group(1)) if m else []


def _safe_field_name(name: str) -> str:
    # dspy field names must be valid Python identifiers.
    if re.fullmatch(r"[A-Za-z_]\w*", name):
        return name
    return "col_" + re.sub(r"\W", "_", name)


def derive_config(template_source: str, dataset_columns: list[str]) -> dict:
    """Derive the DSPy program config (prompt + I/O schema) from a template."""
    output_fields: list[dict] = []
    for widget, attrs in _WIDGET_RE.findall(template_source or ""):
        name_m = _NAME_RE.search(attrs)
        if not name_m:
            continue
        name = name_m.group(1)
        if widget in _UNSUPPORTED_WIDGETS:
            output_fields.append(
                {
                    "name": name,
                    "source": name,
                    "kind": "unsupported",
                    "desc": "",
                    "options": [],
                    "max": None,
                    "enabled": False,
                }
            )
        elif widget == "SelectField":
            options = _bracket_strings(_LABELS_RE, attrs)
            desc = f"{name}: one of " + ", ".join(f"'{o}'" for o in options)
            output_fields.append(
                {
                    "name": name,
                    "source": name,
                    "kind": "select",
                    "desc": desc,
                    "options": options,
                    "max": None,
                    "enabled": True,
                }
            )
        elif widget == "CheckboxGroup":
            options = _bracket_strings(_LABELS_RE, attrs)
            desc = f"{name}: one or more of " + ", ".join(f"'{o}'" for o in options)
            output_fields.append(
                {
                    "name": name,
                    "source": name,
                    "kind": "multiselect",
                    "desc": desc,
                    "options": options,
                    "max": None,
                    "enabled": True,
                }
            )
        elif widget == "RatingField":
            max_m = _MAX_RE.search(attrs)
            mx = int(max_m.group(1)) if max_m else 5
            output_fields.append(
                {
                    "name": name,
                    "source": name,
                    "kind": "rating",
                    "desc": f"score 1..{mx}",
                    "options": [],
                    "max": mx,
                    "enabled": True,
                }
            )
        elif widget == "TextField":
            output_fields.append(
                {
                    "name": name,
                    "source": name,
                    "kind": "text",
                    "desc": "",
                    "options": [],
                    "max": None,
                    "enabled": True,
                }
            )
        elif widget == "NERField":
            entities = _bracket_strings(_ENTITY_RE, attrs)
            ent_str = ", ".join(f"'{e}'" for e in entities)
            output_fields.append(
                {
                    "name": name,
                    "source": name,
                    "kind": "ner",
                    "desc": (
                        f"{name}: entities as JSON list of "
                        f"{{start,end,entity}} with entity in {ent_str}"
                    ),
                    "options": entities,
                    "max": None,
                    "enabled": True,
                }
            )

    # De-duplicate output fields by name (last wins keeps source order stable
    # for first occurrence).
    seen: dict[str, dict] = {}
    deduped: list[dict] = []
    for f in output_fields:
        if f["name"] in seen:
            deduped[deduped.index(seen[f["name"]])] = f
            seen[f["name"]] = f
        else:
            seen[f["name"]] = f
            deduped.append(f)
    output_fields = deduped

    cols = set(dataset_columns or [])
    input_fields: list[dict] = []
    seen_inputs: set[str] = set()
    for col in _DATA_COL_RE.findall(template_source or ""):
        if col not in cols or col in seen_inputs:
            continue
        seen_inputs.add(col)
        input_fields.append(
            {
                "name": _safe_field_name(col),
                "source": col,
                "desc": "",
            }
        )

    return {
        "version": 1,
        "instruction": DEFAULT_INSTRUCTION,
        "input_fields": input_fields,
        "output_fields": output_fields,
        "program_state": None,
        "tuned_at": None,
        "train_metrics": None,
        "n_demos": 0,
        "derived_from": hashlib.sha256((template_source or "").encode()).hexdigest(),
    }


# ---------------------------------------------------------------------------
# Project/template/dataset helpers
# ---------------------------------------------------------------------------


def _project_or_none(pid: str) -> dict | None:
    from .annotation_service import AnnotationService  # lazy: avoids import cycle

    return AnnotationService.get_project(pid)


def _ensure_config(
    pid: str, project: dict | None = None
) -> tuple[dict, dict] | tuple[None, None]:
    """Return (project, cfg), auto-deriving + saving cfg when absent."""
    if project is None:
        project = _project_or_none(pid)
    if not project:
        return None, None
    cfg = DspyProgramStore.get(pid)
    if cfg is None:
        # Derivation needs template_id; the caller's dict may be the lean
        # _get_project_settings shape, so re-read the full row.
        full = _project_or_none(pid) or project
        template = TemplateService.get(full["template_id"])
        source = template["source"] if template else ""
        try:
            columns = list(DatasetService._load_ds(full["dataset_id"]).column_names)
        except Exception:
            columns = []
        cfg = derive_config(source, columns)
        DspyProgramStore.save(pid, cfg)
    return project, cfg


# ---------------------------------------------------------------------------
# Program / LM construction (dspy 2.6+ / 3.x API)
# ---------------------------------------------------------------------------


def _output_type(kind: str):
    if kind == "multiselect":
        return list[str]
    if kind == "rating":
        return int
    if kind == "ner":
        return list[dict]
    return str


def _enabled(cfg: dict, key: str) -> list[dict]:
    # Derived input fields carry no explicit "enabled" key → enabled by default.
    return [f for f in cfg.get(key, []) if f.get("enabled", True)]


def _build_program(cfg: dict):
    dspy = _require_dspy()
    fields: dict[str, tuple] = {}
    for f in _enabled(cfg, "input_fields"):
        fields[f["name"]] = (str, dspy.InputField(desc=f.get("desc") or f["name"]))
    outputs = _enabled(cfg, "output_fields")
    if not outputs:
        raise ValueError("no enabled output fields — enable at least one field")
    for f in outputs:
        fields[f["name"]] = (
            _output_type(f["kind"]),
            dspy.OutputField(desc=f.get("desc") or f["name"]),
        )
    signature = dspy.Signature(fields).with_instructions(
        cfg.get("instruction") or DEFAULT_INSTRUCTION
    )
    program = dspy.Predict(signature)
    if cfg.get("program_state"):
        # load_state overwrites instruction/descriptions from the stored
        # state — the PUT handler keeps that state in sync with user edits.
        try:
            program.load_state(json.loads(json.dumps(cfg["program_state"])))
        except Exception:
            pass  # stale/incompatible state → fall back to the built signature
    return program


def _lm_scope(project: dict):
    """dspy.context() with this project's LM.

    dspy.configure() is bound to the thread that first called it (uvicorn
    rotates worker threads) — dspy.context() works from any thread.
    """
    dspy = _require_dspy()
    if not LLM_API_KEY:
        raise DspyNotConfigured("FYNDNOTE_LLM_API_KEY is not set")
    model = project.get("dspy_model") or DSPY_DEFAULT_MODEL
    api_base = project.get("dspy_api_base") or LLM_API_BASE or None
    lm = dspy.LM(model=model, api_base=api_base, api_key=LLM_API_KEY)
    return dspy.context(lm=lm)


# ---------------------------------------------------------------------------
# Coercion
# ---------------------------------------------------------------------------


def _coerce(field: dict, value):
    kind = field["kind"]
    if kind == "select":
        return str(value) if value is not None else ""
    if kind == "text":
        return str(value) if value is not None else ""
    if kind == "multiselect":
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, list):
            return [str(v) for v in value]
        return []
    if kind == "rating":
        mx = field.get("max") or 5
        try:
            v = int(value)
        except (TypeError, ValueError):
            v = 1
        return max(1, min(mx, v))
    if kind == "ner":
        return value if isinstance(value, list) else []
    return value


# ---------------------------------------------------------------------------
# Predict
# ---------------------------------------------------------------------------


def predict(project: dict, row: dict) -> dict | None:
    """Run the project's DSPy program on one dataset row.

    Same failure contract as ml_service.call_ml_backend: None on any error.
    """
    try:
        pid = project["id"]
        _, cfg = _ensure_config(pid, project)
        if cfg is None:
            return None
        inputs = {
            f["name"]: str(row.get(f["source"], ""))
            for f in _enabled(cfg, "input_fields")
        }
        outs = _enabled(cfg, "output_fields")
        with _LM_LOCK, _lm_scope(project):
            program = _build_program(cfg)
            result = program(**inputs)
        annotation = {}
        for f in outs:
            raw = getattr(result, f["name"], None)
            if raw is None and isinstance(result, dict):
                raw = result.get(f["name"])
            annotation[f["name"]] = _coerce(f, raw)
        return annotation
    except Exception:
        return None


def test_predict(pid: str, row_index: int) -> dict:
    """Dry-run predict (no fyndnote_ml_annotations write); raises on failure."""
    project, cfg = _ensure_config(pid)
    if cfg is None:
        raise ValueError("project not found")
    inputs = {
        f["name"]: str(
            DatasetService.get_row(project["dataset_id"], row_index).get(
                f["source"], ""
            )
        )
        for f in _enabled(cfg, "input_fields")
    }
    outs = _enabled(cfg, "output_fields")
    with _LM_LOCK, _lm_scope(project):
        program = _build_program(cfg)
        result = program(**inputs)
    annotation = {}
    fields_out = []
    for f in outs:
        raw = getattr(result, f["name"], None)
        if raw is None and isinstance(result, dict):
            raw = result.get(f["name"])
        value = _coerce(f, raw)
        annotation[f["name"]] = value
        fields_out.append(
            {
                "name": f["name"],
                "desc": f.get("desc", ""),
                "kind": f["kind"],
                "value": value,
            }
        )
    return {
        "inputs": inputs,
        "fields": fields_out,
        "annotation": annotation,
        "instruction": cfg.get("instruction"),
        "tuned": cfg.get("program_state") is not None,
    }


# ---------------------------------------------------------------------------
# Tuning
# ---------------------------------------------------------------------------


def _extract_examples(pid: str, cfg: dict) -> list[tuple[int, dict, dict]]:
    """(row_index, inputs, outputs) per usable human-annotated row."""
    from ..database import get_db

    project = _project_or_none(pid)
    input_fields = _enabled(cfg, "input_fields")
    output_fields = _enabled(cfg, "output_fields")
    out_names = [f["name"] for f in output_fields]

    db = get_db()
    rows = db.execute(
        "SELECT row_index, data, updated_at FROM fyndnote_annotations "
        "WHERE project_id = ? ORDER BY row_index",
        (pid,),
    ).fetchall()
    db.close()

    # Dedupe per row_index keeping the newest updated_at.
    latest: dict[int, dict] = {}
    for r in rows:
        cur = latest.get(r["row_index"])
        if cur is None or (r["updated_at"] or "") >= (cur["updated_at"] or ""):
            latest[r["row_index"]] = r

    examples = []
    for row_index in sorted(latest):
        try:
            ann = json.loads(latest[row_index]["data"])
        except (TypeError, ValueError):
            continue
        if not isinstance(ann, dict):
            continue
        if any(name not in ann for name in out_names):
            continue  # missing any enabled output field → unusable for tuning
        try:
            row = DatasetService.get_row(project["dataset_id"], row_index)
        except Exception:
            continue
        inputs = {f["name"]: str(row.get(f["source"], "")) for f in input_fields}
        outputs = {f["name"]: _coerce(f, ann[f["name"]]) for f in output_fields}
        examples.append((row_index, inputs, outputs))
    return examples


def _make_metric(cfg: dict):
    output_fields = _enabled(cfg, "output_fields")

    def _eq(field, gold, pred):
        kind = field["kind"]
        if kind == "multiselect":
            g = sorted(
                str(x) for x in (gold if isinstance(gold, list) else [gold]) if x
            )
            p = sorted(
                str(x) for x in (pred if isinstance(pred, list) else [pred]) if x
            )
            return g == p
        if kind == "ner":
            return json.dumps(gold, sort_keys=True) == json.dumps(pred, sort_keys=True)
        return str(gold) == str(pred)

    def metric(gold, pred, trace=None) -> float:
        if not output_fields:
            return 0.0
        hits = 0
        for f in output_fields:
            try:
                g = getattr(gold, f["name"], None)
                if g is None and isinstance(gold, dict):
                    g = gold.get(f["name"])
                p = getattr(pred, f["name"], None)
                if p is None and isinstance(pred, dict):
                    p = pred.get(f["name"])
                if _eq(f, g, p):
                    hits += 1
            except Exception:
                pass
        return hits / len(output_fields)

    return metric


def tune(pid: str, optimizer: str = "mipro", max_examples: int = 50) -> dict:
    """Prompt-optimize the project's program against human annotations."""
    dspy = _require_dspy()
    if optimizer not in VALID_OPTIMIZERS:
        raise ValueError(
            f"unknown optimizer '{optimizer}' — use 'mipro' or 'bootstrap'"
        )
    project, cfg = _ensure_config(pid)
    if cfg is None:
        raise ValueError("project not found")

    examples = _extract_examples(pid, cfg)[: max(1, max_examples)]
    if len(examples) < 3:
        raise ValueError("need at least 3 annotated rows to tune")

    input_names = [f["name"] for f in _enabled(cfg, "input_fields")]
    dspy_examples = [
        dspy.Example(**inputs, **outputs).with_inputs(*input_names)
        for _, inputs, outputs in examples
    ]
    split = max(1, int(len(dspy_examples) * 0.7))
    train, val = dspy_examples[:split], dspy_examples[split:]
    if not val:  # tiny trainsets: keep one example out for scoring
        val = [train.pop()]
        if not train:
            raise ValueError("need at least 3 annotated rows to tune")

    metric = _make_metric(cfg)
    with _LM_LOCK, _lm_scope(project):
        program = _build_program(cfg)
        if optimizer == "bootstrap":
            opt = dspy.BootstrapFewShot(
                metric=metric,
                max_bootstrapped_demos=4,
                max_labeled_demos=min(16, len(train)),
            )
            compiled = opt.compile(program, trainset=train)
        else:
            opt = dspy.MIPROv2(metric=metric, auto="light")
            compiled = opt.compile(
                program,
                trainset=train,
                valset=val,
                requires_permission_to_run=False,
            )
        score = sum(metric(ex, compiled(**ex.inputs()), None) for ex in val) / len(val)
        state = compiled.dump_state()
        demos = getattr(compiled, "demos", None) or []
        instruction = _extract_instructions(compiled, cfg.get("instruction"))

    cfg["instruction"] = instruction
    cfg["program_state"] = state
    cfg["tuned_at"] = datetime.now(UTC).isoformat()
    cfg["train_metrics"] = {
        "score": score,
        "optimizer": optimizer,
        "train_size": len(train),
        "val_size": len(val),
    }
    cfg["n_demos"] = len(demos)
    DspyProgramStore.save(pid, cfg)

    return {
        "status": "ok",
        "score": score,
        "n_demos": len(demos),
        "instruction": instruction,
        "optimizer": optimizer,
        "train_size": len(train),
        "val_size": len(val),
    }


def _extract_instructions(compiled, fallback: str) -> str:
    """Walk a compiled program for its (possibly optimized) instructions."""
    try:
        state = compiled.dump_state()
        sig = state.get("signature") if isinstance(state, dict) else None
        if isinstance(sig, dict) and sig.get("instructions"):
            return sig["instructions"]
    except Exception:
        pass
    for attr in ("prog_1", "predict", "program", "signature"):
        node = getattr(compiled, attr, None)
        sig = getattr(node, "signature", None) or (
            node if attr == "signature" else None
        )
        instr = getattr(sig, "instructions", None)
        if isinstance(instr, str) and instr.strip():
            return instr
    return fallback


# ---------------------------------------------------------------------------
# Program-state <-> user-edit sync (PUT handler helper)
# ---------------------------------------------------------------------------


def rewrite_state(cfg: dict) -> dict:
    """Keep cfg['program_state'] honoring user edits to instruction/descs.

    load_state overwrites the built signature from stored state, so edits to
    instruction/field descriptions must be mirrored into that state. If the
    stored state's shape no longer matches the enabled fields (field toggled),
    rebuild the state from cfg, preserving demos.
    """
    state = cfg.get("program_state")
    if not state:
        return cfg
    try:
        fields_desc = [
            f.get("desc") or f["name"] for f in _enabled(cfg, "input_fields")
        ] + [f.get("desc") or f["name"] for f in _enabled(cfg, "output_fields")]
        sig = state.get("signature")
        stored = sig.get("fields") if isinstance(sig, dict) else None
        if (
            isinstance(stored, list)
            and len(stored) == len(fields_desc)
            and sig.get("instructions") is not None
        ):
            sig["instructions"] = cfg.get("instruction") or DEFAULT_INSTRUCTION
            for entry, desc in zip(stored, fields_desc, strict=True):
                if isinstance(entry, dict) and "description" in entry:
                    entry["description"] = desc
        else:
            # Shape drifted: rebuild, preserving demos/train/traces.
            fresh = _build_program({**cfg, "program_state": None}).dump_state()
            for key in ("demos", "traces", "train"):
                if key in state:
                    fresh[key] = state[key]
            cfg["program_state"] = fresh
    except Exception:
        cfg["program_state"] = None  # unreadable state → drop rather than lie
    return cfg


def reset(pid: str) -> dict | None:
    """Drop tuning state; user prompt edits survive."""
    cfg = DspyProgramStore.get(pid)
    if cfg is None:
        return None
    cfg["program_state"] = None
    cfg["tuned_at"] = None
    cfg["train_metrics"] = None
    cfg["n_demos"] = 0
    return DspyProgramStore.save(pid, cfg)
