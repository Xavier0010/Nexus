import logging
import os
from pathlib import Path
from typing import Literal, Optional, Tuple
from dotenv import load_dotenv
from sqlalchemy import create_engine, Engine

load_dotenv()

_log = logging.getLogger("nexus.config")

# - Path(s) -
BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"
LOG_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"

MODEL_PATH = MODEL_DIR / "model.pkl"
SCALER_PATH = MODEL_DIR / "scaler.pkl"
THRESHOLD_PATH = MODEL_DIR / "threshold.pkl"

ANOMALY_LOG_PATH = LOG_DIR / "anomaly_log.json"
FAILED_PAYLOAD_PATH = LOG_DIR / "failed_payloads.jsonl"

SUMMARY_DIR = LOG_DIR / "summary"
DAILY_SUMMARY_DIR = SUMMARY_DIR / "daily"
WEEKLY_SUMMARY_DIR = SUMMARY_DIR / "weekly"


# - Database (Priority: Hosted MySQL/MariaDB) -
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", "3306") or 3306),
    "user":     os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASS", ""),
    "database": os.getenv("DB_NAME", "Asentinel"),
}

MYSQL_URL = (
    f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
    f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
)

# - Database (Alternative 1: Local SQLite fallback) -
# Set SQLITE_DB_PATH in .env to point at the Laravel workspace database.sqlite
SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "")

# - Database (Alternative 2: CSV fallback) -
CSV_FALLBACK_ENABLED = False

# Legacy aliases kept for backwards compatibility
DB_ENABLED = True

# DB Engine
DB_MODE = "none"
ENGINE = None

try:
    ENGINE = create_engine(MYSQL_URL, pool_pre_ping=True)
    with ENGINE.connect():
        DB_MODE = "mysql"
        _log.info("[db] Hosted MySQL connected.")
except Exception:
    if SQLITE_DB_PATH and Path(SQLITE_DB_PATH).is_file():
        try:
            sqlite_url = f"sqlite:///{Path(SQLITE_DB_PATH).as_posix()}"
            ENGINE = create_engine(sqlite_url, pool_pre_ping=True)
            with ENGINE.connect():
                DB_MODE = "sqlite"
                _log.info("[db] SQLite connected.")
        except Exception:
            pass

if DB_MODE == "none":
    DB_MODE = "csv"
    _log.warning("[db] Falling back to CSV mode.")

# Fetch training data from DB
TRAINING_QUERY = """
    SELECT id_log_monitor, id_aplikasi, nama, id_service, url, 
           status, http_status_code, response_time_ms,
           checked_at, created_at, updated_at
    FROM log_monitor
"""

# Fetch new records from DB
FETCH_QUERY = """
    SELECT id_log_monitor, id_aplikasi, nama, id_service, url,
           status, http_status_code, response_time_ms,
           checked_at, created_at, updated_at
    FROM log_monitor
    WHERE id_log_monitor > {last_id}
    ORDER BY id_log_monitor ASC
"""

# - Batch Fetching Interval (every 10 seconds) -
FETCH_INTERVAL_SECONDS = 10


# - Model Hyperparameter(s) -
MODEL_PARAMS = {
    "n_estimators": 200,
    "max_features": 0.8,
    "contamination": "auto",
    "random_state": 42,
    "n_jobs": -1,
}

# - CSV Training Data (without DB) -
TRAINING_CSV = DATA_DIR / "log_monitor.csv"

# Threshold = Nth percentile of training anomaly scores
THRESHOLD_PERCENTILE = 10

# - Strike & Recover Confirmation -
CONFIRM_STRIKES = 3
RECOVER_STRIKES = 3


# - Schedule Retraining -
RETRAIN_SCHEDULE = {
    "hour": "*",
    "minute": 0
}


# - Notifier Configuration -
MONITOR_ENABLED=True
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
NOTIFY_BATCH_LIMIT = 5
MAX_RETRIES = 3
BASE_DELAY = 1.0
COOLDOWN_SECONDS=0
SEND_RECOVERY_ALERTS=True
LOG_LEVEL="INFO"

# - Notifier Priority -
WEBHOOK_WARNING_INTERVAL_SECONDS = 180
CRITICAL_RT_MS = 4000
CRITICAL_SCORE_MULTIPLIER = 1.5
ESCALATE_STRIKES = 10


# Summary Schedule
SUMMARY_SCHEDULE = {
    "hour": 0,
    "minute": 0
}


# - LLM Engine Configuration -
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3") or 0.3)
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "500") or 500)


# - Check Directories Exist -
MODEL_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
