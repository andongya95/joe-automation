"""Example configuration file. Copy this to settings.py and fill in your values."""

import json
import os
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
except ImportError:  # pragma: no cover
    def load_dotenv(*_, **__):
        """Fallback no-op if python-dotenv is not installed."""
        return False

# Load environment variables from .env file
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Secret management helpers
# ---------------------------------------------------------------------------
SECRET_FILE = Path(__file__).with_name("secret.json")


def _load_secrets() -> dict:
    """Load secrets from secret.json if present."""
    if not SECRET_FILE.exists():
        return {}
    try:
        with SECRET_FILE.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


# Cache secrets with file modification time to avoid reloading on every call
_secrets_cache: dict = {}
_secrets_mtime: float = 0
_secrets_size: int = 0


def _reload_secrets_cache():
    """Force reload secrets from disk, updating cache."""
    global _secrets_cache, _secrets_mtime, _secrets_size
    try:
        if SECRET_FILE.exists():
            _secrets_cache = _load_secrets()
            stat = SECRET_FILE.stat()
            _secrets_mtime = stat.st_mtime
            _secrets_size = stat.st_size
        else:
            _secrets_cache = {}
            _secrets_mtime = 0
            _secrets_size = 0
    except OSError:
        _secrets_cache = {}


def _get_secret(key: str, default: str = "") -> str:
    """Read value from env first, then fall back to secret.json.
    
    Reloads secrets from disk if the file has been modified since last load.
    This allows API keys to be updated via the web UI without restarting the app.
    """
    # Check environment variable first (highest priority)
    env_value = os.getenv(key)
    if env_value:
        return env_value
    
    # Reload secrets if file has been modified (check both mtime and size for reliability)
    global _secrets_cache, _secrets_mtime, _secrets_size
    try:
        if SECRET_FILE.exists():
            stat = SECRET_FILE.stat()
            current_mtime = stat.st_mtime
            current_size = stat.st_size
            # Reload if mtime or size changed (more reliable than just mtime)
            # Also reload if cache is empty (first call)
            if (current_mtime != _secrets_mtime or 
                current_size != _secrets_size or 
                not _secrets_cache):
                _reload_secrets_cache()
        else:
            # File was deleted, clear cache
            if _secrets_cache:
                _secrets_cache = {}
                _secrets_mtime = 0
                _secrets_size = 0
    except OSError:
        # If we can't check file, try to reload anyway
        _reload_secrets_cache()
    
    return _secrets_cache.get(key, default) or default

# Database settings
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "job_listings.db"))

# LLM settings
LLM_PROVIDER = _get_secret("LLM_PROVIDER", "deepseek").lower()
DEEPSEEK_API_KEY = _get_secret("DEEPSEEK_API_KEY", "")
OPENAI_API_KEY = _get_secret("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = _get_secret("ANTHROPIC_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-chat")

# LLM concurrency settings
def _get_int_env(key: str, default: int) -> int:
    """Safely get integer from environment variable."""
    try:
        value = os.getenv(key)
        if value is None:
            return default
        return int(value)
    except (ValueError, TypeError):
        import logging
        logging.warning(f"Invalid value for {key}, using default: {default}")
        return default

def _get_float_env(key: str, default: float) -> float:
    """Safely get float from environment variable."""
    try:
        value = os.getenv(key)
        if value is None:
            return default
        return float(value)
    except (ValueError, TypeError):
        import logging
        logging.warning(f"Invalid value for {key}, using default: {default}")
        return default

LLM_MAX_CONCURRENCY = _get_int_env("LLM_MAX_CONCURRENCY", 20)
LLM_MIN_CALL_INTERVAL = _get_float_env("LLM_MIN_CALL_INTERVAL", 1.0)
LLM_PROCESSING_BATCH_SIZE = _get_int_env("LLM_PROCESSING_BATCH_SIZE", 20)  # Process and save in batches

# Scraping settings
SCRAPE_INTERVAL_HOURS = _get_int_env("SCRAPE_INTERVAL_HOURS", 6)
JOE_EXPORT_URL = os.getenv(
    "JOE_EXPORT_URL",
    "https://www.aeaweb.org/joe/resultset_xls_output.php?mode=xls_xml"
)

# Portfolio settings
PORTFOLIO_PATH = os.getenv("PORTFOLIO_PATH", str(BASE_DIR / "portfolio"))

# Matching criteria
# List your research areas/focus areas for portfolio matching
# These are used to calculate fit scores based on alignment with job requirements
RESEARCH_FOCAL_AREAS = [
    # Example entries (uncomment and modify as needed):
    # "labor economics",
    # "applied econometrics",
    # "environmental economics",
    # Add your research areas here
]

# Logging settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
VERBOSE = os.getenv("VERBOSE", "false").lower() == "true"

