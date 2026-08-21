"""Seed the database with a few demo projects for development."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uuid
from database import get_db, init_db, seed_from_json
from services.dataset_service import DatasetService
from services.annotation_service import AnnotationService
from services.template_service import TemplateService

# 1. Reset DB
db = get_db()
db.executescript("""
    DELETE FROM fyndnot_annotations;
    DELETE FROM fyndnot_project_permissions;
    DELETE FROM fyndnot_projects;
    DELETE FROM fyndnot_users;
""")
db.commit()
db.close()

# 2. Re-seed users
init_db()
seed_from_json()

# 3. Create a template
tmpl = TemplateService.create(
    "sentiment",
    '<div><h3>{text}</h3><SelectField name="sentiment" options="positive,negative,neutral" /></div>',
    False,
)
tid = tmpl["id"]
print(f"Template: {tid}")

# 4. Load IMDB dataset
meta = DatasetService.load("stanfordnlp/imdb", split="train")
ds_id = meta["id"]
print(f"Dataset: {ds_id} ({meta['num_rows']} rows)")

# 5. Create projects
projects = [
    ("IMDB Sentiment Analysis", "#1976d2", "nlp,imdb", "Label the sentiment of each review"),
    ("Review Triage", "#e67e22", "triage", "Quickly triage reviews"),
    ("Quality Check", "#2ecc71", "qa", "Quality assurance pass"),
]

db = get_db()
pids = []
for name, color, tags, instructions in projects:
    pid = str(uuid.uuid4())
    pids.append(pid)
    db.execute(
        "INSERT INTO fyndnot_projects (id, name, dataset_id, template_id, salt, color, tags, instructions) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pid, name, ds_id, tid, f"seed-{pid[:8]}", color, tags, instructions),
    )

# 6. Add permissions
perms = []
for pid in pids:
    perms.append(("alice", pid, "project_admin"))
perms.append(("bob", pids[0], "annotator"))
db.executemany(
    "INSERT INTO fyndnot_project_permissions (user_id, project_id, role) VALUES (?, ?, ?)",
    perms,
)
db.commit()
db.close()

# 7. Verify
projects = AnnotationService.list_projects("alice")
print(f"\nProjects visible to alice: {len(projects)}")
for p in projects:
    print(f"  - {p['name']}  (id={p['id']})")
