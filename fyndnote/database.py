"""Database layer — schema management plus a tiny SQL facade.

Every query runs through SQLAlchemy Core (``text()`` on an ``Engine``). The
schema is declared once as a SQLAlchemy ``MetaData`` so DDL is rendered
per-dialect (SQLite, PostgreSQL, MySQL, MariaDB, …) instead of being pasted
as raw SQL for one backend. That is what fixes ``init_db`` on PostgreSQL:
the old psycopg implementation shipped SQLite-flavoured DDL and needed a
superuser to turn FK checks off while seeding, which aborted the whole seed
for a normal role (``InFailedSqlTransaction``).

The facade keeps the historical ``db.execute(sql, params)`` / ``fetchone`` /
``fetchall`` / ``dict(row)`` convention the service layer was written
against:

- positional ``?`` placeholders are rewritten into bound parameters
  (``:c0``, ``:c1``…) before SQLAlchemy sees them;
- the handful of SQLite-only statements in the code base
  (``INSERT OR REPLACE`` / ``INSERT OR IGNORE`` / ``ON CONFLICT``) are
  translated to the active dialect's upsert syntax;
- JSON field access goes through :func:`json_path_expr` /
  :func:`json_num_expr` so annotation filters work on every dialect.
"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    inspect,
    make_url,
    text,
)
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool, StaticPool

from .config import DATABASE_PATH, DATABASE_URL, DATASETS_DIR, TEMPLATES_DIR

# ---------------------------------------------------------------------------
# Engine / dialect resolution
# ---------------------------------------------------------------------------

_engines: dict[str, Engine] = {}

_MYSQL_FLAVOURS = ("mysql", "mariadb")


def _normalize_url(url: str) -> str:
    """Upgrade a plain ``postgresql://`` URL to the psycopg (v3) driver.

    One PostgreSQL driver across the project; an explicit
    ``postgresql+psycopg2://`` URL is respected as-is.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _engine_args(url: str, dialect: str) -> dict:
    if dialect == "sqlite":
        if ":memory:" in url or url.rstrip("/") == "sqlite://":
            return {
                "connect_args": {"check_same_thread": False},
                "poolclass": StaticPool,
            }
        # FastAPI runs handlers in a threadpool: each thread checks out its own
        # connection instead of sharing one across threads.
        return {"connect_args": {"check_same_thread": False}, "poolclass": QueuePool}
    return {"pool_pre_ping": True}


def _resolve_url() -> str:
    return (
        _normalize_url(DATABASE_URL)
        if DATABASE_URL
        else "sqlite:///" + str(DATABASE_PATH)
    )


def _get_engine() -> Engine:
    url = _resolve_url()
    eng = _engines.get(url)
    if eng is None:
        # The URL alone names the dialect, so pooling can be chosen without
        # spinning up a throwaway probe engine first.
        eng = create_engine(url, **_engine_args(url, make_url(url).get_dialect().name))
        _engines[url] = eng
    return eng


def dialect_name() -> str:
    """Active dialect: ``sqlite``, ``postgresql``, ``mysql``, ``mariadb``, …"""
    return _get_engine().dialect.name


def _dialect() -> str:
    return dialect_name()


# ---------------------------------------------------------------------------
# Schema — single source of truth for DDL on every dialect
# ---------------------------------------------------------------------------

metadata = MetaData()

#: portable stand-in for SQLite's TEXT / PostgreSQL's VARCHAR
_TEXT = String(255)

#: TEXT everywhere, but VARCHAR(255) on MySQL, which rejects DEFAULT on BLOB/TEXT
_defaultable_text = Text().with_variant(String(255), "mysql")

#: TEXT everywhere, DATETIME on MySQL (its TIMESTAMP is capped at year 2038)
_ts_text = Text().with_variant(DATETIME(), "mysql")


def _now() -> text:
    return text("CURRENT_TIMESTAMP")


fyndnote_users = Table(
    "fyndnote_users",
    metadata,
    Column("id", _TEXT, primary_key=True),
    Column("name", Text, nullable=False),
    Column("global_role", _TEXT, nullable=False),
    Column("created_at", _ts_text, server_default=_now()),
    CheckConstraint("global_role IN ('system_admin','annotator')"),
)

