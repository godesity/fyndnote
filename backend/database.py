import sqlite3
from config import DATABASE_PATH

def get_db() -> sqlite3.Connection:
    db = sqlite3.connect(str(DATABASE_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS fyndnot_users (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            global_role TEXT NOT NULL CHECK(global_role IN ('system_admin','annotator')),
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS fyndnot_projects (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            dataset_id  TEXT NOT NULL,
            template_id TEXT NOT NULL,
            salt        TEXT NOT NULL,
            color       TEXT DEFAULT '#1976d2',
            tags        TEXT DEFAULT '',
            instructions TEXT DEFAULT '',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS fyndnot_project_permissions (
            user_id    TEXT NOT NULL REFERENCES fyndnot_users(id),
            project_id TEXT NOT NULL REFERENCES fyndnot_projects(id),
            role       TEXT NOT NULL CHECK(role IN ('project_admin','annotator')),
            PRIMARY KEY (user_id, project_id)
        );
        CREATE TABLE IF NOT EXISTS fyndnot_annotations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  TEXT NOT NULL REFERENCES fyndnot_projects(id),
            row_index   INTEGER NOT NULL,
            user_id     TEXT NOT NULL REFERENCES fyndnot_users(id),
            data        TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, row_index, user_id)
        );
        CREATE TABLE IF NOT EXISTS fyndnot_ml_annotations (
            project_id  TEXT NOT NULL REFERENCES fyndnot_projects(id),
            row_index   INTEGER NOT NULL,
            annotator   TEXT NOT NULL,
            data        TEXT NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(project_id, row_index)
        );
        CREATE TABLE IF NOT EXISTS fyndnot_datasets (
            id            TEXT PRIMARY KEY,
            source        TEXT NOT NULL,
            source_type   TEXT NOT NULL,
            source_format TEXT,
            hf_name       TEXT,
            hf_split      TEXT,
            num_rows      INTEGER NOT NULL,
            columns       TEXT NOT NULL,
            created_at    TEXT NOT NULL,
            s3_uploaded   INTEGER DEFAULT 0
        );
    """)
    # Migration for existing databases that lack color/tags/instructions columns
    for col in [("color", "TEXT DEFAULT '#1976d2'"), ("tags", "TEXT DEFAULT ''"), ("instructions", "TEXT DEFAULT ''")]:
        try:
            db.execute(f"ALTER TABLE fyndnot_projects ADD COLUMN {col[0]} {col[1]}")
        except sqlite3.OperationalError:
            pass  # column already exists
    # Migration for ML backend columns
    for col in [("ml_enabled", "INTEGER DEFAULT 0"), ("ml_url", "TEXT DEFAULT ''"), ("ml_annotator", "TEXT DEFAULT ''"), ("ml_mode", "TEXT DEFAULT 'on_navigate'")]:
        try:
            db.execute(f"ALTER TABLE fyndnot_projects ADD COLUMN {col[0]} {col[1]}")
        except sqlite3.OperationalError:
            pass
    db.commit()
    db.close()

def seed_from_json():
    import json
    seed_file = DATABASE_PATH.parent / "users.json"
    if not seed_file.exists():
        return
    db = get_db()
    existing = db.execute("SELECT COUNT(*) FROM fyndnot_users").fetchone()[0]
    if existing > 0:
        db.close()
        return
    db.execute("PRAGMA foreign_keys=OFF")
    with open(seed_file) as f:
        data = json.load(f)
    for user in data["users"]:
        db.execute(
            "INSERT OR IGNORE INTO fyndnot_users (id, name, global_role) VALUES (?, ?, ?)",
            (user["id"], user["name"], user["global_role"])
        )
        for project_id, role in user.get("project_roles", {}).items():
            db.execute(
                "INSERT OR IGNORE INTO fyndnot_project_permissions (user_id, project_id, role) VALUES (?, ?, ?)",
                (user["id"], project_id, role)
            )
    db.execute("PRAGMA foreign_keys=ON")
    db.commit()
    db.close()
