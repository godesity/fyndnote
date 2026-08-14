import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATABASE_PATH = DATA_DIR / "labeling.db"
DATASETS_DIR = DATA_DIR / "datasets"
DATASETS_UPLOAD_DIR = DATA_DIR / "datasets" / "uploads"
TEMPLATES_DIR = DATA_DIR / "templates"
