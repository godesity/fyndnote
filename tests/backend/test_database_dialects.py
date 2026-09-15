"""Cross-dialect portability guards for the SQLAlchemy database layer.

These pin the guarantees the PostgreSQL/MySQL support rests on: DDL that
compiles on every target dialect, SQLite-only statements that translate to
each backend's upsert syntax, and ``?`` placeholders that survive the trip
into SQLAlchemy's bound-parameter world. They run without any server.
"""

from unittest import mock

import pytest
from sqlalchemy.dialects import registry
from sqlalchemy.schema import CreateTable

from fyndnote import database as dbmod
from fyndnote.database import (
    _adapt,
    _convert_params,
    json_num_expr,
    json_path_expr,
    metadata,
    numeric_compare,
)

DRIVERS = ["sqlite", "postgresql", "mysql", "mariadb"]


def _ddl_for(name):
    dialect = registry.load(name)
    dialect = dialect() if isinstance(dialect, type) else dialect
    return {
        table.name: str(CreateTable(table).compile(dialect=dialect)).strip()
        for table in metadata.tables.values()
    }


def _with_dialect(name, fn, *args):
    with mock.patch.object(dbmod, "_dialect", return_value=name):
        return fn(*args)


def _adapt_for(name, sql):
    with mock.patch.object(dbmod, "_dialect", return_value=name):
        return _adapt(sql)


@pytest.mark.parametrize("name", DRIVERS)
def test_schema_ddl_compiles_on_every_dialect(name):
    """Every table renders a CREATE statement the backend accepts."""
    ddl = _ddl_for(name)
    assert set(ddl) == set(metadata.tables)
    for stmt in ddl.values():
        assert stmt.upper().startswith("CREATE TABLE")


def test_mysql_rejects_no_defaults_on_text_columns():
    """MySQL refuses DEFAULT on BLOB/TEXT: defaulted columns must be VARCHAR."""
    for table in ("fyndnote_projects", "fyndnote_ml_annotations"):
        for line in _ddl_for("mysql")[table].splitlines():
            if "DEFAULT" in line.upper() and "CURRENT_TIMESTAMP" not in line.upper():
                assert "TEXT" not in line.upper(), f"{table}: {line}"


@pytest.mark.parametrize("name", ["mysql", "mariadb"])
def test_mysql_timestamps_avoid_the_2038_ceiling(name):
    """MySQL TIMESTAMP caps at year 2038, so *_at columns must not use it."""
    users = _ddl_for(name)["fyndnote_users"].upper()
    assert "DEFAULT CURRENT_TIMESTAMP" in users
    assert "TIMESTAMP" not in users.replace("CURRENT_TIMESTAMP", "")


@pytest.mark.parametrize(
    "name,marker",
    [
        # SQLite needs no keyword: an INTEGER PRIMARY KEY *is* the rowid alias.
        ("sqlite", "id INTEGER NOT NULL"),
        ("postgresql", "SERIAL"),
        ("mysql", "AUTO_INCREMENT"),
        ("mariadb", "AUTO_INCREMENT"),
    ],
)
def test_annotation_pk_grows_per_dialect(name, marker):
    ddl = _ddl_for(name)["fyndnote_annotations"]
    assert "PRIMARY KEY (id)" in ddl
    assert marker in ddl


def test_foreign_keys_survive_on_server_dialects():
    assert (
        "REFERENCES" in _ddl_for("postgresql")["fyndnote_project_permissions"].upper()
    )
    # SQLite keeps its historical FK-off behaviour, but the schema declares them.
    assert "REFERENCES" in _ddl_for("sqlite")["fyndnote_project_permissions"].upper()


def test_adapt_keeps_sqlite_statements_verbatim():
    sql = "INSERT OR REPLACE INTO fyndnote_ml_annotations (project_id, row_index) VALUES (?, ?)"
    assert _adapt_for("sqlite", sql) == sql


def test_adapt_translates_insert_or_replace():
    sql = "INSERT OR REPLACE INTO fyndnote_ml_annotations (project_id, row_index, annotator, data) VALUES (?, ?, ?, ?)"

    pg = _adapt_for("postgresql", sql)
    assert "INSERT OR REPLACE" not in pg
    assert "ON CONFLICT (project_id, row_index) DO UPDATE SET" in pg
    assert "annotator = EXCLUDED.annotator" in pg

    my = _adapt_for("mysql", sql)
    assert "ON CONFLICT" not in my
    assert "ON DUPLICATE KEY UPDATE" in my
    assert "annotator = VALUES(annotator)" in my


