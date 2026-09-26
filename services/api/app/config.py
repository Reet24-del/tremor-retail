import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.getenv("TREMOR_DATA_DIR", REPO_ROOT / "data"))
DEMO_DIR = DATA_DIR / "demo"
RUNTIME_DIR = Path(os.getenv("TREMOR_RUNTIME_DIR", REPO_ROOT / "runtime"))
DB_PATH = RUNTIME_DIR / "tremor.duckdb"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LLM_MODEL = os.getenv("TREMOR_LLM_MODEL", "")  # e.g. a current Claude Sonnet model id
USE_LLM = bool(ANTHROPIC_API_KEY and LLM_MODEL and os.getenv("TREMOR_DISABLE_LLM") != "1")
LLM_TIMEOUT_S = float(os.getenv("TREMOR_LLM_TIMEOUT", "40"))

MAX_UPLOAD_MB = 10
DETECTOR_VERSION = "demo-v1"
PROMPT_VERSION = "signal-v1"
CONFIG_VERSION = "cfg-2026-09-26"

# Matching thresholds (configuration, tuned only against labelled demo pairs)
FUZZY_AUTO_ACCEPT = 92.0
COMBINED_AUTO_ACCEPT = 85.0
COMBINED_REVIEW = 70.0

# Detection thresholds
COST_Z_THRESHOLD = 3.5
MIN_LEAKAGE_INR = 200.0
MIN_STOCK_VARIANCE_UNITS = 5
MIN_STOCK_VARIANCE_INR = 300.0
SPIKE_Z_THRESHOLD = 3.5

CORS_ORIGINS = [o.strip() for o in os.getenv("TREMOR_CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