fyndnote_projects = Table(
    "fyndnote_projects",
    metadata,
    Column("id", _TEXT, primary_key=True),
    Column("name", _TEXT, nullable=False),
    Column("dataset_id", _TEXT, nullable=False),
    Column("template_id", _TEXT, nullable=False),
    Column("salt", _TEXT, nullable=False),
    Column("color", _defaultable_text, server_default=text("'#1976d2'")),
    Column("tags", _defaultable_text, server_default=text("''")),
    Column("instructions", _defaultable_text, server_default=text("''")),
    Column("ml_enabled", Integer, server_default=text("0")),
    Column("ml_url", _defaultable_text, server_default=text("''")),
    Column("ml_annotator", _defaultable_text, server_default=text("''")),
    Column("ml_mode", _defaultable_text, server_default=text("'on_navigate'")),
    Column("created_at", _ts_text, server_default=_now()),
)

fyndnote_project_permissions = Table(
    "fyndnote_project_permissions",
    metadata,
    Column("user_id", _TEXT, ForeignKey("fyndnote_users.id"), nullable=False),
    Column("project_id", _TEXT, ForeignKey("fyndnote_projects.id"), nullable=False),
    Column("role", _TEXT, nullable=False),
    PrimaryKeyConstraint("user_id", "project_id"),
    CheckConstraint("role IN ('project_admin','annotator')"),
)

fyndnote_annotations = Table(
    "fyndnote_annotations",
    metadata,
    # autoincrement Integer PK: AUTOINCREMENT on SQLite, SERIAL on PostgreSQL,
    # AUTO_INCREMENT on MySQL.
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("project_id", _TEXT, ForeignKey("fyndnote_projects.id"), nullable=False),
    Column("row_index", Integer, nullable=False),
    Column("user_id", _TEXT, ForeignKey("fyndnote_users.id"), nullable=False),
    Column("data", Text, nullable=False),
    Column("created_at", _ts_text, server_default=_now()),
    Column("updated_at", _ts_text, server_default=_now()),
    UniqueConstraint("project_id", "row_index", "user_id"),
)

fyndnote_ml_annotations = Table(
    "fyndnote_ml_annotations",
    metadata,
    Column("project_id", _TEXT, ForeignKey("fyndnote_projects.id"), nullable=False),
    Column("row_index", Integer, nullable=False),
    Column("annotator", _TEXT, nullable=False),
    Column("data", Text, nullable=False),
    Column("created_at", _ts_text, server_default=_now()),
    Column("updated_at", _ts_text, server_default=_now()),
    PrimaryKeyConstraint("project_id", "row_index"),
)