def test_adapt_translates_insert_or_ignore():
    sql = "INSERT OR IGNORE INTO fyndnote_project_permissions (user_id, project_id, role) VALUES (?, ?, ?)"

    pg = _adapt_for("postgresql", sql)
    assert "DO NOTHING" in pg and "DO UPDATE" not in pg

    assert _adapt_for("mysql", sql).startswith("INSERT IGNORE INTO")


def test_adapt_uses_targetless_on_conflict_for_unknown_tables():
    """No declared conflict keys: emit the target-less form, never a bogus target."""
    ignore = "INSERT OR IGNORE INTO fyndnote_datasets (id, source) VALUES (?, ?)"
    assert _adapt_for("postgresql", ignore).endswith("ON CONFLICT DO NOTHING")
    assert _adapt_for("mysql", ignore).startswith("INSERT IGNORE INTO")

    replace = "INSERT OR REPLACE INTO fyndnote_datasets (id, source) VALUES (?, ?)"
    assert _adapt_for("postgresql", replace) == (
        "INSERT INTO fyndnote_datasets (id, source) VALUES (?, ?)"
    )


def test_adapt_rewrites_on_conflict_for_mysql():
    sql = """
        INSERT INTO fyndnote_annotations (project_id, row_index, user_id, data, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(project_id, row_index, user_id)
        DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at
    """
    assert "ON CONFLICT(project_id, row_index, user_id)" in _adapt_for(
        "postgresql", sql
    )

    my = _adapt_for("mysql", sql)
    assert "ON CONFLICT" not in my
    assert "ON DUPLICATE KEY UPDATE" in my
    assert "data = VALUES(data)" in my
    assert "updated_at = VALUES(updated_at)" in my


def test_adapt_drops_pragma_off_sqlite():
    assert _adapt_for("postgresql", "PRAGMA journal_mode=WAL") == ""
    assert _adapt_for("sqlite", "PRAGMA journal_mode=WAL") == "PRAGMA journal_mode=WAL"


@pytest.mark.parametrize("name", DRIVERS)
def test_adapt_passes_through_plain_selects(name):
    sql = "SELECT * FROM fyndnote_projects WHERE id = ?"
    assert _adapt_for(name, sql) == sql


def test_convert_params_binds_positional_placeholders():
    p = _convert_params("SELECT * FROM t WHERE a = ? AND b = ?", ("x", "y"))
    assert "?" not in p.sql
    assert p.params == {"c0": "x", "c1": "y"}


def test_convert_params_leaves_named_sql_untouched():
    assert _convert_params("SELECT * FROM t WHERE a = :val", {"val": 1}).params == {
        "val": 1
    }


def test_convert_params_handles_bulk_values():
    p = _convert_params("INSERT INTO t (a, b) VALUES (?, ?), (?, ?)", (1, 2, 3, 4))
    assert "?" not in p.sql
    assert set(p.params) == {"c0", "c1", "c2", "c3"}


@pytest.mark.parametrize(
    "dialect,expr,path",
    [
        ("postgresql", "d::jsonb #>> ?", "{label}"),
        ("mysql", "JSON_UNQUOTE(JSON_EXTRACT(d, ?))", "$.label"),
        ("sqlite", "json_extract(d, ?)", "$.label"),
    ],
)
def test_json_path_expr_per_dialect(dialect, expr, path):
    assert _with_dialect(dialect, json_path_expr, "d", "label") == (expr, path)


@pytest.mark.parametrize(
    "dialect,cast",
    [("postgresql", "NUMERIC"), ("mysql", "DECIMAL"), ("sqlite", "REAL")],
)
def test_json_num_expr_casts_per_dialect(dialect, cast):
    expr, _ = _with_dialect(dialect, json_num_expr, "d", "score")
    assert expr.upper().startswith("CAST(")
    assert cast in expr.upper()


def test_nested_json_paths_use_dialect_path_syntax():
    assert (
        _with_dialect("postgresql", json_path_expr, "d", "meta.inner")[1]
        == "{meta,inner}"
    )
    assert (
        _with_dialect("sqlite", json_path_expr, "d", "meta.inner")[1] == "$.meta.inner"
    )


def test_numeric_compare_excludes_nulls():
    """A missing key or non-numeric text must never satisfy a numeric filter."""
    guarded = numeric_compare("x", "!=")
    assert guarded.endswith("x != ?")
    assert "x IS NOT NULL AND" in guarded
