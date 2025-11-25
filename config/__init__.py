"""Configuration module for AEA JOE Automation Tool."""

import shutil
import logging
from pathlib import Path

# Auto-copy settings.example.py to settings.py if it doesn't exist
_CONFIG_DIR = Path(__file__).parent
_SETTINGS_FILE = _CONFIG_DIR / "settings.py"
_EXAMPLE_FILE = _CONFIG_DIR / "settings.example.py"

if not _SETTINGS_FILE.exists() and _EXAMPLE_FILE.exists():
    try:
        shutil.copy2(_EXAMPLE_FILE, _SETTINGS_FILE)
        logger = logging.getLogger(__name__)
        logger.info(f"Created {_SETTINGS_FILE} from {_EXAMPLE_FILE}")
    except (OSError, PermissionError) as e:
        # If we can't create the file, log a warning but continue
        # The import will fail later, but at least we tried
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not auto-create {_SETTINGS_FILE}: {e}")

from .settings import *