fyndnote_datasets = Table(
    "fyndnote_datasets",
    metadata,
    Column("id", _TEXT, primary_key=True),
    Column("name", Text, nullable=False),
    Column("source", Text, nullable=False),
    Column("source_type", _TEXT, nullable=False),
    Column("source_format", _TEXT),
    Column("hf_name", Text),
    Column("hf_split", _TEXT),
    Column("num_rows", Integer, nullable=False),
    Column("columns", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("s3_uploaded", Integer, server_default=text("0")),
    # The label every picker/list shows. ``hf_name`` is the HuggingFace *config*
    # name ("" on most imports, NULL for file/http), so it cannot double as the
    # display name: two datasets with the same label are indistinguishable.
    Index("fyndnote_datasets_name_uq", "name", unique=True),
)

dataset_meta = Table(
    "dataset_meta",
    metadata,
    Column("project_id", _TEXT, primary_key=True),
    Column("num_rows", Integer, nullable=False, server_default=text("0")),
    Column("next_fragment", Integer, nullable=False, server_default=text("0")),
    Column("schema", Text),
    Column("created_at", Text, nullable=False),
)


# ---------------------------------------------------------------------------
# Statement compatibility (SQLite-flavoured SQL -> active dialect)
# ---------------------------------------------------------------------------

#: conflict keys for statements upserted with ``INSERT OR REPLACE``/``OR IGNORE``
_UPSERT_KEYS = {
    "fyndnote_ml_annotations": ["project_id", "row_index"],
    "fyndnote_project_permissions": ["user_id", "project_id"],
    "fyndnote_users": ["id"],
}

_INSERT_RE = re.compile(
    r"^\s*INSERT(?:\s+OR\s+\w+)?\s+INTO\s+(?P<table>[\w.]+)\s*\((?P<cols>[^)]*)\)\s*"
    r"VALUES\s+(?P<vals>.+?)\s*;?\s*$",
    re.IGNORECASE | re.DOTALL,
)
_OR_INSERT_RE = re.compile(
    r"^INSERT\s+OR\s+(?P<verb>REPLACE|IGNORE)\s+INTO\s+(?P<table>[\w.]+)",
    re.IGNORECASE,
)
_ON_CONFLICT_RE = re.compile(
    r"\bON\s+CONFLICT\b(?P<target>\s*\([^)]*\))?\s*DO\s+(?P<mode>NOTHING|UPDATE\s+SET\s+(?P<sets>.+?))\s*$",
    re.IGNORECASE | re.DOTALL,
)


class _Params:
    """Distinguishes already-named SQL from the legacy positional form."""

    __slots__ = ("params", "sql")

    def __init__(self, sql: str, params):
        self.sql = sql
        self.params = params


def _convert_params(sql: str, params) -> _Params:
    """Rewrite a ``?``-placeholder statement into bound ``:cN`` parameters."""
    if isinstance(params, dict):
        return _Params(sql, params)
    if params is None:
        params = ()
    if not isinstance(params, (list, tuple)):
        params = (params,)
    if not params:
        return _Params(sql, {})

    counter = iter(range(len(params)))
    if _INSERT_RE.match(sql) and re.search(
        r"\(\s*\?\s*(?:,\s*\?\s*)*\)", sql, re.IGNORECASE
    ):
        # Bulk VALUES form: (?, ?, ?) -> (:c0, :c1, :c2)
        converted = re.sub(
            r"\(\s*\?\s*(?:,\s*\?\s*)*\)",
            lambda _m: "(" + ", ".join(f":c{n}" for n in counter) + ")",
            sql,
        )
    else:
        converted = re.sub(r"\?", lambda _m: f":c{next(counter)}", sql, len(params))
    return _Params(converted, {f"c{i}": v for i, v in enumerate(params)})


def _upsert(sql: str, verb: str, table: str, dialect: str) -> str:
    """Render ``INSERT OR REPLACE``/``OR IGNORE`` in the dialect's upsert form."""
    m = _INSERT_RE.match(sql)
    if not m:
        return sql
    quoted = m.group("table")
    cols = [c.strip() for c in m.group("cols").split(",")]
    base = f"INSERT INTO {quoted} ({', '.join(cols)}) VALUES {m.group('vals').strip()}"
    keys = _UPSERT_KEYS.get(table.lower())
    unknown = keys is None or any(k not in cols for k in keys)

    if dialect == "postgresql":
        if verb == "IGNORE":
            return (
                base
                if "ON CONFLICT" in base.upper()
                else base + " ON CONFLICT DO NOTHING"
            )
        if unknown:
            return base
        updates = [c for c in cols if c not in keys]
        set_ = ", ".join(f"{c} = EXCLUDED.{c}" for c in updates) or "id = id"
        return base + f" ON CONFLICT ({', '.join(keys)}) DO UPDATE SET {set_}"

    if dialect in _MYSQL_FLAVOURS:
        if verb == "IGNORE":
            return re.sub(
                r"^INSERT\s+OR\s+IGNORE\s+INTO\s+",
                "INSERT IGNORE INTO ",
                sql.strip(),
                count=1,
                flags=re.IGNORECASE,
            )
        if unknown:
            return base
        updates = [c for c in cols if c not in keys]
        set_ = ", ".join(f"{c} = VALUES({c})" for c in updates) or "id = id"
        return base + f" ON DUPLICATE KEY UPDATE {set_}"

    # Unknown dialect: a plain INSERT is the closest portable form.
    return base


def _on_conflict_for(sql: str, dialect: str) -> str:
    """Translate PostgreSQL's ``ON CONFLICT`` clause for other dialects."""
    m = _ON_CONFLICT_RE.search(sql)
    if not m:
        return sql
    head = sql[: m.start()].rstrip()
    if m.group("mode").upper().startswith("NOTHING"):
        tail = (
            "ON DUPLICATE KEY UPDATE id = id"
            if dialect in _MYSQL_FLAVOURS
            else "ON CONFLICT DO NOTHING"
        )
        return f"{head} {tail}"
    sets = m.group("sets").strip().rstrip(";").rstrip()
    if dialect in _MYSQL_FLAVOURS:
        sets = re.sub(r"\bexcluded\.(\w+)", r"VALUES(\1)", sets, flags=re.IGNORECASE)
        return f"{head} ON DUPLICATE KEY UPDATE {sets}"
    return sql


def _adapt(sql: str) -> str:
    """Rewrite dialect-specific statements for the active dialect."""
    s = sql.strip()
    if not s:
        return ""
    dialect = _dialect()
    if dialect == "sqlite":
        return s

    if re.match(r"PRAGMA\b", s, re.IGNORECASE):
        # PRAGMA handling belongs to init_db/seed_from_json, which are
        # dialect-aware; no service depends on a PRAGMA result.
        return ""

    m = _OR_INSERT_RE.match(s)
    if m:
        return _upsert(s, m.group("verb").upper(), m.group("table"), dialect)

    if re.search(r"\bON\s+CONFLICT\b", s, re.IGNORECASE) and dialect != "postgresql":
        return _on_conflict_for(s, dialect)

    return s


# ---------------------------------------------------------------------------
# JSON field access (per-dialect codegen)
# ---------------------------------------------------------------------------


def json_path_expr(col: str, field_name: str) -> tuple[str, str]:
    """Return ``(sql_fragment, path_param)`` for a JSON field's *text* value.

    The fragment contains exactly one ``?`` placeholder; bind it to
    ``path_param``.
    """
    dialect = _dialect()
    if dialect == "postgresql":
        return f"{col}::jsonb #>> ?", "{" + field_name.replace(".", ",") + "}"
    if dialect in _MYSQL_FLAVOURS:
        return f"JSON_UNQUOTE(JSON_EXTRACT({col}, ?))", f"$.{field_name}"
    return f"json_extract({col}, ?)", f"$.{field_name}"


def json_num_expr(col: str, field_name: str) -> tuple[str, str]:
    """Return ``(sql_fragment, path_param)`` yielding a JSON field as a number."""
    expr, path = json_path_expr(col, field_name)
    dialect = _dialect()
    if dialect == "postgresql":
        return f"CAST({expr} AS NUMERIC)", path
    if dialect in _MYSQL_FLAVOURS:
        return f"CAST({expr} AS DECIMAL(40, 10))", path
    return f"CAST({expr} AS REAL)", path


def numeric_compare(fragment: str, op: str) -> str:
    """Numeric comparison where NULL (missing / non-numeric value) never matches.

    Guards the PostgreSQL cast too: without it a stored non-numeric value
    raises ``invalid input syntax for type numeric`` instead of filtering out.
    """
    return f"{fragment} IS NOT NULL AND {fragment} {op} ?"


# ---------------------------------------------------------------------------
# Result / row wrappers (sqlite3.Row-compatible surface)
# ---------------------------------------------------------------------------


class _Row(dict):
    """Mapping row that also supports ``row[0]`` and value iteration."""

    __slots__ = ()

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return dict.__getitem__(self, key)

    def __iter__(self):
        return iter(self.values())


class _Result:
    __slots__ = ("_rows", "rowcount")

    def __init__(self, keys: list[str], rows: list, rowcount: int):
        self._rows = [_Row(dict(zip(keys, r))) for r in rows]
        self.rowcount = rowcount

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def fetchmany(self, n: int = 1):
        return self._rows[:n]

    def __iter__(self):
        return iter(self._rows)


class _DB:
    """Connection wrapper preserving the historical service API.

    Transactions autobegin on the first statement; ``commit()`` commits and
    ``close()`` releases the connection (rolling back anything left open),
    matching the psycopg3/sqlite3 semantics the services assume.
    """

    def __init__(self, eng: Engine):
        self._eng = eng
        self._conn = eng.connect()

    def _run(self, sql: str, params) -> _Result:
        bound = params if isinstance(params, _Params) else _convert_params(sql, params)
        cursor = self._conn.execute(text(bound.sql), bound.params)
        if cursor.returns_rows:
            keys = list(cursor.keys())
            rows = [tuple(r) for r in cursor.fetchall()]
        else:
            keys, rows = [], []
        return _Result(keys, rows, cursor.rowcount)

    def execute(self, sql: str, params=None) -> _Result:
        adapted = _adapt(sql)
        if not adapted:
            return _Result([], [], 0)
        return self._run(adapted, params)

    def executemany(self, sql: str, seq) -> None:
        adapted = _adapt(sql)
        if not adapted:
            return
        rows = [tuple(r) for r in seq]
        if not rows:
            return
        probe = _convert_params(adapted, rows[0])
        if probe.params and all(k[1:].isdigit() for k in probe.params):
            self._conn.execute(
                text(probe.sql), [{f"c{i}": v for i, v in enumerate(r)} for r in rows]
            )
        else:
            self._conn.execute(text(adapted), rows)

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            if statement.strip():
                self.execute(statement)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


def get_db() -> _DB:
    """Open a connection. Schema creation happens in :func:`init_db` only."""
    return _DB(_get_engine())


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

#: columns added after the first release (for databases created earlier)
_MIGRATION_COLUMNS = ("ml_enabled", "ml_url", "ml_annotator", "ml_mode")


def init_db() -> None:
    """Create the schema and migrate databases from older releases.

    Goes entirely through SQLAlchemy Core, so one code path serves SQLite and
    server backends (PostgreSQL/MySQL/MariaDB/…).
    """
    if not DATABASE_URL:
        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    eng = _get_engine()
    if eng.dialect.name == "sqlite":
        with eng.begin() as conn:
            # Durability only: FK enforcement stays off, matching the
            # historical behaviour (services delete child rows explicitly).
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")

    # Must precede create_all: the declared unique index references ``name``,
    # which older databases do not have yet.
    _backfill_dataset_names(eng)
    metadata.create_all(eng)
    _migrate(eng)


def derive_display_name(source: str, source_type: str | None = None) -> str:
    """The label a dataset row gets when the user does not pick one.

    The HuggingFace ``hf_name`` is deliberately not part of this: it is the
    *config* name (``test``, ``plain_text``) and repeats across every repo that
    ships it, whereas the repo id in ``source`` actually distinguishes datasets.
    """
    if source_type != "huggingface":
        tail = source.split("?")[0].rstrip("/").split("/")[-1]
        return tail or source
    return source


def name_variant(base: str, occurrence: int) -> str:
    """The ``occurrence``-th (1-based) disambiguated spelling of ``base``."""
    return base if occurrence <= 1 else f"{base} ({occurrence})"


def _backfill_dataset_names(eng: Engine) -> None:
    """Give every dataset row a unique display name and index it.

    Rows written before the column existed all displayed the same thing in the
    picker (the repo id, with the HF config always ``""``/NULL), so backfilling
    the derived value alone would immediately violate the unique index. Walking
    every row in creation order — first holder of a label keeps it, later ones
    get ``label (2)``, ``(3)``, … — makes the table collision-free, which is a
    precondition for the index this adds at the end.
    """
    insp = inspect(eng)
    if not insp.has_table("fyndnote_datasets"):
        return
    existing = {c["name"] for c in insp.get_columns("fyndnote_datasets")}
    if "name" not in existing:
        col = fyndnote_datasets.columns["name"]
        spec = col.type.compile(dialect=eng.dialect)
        with eng.begin() as conn:
            conn.exec_driver_sql(
                f"ALTER TABLE fyndnote_datasets ADD COLUMN name {spec} NOT NULL DEFAULT ''"
            )
        if "name" not in {
            c["name"] for c in inspect(eng).get_columns("fyndnote_datasets")
        }:  # pragma: no cover - defensive
            return

    with eng.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id, source, source_type, name FROM fyndnote_datasets"
                " ORDER BY created_at, id"
            )
        ).all()
        update = text("UPDATE fyndnote_datasets SET name = :name WHERE id = :id")
        taken: set[str] = set()
        for ds_id, source, source_type, name in rows:
            # An already-labelled row keeps its label; empty/NULL derives from
            # the source, and any row whose label collides with an earlier one
            # is re-suffixed (covers duplicates a pre-column writer left behind).
            base = (name or "").strip() or derive_display_name(
                source or "", source_type
            )
            n = 1
            while (cand := name_variant(base, n)) in taken:
                n += 1
            if cand != name:
                conn.execute(update, {"name": cand, "id": ds_id})
            taken.add(cand)

    _ensure_dataset_name_index(eng)


