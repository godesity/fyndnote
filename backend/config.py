import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DATABASE_PATH = DATA_DIR / "labeling.db"
DATASETS_DIR = DATA_DIR / "datasets"
DATASETS_UPLOAD_DIR = DATA_DIR / "datasets" / "uploads"
TEMPLATES_DIR = DATA_DIR / "templates"

# Redirect HF datasets cache into our managed tree (avoids duplication)
os.environ.setdefault("HF_DATASETS_CACHE", str(DATASETS_DIR))

# S3 cache settings
S3_CACHE_ENABLED = os.getenv("S3_CACHE_ENABLED", "false").lower() == "true"
S3_CACHE_BUCKET = os.getenv("S3_CACHE_BUCKET", "")
S3_CACHE_PREFIX = os.getenv("S3_CACHE_PREFIX", "datasets-cache")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL") or None

# LRU / disk-pressure settings
MAX_CACHED_DATASETS = int(os.getenv("MAX_CACHED_DATASETS", "10"))
DISK_USAGE_THRESHOLD = float(os.getenv("DISK_USAGE_THRESHOLD", "0.9"))
