"""Scheduler for periodic job scraping and updates."""

import logging
import schedule
import time
from typing import Callable, Optional

from config.settings import SCRAPE_INTERVAL_HOURS

# Configure logging with datetime prefix
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def schedule_updates(update_function: Callable, interval_hours: Optional[int] = None):
    """Schedule periodic updates using the schedule library."""
    if interval_hours is None:
        interval_hours = SCRAPE_INTERVAL_HOURS
    
    schedule.every(interval_hours).hours.do(update_function)
    logger.info(f"Scheduled updates every {interval_hours} hours")


def run_scheduler(update_function: Callable, interval_hours: Optional[int] = None):
    """Run the scheduler in a blocking loop."""
    schedule_updates(update_function, interval_hours)
    
    logger.info("Scheduler started. Press Ctrl+C to stop.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")