def _ensure_dataset_name_index(eng: Engine) -> None:
    """Create the unique display-name index on a table ``create_all`` skipped.

    ``metadata.create_all`` checks table existence and skips an existing table
    *wholesale* — indexes included — so the declared unique index only reaches
    fresh databases. Without this, upgraded servers get the ``name`` column but
    no DB-level uniqueness, and the post-concurrency-guard INSERT would happily
    accept two datasets sharing a label.
    """
    have = {i["name"] for i in inspect(eng).get_indexes("fyndnote_datasets")}
    for index in fyndnote_datasets.indexes:
        if index.name not in have:
            index.create(bind=eng, checkfirst=True)


def _migrate(eng: Engine) -> None:
    """Add ``ml_*`` columns introduced after the first release."""
    existing = {c["name"] for c in inspect(eng).get_columns("fyndnote_projects")}
    for name in (c for c in _MIGRATION_COLUMNS if c not in existing):
        col = fyndnote_projects.columns[name]
        spec = col.type.compile(dialect=eng.dialect)
        default = (
            col.server_default.arg.text if col.server_default is not None else None
        )
        clause = f" DEFAULT {default}" if default else ""
        with eng.begin() as conn:
            conn.exec_driver_sql(
                f"ALTER TABLE fyndnote_projects ADD COLUMN {name} {spec}{clause}"
            )


