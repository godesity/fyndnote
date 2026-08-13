import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATABASE_PATH = DATA_DIR / "labeling.db"
DATASETS_DIR = DATA_DIR / "datasets"
TEMPLATES_DIR = DATA_DIR / "templates"
