import os
from pathlib import Path

from dotenv import load_dotenv

# Workspace Root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / "Env" / ".env")

# Data Paths
DEFAULT_INPUT_DIR = BASE_DIR / "Input file"
RAW_DATA_DIR = BASE_DIR / "Raw Data"
SAMPLE_DATA_DIR = BASE_DIR / "Sample data for Hack Fest"
# Directory for knowledge documents & guides (neat and organized)
CUSTOM_DOCS_DIR = BASE_DIR / "knowledge_docs"
CUSTOM_DOCS_DIR.mkdir(exist_ok=True, parents=True)

# Core Reference Documents & Guides (located in knowledge_docs)
HACKATHON_GUIDE_PATH = CUSTOM_DOCS_DIR / "HACKATHON_DATA_GUIDE.md"
if not HACKATHON_GUIDE_PATH.exists():
    HACKATHON_GUIDE_PATH = BASE_DIR / "HACKATHON_DATA_GUIDE.md"

CHEAT_SHEET_PATH = CUSTOM_DOCS_DIR / "Diagnostic Cheat Sheet.md"
if not CHEAT_SHEET_PATH.exists():
    CHEAT_SHEET_PATH = BASE_DIR / "Diagnostic Cheat Sheet.md"

WER_GUIDE_PATH = CUSTOM_DOCS_DIR / "How to read Crash Dumps_REPORT_WER.md"
if not WER_GUIDE_PATH.exists():
    WER_GUIDE_PATH = SAMPLE_DATA_DIR / "Guide" / "How to read Crash Dumps_REPORT_WER.md"

START_GUIDE_PATH = CUSTOM_DOCS_DIR / "Where to start across 17 folders.md"
if not START_GUIDE_PATH.exists():
    START_GUIDE_PATH = SAMPLE_DATA_DIR / "Guide" / "Where to start across 17 folders.md"

ANOMALY_GUIDE_PATH = CUSTOM_DOCS_DIR / "ANOMALY_INVESTIGATION_GUIDE.md"
if not ANOMALY_GUIDE_PATH.exists():
    ANOMALY_GUIDE_PATH = SAMPLE_DATA_DIR / "Dataset & Reference Materials" / "ANOMALY_INVESTIGATION_GUIDE.md"

CATALOG_PATH = CUSTOM_DOCS_DIR / "COMMON_ANOMALY_CATALOG.md"
if not CATALOG_PATH.exists():
    CATALOG_PATH = SAMPLE_DATA_DIR / "Dataset & Reference Materials" / "COMMON_ANOMALY_CATALOG.md"

METHODOLOGY_PATH = CUSTOM_DOCS_DIR / "DATASET_METHODOLOGY.md"
if not METHODOLOGY_PATH.exists():
    METHODOLOGY_PATH = SAMPLE_DATA_DIR / "Dataset & Reference Materials" / "DATASET_METHODOLOGY.md"

INDEX_GUIDE_PATH = CUSTOM_DOCS_DIR / "INDEX.md"
if not INDEX_GUIDE_PATH.exists():
    INDEX_GUIDE_PATH = SAMPLE_DATA_DIR / "Dataset & Reference Materials" / "INDEX.md"

GUIDE_DIR = SAMPLE_DATA_DIR / "Guide" / "Windows Troubleshooting Guide"
LABELED_DATA_DIR = SAMPLE_DATA_DIR / "Dataset & Reference Materials" / "labeled_by_category"

# Output Paths
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
RAG_CACHE_DIR = OUTPUT_DIR / "rag_cache"
RAG_CACHE_DIR.mkdir(exist_ok=True, parents=True)

# Luna 5.6 API Configuration. Luna is opt-in and requires an environment key.
LUNA_ENABLED = os.getenv("LUNA_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
LUNA_API_KEY = os.getenv("LUNA_API_KEY", "")
LUNA_BASE_URL = os.getenv("LUNA_BASE_URL", "https://llm-api-cis.azure-intlsd-np.nielsencsp.net/")
LUNA_MODEL = os.getenv("LUNA_MODEL", "hack-fest-gpt-5.6-luna")

# Detection Thresholds
CLUSTER_WINDOW_SECONDS = 180
CLUSTER_MIN_DISTINCT_PROCESSES = 4
APP_RECURRENCE_HIGH_THRESHOLD = 5
APP_RECURRENCE_MED_THRESHOLD = 3
APP_RECURRENCE_POSSIBLE_THRESHOLD = 2
DISK_FREE_CRITICAL_PERCENT = 5.0
DISK_FREE_WARNING_PERCENT = 15.0
MEMORY_AVAILABLE_CRITICAL_MB = 1500
MEMORY_FREE_WARNING_PERCENT = 10.0
STABILITY_DROP_THRESHOLD = 2.0