def _seed_file() -> Path | None:
    for candidate in (
        DATABASE_PATH.parent / "users.json",
        Path(__file__).resolve().parent / "_data" / "users.json",
    ):
        if candidate.exists():
            return candidate
    return None


def seed_from_json() -> None:
    """Insert the bundled seed users and their project roles.

    Each row is its own transaction, so a foreign-key violation on a server
    backend skips that row instead of aborting the whole seed — the bug the
    old psycopg implementation hit (it needed a superuser to disable FK
    checks, and a normal role's failed statement poisoned the transaction).
    """
    seed_file = _seed_file()
    if seed_file is None:
        return

    eng = _get_engine()
    now = datetime.now(UTC).isoformat()
    for user in json.loads(seed_file.read_text())["users"]:
        _insert_if_absent(
            eng,
            fyndnote_users,
            {
                "id": user["id"],
                "name": user["name"],
                "global_role": user["global_role"],
                "created_at": user.get("created_at", now),
            },
        )
        for project_id, role in user.get("project_roles", {}).items():
            _insert_if_absent(
                eng,
                fyndnote_project_permissions,
                {
                    "user_id": user["id"],
                    "project_id": project_id,
                    "role": role,
                },
                skip_fk_violations=True,
            )


def _insert_if_absent(
    eng: Engine, table: Table, row: dict, skip_fk_violations: bool = False
) -> bool:
    """Insert ``row`` when its primary key is free; return whether it is stored.

    One transaction per row, so a foreign-key violation on a server backend
    costs a single row instead of the whole seed.
    """
    pk_cols = [c.name for c in table.primary_key.columns]
    with eng.connect() as conn:
        taken = conn.execute(
            text(
                f"SELECT 1 FROM {table.name} WHERE "
                + " AND ".join(f"{c} = :{c}" for c in pk_cols)
            ),
            {c: row[c] for c in pk_cols},
        ).first()
        if taken is not None:
            return True
        try:
            conn.execute(table.insert().values(**row))
            conn.commit()
        except Exception:
            conn.rollback()
            if skip_fk_violations:
                return False
            raise
    return True
