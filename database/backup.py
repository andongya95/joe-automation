"""Database backup functionality."""

import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

from config.settings import DATABASE_PATH

# Configure logging with datetime prefix
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def get_backup_directory() -> Path:
    """Get the backup directory path."""
    db_path = Path(DATABASE_PATH)
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def create_backup(backup_name: Optional[str] = None) -> Optional[str]:
    """Create a backup of the database with date stamp."""
    try:
        db_path = Path(DATABASE_PATH)
        
        if not db_path.exists():
            logger.warning(f"Database file not found: {db_path}, skipping backup")
            return None
        
        backup_dir = get_backup_directory()
        
        # Generate backup filename with date
        if backup_name:
            backup_filename = backup_name
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"job_listings_{timestamp}.db"
        
        backup_path = backup_dir / backup_filename
        
        # Copy database file
        shutil.copy2(db_path, backup_path)
        
        # Get file size
        size_mb = backup_path.stat().st_size / (1024 * 1024)
        
        logger.info(f"Database backup created: {backup_path} ({size_mb:.2f} MB)")
        return str(backup_path)
        
    except Exception as e:
        logger.error(f"Failed to create database backup: {e}", exc_info=True)
        return None


def create_backup_if_changed() -> Optional[str]:
    """Create a backup only if crossing a date boundary (new day)."""
    try:
        db_path = Path(DATABASE_PATH)
        
        if not db_path.exists():
            return None
        
        backup_dir = get_backup_directory()
        
        # Get today's date
        today = datetime.now().date()
        
        # Find most recent backup
        backups = sorted(backup_dir.glob("job_listings_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
        
        # If no backups exist, create one
        if not backups:
            return create_backup()
        
        # Get the date of the most recent backup
        last_backup_time = datetime.fromtimestamp(backups[0].stat().st_mtime)
        last_backup_date = last_backup_time.date()
        
        # Only create backup if crossing a date boundary (new day)
        if today > last_backup_date:
            logger.info(f"Date boundary crossed: last backup was {last_backup_date}, today is {today}")
            return create_backup()
        
        logger.debug(f"No date boundary crossed (last backup: {last_backup_date}, today: {today}), skipping backup")
        return None
        
    except Exception as e:
        logger.error(f"Error checking for backup need: {e}")
        return None


def list_backups() -> list[dict]:
    """List all database backups."""
    try:
        backup_dir = get_backup_directory()
        backups = []
        
        for backup_path in sorted(backup_dir.glob("job_listings_*.db"), reverse=True):
            stat = backup_path.stat()
            backups.append({
                'filename': backup_path.name,
                'path': str(backup_path),
                'size': stat.st_size,
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'created': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'date': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return backups
    except Exception as e:
        logger.error(f"Error listing backups: {e}")
        return []


def restore_backup(backup_filename: str) -> bool:
    """Restore database from a backup."""
    try:
        backup_dir = get_backup_directory()
        backup_path = backup_dir / backup_filename
        
        if not backup_path.exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False
        
        db_path = Path(DATABASE_PATH)
        
        # Create backup of current database before restoring
        if db_path.exists():
            current_backup = create_backup(f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
            if current_backup:
                logger.info(f"Created backup of current database before restore: {current_backup}")
        
        # Restore from backup
        shutil.copy2(backup_path, db_path)
        
        logger.info(f"Database restored from backup: {backup_filename}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to restore backup: {e}", exc_info=True)
        return False


def delete_backup(backup_filename: str) -> bool:
    """Delete a backup file."""
    try:
        backup_dir = get_backup_directory()
        backup_path = backup_dir / backup_filename
        
        if not backup_path.exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False
        
        # Prevent deleting files outside backup directory
        if not str(backup_path.resolve()).startswith(str(backup_dir.resolve())):
            logger.error("Invalid backup path")
            return False
        
        backup_path.unlink()
        logger.info(f"Backup deleted: {backup_filename}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete backup: {e}")
        return False

