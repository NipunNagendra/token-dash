"""Token usage dashboard: pull public LLM usage slices, derive metrics, build a static page."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
MANUAL = DATA / "manual"
CONFIG = ROOT / "config"
SITE = ROOT / "site"
DB_PATH = DATA / "tokendash.duckdb"
