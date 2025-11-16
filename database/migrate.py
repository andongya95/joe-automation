"""Database migration script to add new columns and normalize dates."""

import sqlite3
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Any

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATABASE_PATH

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def _normalize_date(date_value: Any) -> Optional[str]:
    """Normalize a date value to YYYY-MM-DD format for SQLite DATE storage.
    
    Args:
        date_value: Date value that could be a string, datetime object, or None
        
    Returns:
        Date string in YYYY-MM-DD format, or None if invalid/empty
    """
    if date_value is None:
        return None
    
    if isinstance(date_value, datetime):
        return date_value.strftime("%Y-%m-%d")
    
    if not isinstance(date_value, str):
        date_value = str(date_value)
    
    date_value = date_value.strip()
    if not date_value or date_value.lower() in ('null', 'none', ''):
        return None
    
    # If already in YYYY-MM-DD format, validate and return
    try:
        datetime.strptime(date_value, "%Y-%m-%d")
        return date_value
    except ValueError:
        pass
    
    # Handle datetime strings (YYYY-MM-DD HH:MM:SS) - extract just the date part
    try:
        if ' ' in date_value and ':' in date_value:
            # It's a datetime string, extract just the date part
            date_part = date_value.split(' ')[0]
            datetime.strptime(date_part, "%Y-%m-%d")
            return date_part
    except (ValueError, IndexError):
        pass
    
    # Try to parse common date formats and convert to YYYY-MM-DD
    date_formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%Y-%m-%d %H:%M:%S",  # Handle datetime strings
    ]
    
    for fmt in date_formats:
        try:
            date_obj = datetime.strptime(date_value, fmt)
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # If parsing fails, return None (invalid date)
    logger.warning(f"Could not parse date value: {date_value}")
    return None


def normalize_existing_dates():
    """Normalize all existing date fields in the database to YYYY-MM-DD format."""
    db_path = Path(DATABASE_PATH)
    
    if not db_path.exists():
        logger.info("Database doesn't exist yet, skipping date normalization")
        return
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get all jobs with date fields
        cursor.execute("""
            SELECT job_id, deadline, extracted_deadline, posted_date 
            FROM job_postings
            WHERE deadline IS NOT NULL 
               OR extracted_deadline IS NOT NULL 
               OR posted_date IS NOT NULL
        """)
        
        rows = cursor.fetchall()
        logger.info(f"Found {len(rows)} jobs with date fields to check")
        
        updated_count = 0
        for job_id, deadline, extracted_deadline, posted_date in rows:
            updates = []
            params = []
            
            # Normalize each date field
            normalized_deadline = _normalize_date(deadline)
            if normalized_deadline != deadline:
                updates.append("deadline = ?")
                params.append(normalized_deadline)
            
            normalized_extracted = _normalize_date(extracted_deadline)
            if normalized_extracted != extracted_deadline:
                updates.append("extracted_deadline = ?")
                params.append(normalized_extracted)
            
            normalized_posted = _normalize_date(posted_date)
            if normalized_posted != posted_date:
                updates.append("posted_date = ?")
                params.append(normalized_posted)
            
            # Update if any dates were normalized
            if updates:
                params.append(job_id)
                query = f"UPDATE job_postings SET {', '.join(updates)} WHERE job_id = ?"
                cursor.execute(query, params)
                updated_count += 1
        
        conn.commit()
        conn.close()
        
        if updated_count > 0:
            logger.info(f"Normalized dates for {updated_count} jobs")
        else:
            logger.info("All dates are already in correct format")
        
    except Exception as e:
        logger.error(f"Error normalizing dates: {e}", exc_info=True)
        raise


def migrate_database():
    """Add new columns to existing database if they don't exist."""
    db_path = Path(DATABASE_PATH)
    
    if not db_path.exists():
        logger.info("Database doesn't exist yet, will be created on first use")
        return
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get existing columns
        cursor.execute("PRAGMA table_info(job_postings)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        
        logger.info(f"Existing columns: {existing_columns}")
        
        # Add new columns if they don't exist
        new_columns = {
            'extracted_deadline': 'DATE',
            'application_portal_url': 'TEXT',
            'requires_separate_application': 'INTEGER DEFAULT 0',
            'country': 'TEXT',
            'application_materials': 'TEXT',
            'references_separate_email': 'INTEGER DEFAULT 0',
            'position_track': 'TEXT',
            'difficulty_score': 'REAL',
            'difficulty_reasoning': 'TEXT',
            'fit_updated_at': 'TIMESTAMP',
            'fit_portfolio_hash': 'TEXT'
        }
        
        for column_name, column_type in new_columns.items():
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE job_postings ADD COLUMN {column_name} {column_type}")
                    logger.info(f"Added column: {column_name}")
                except sqlite3.OperationalError as e:
                    if "duplicate column" not in str(e).lower():
                        raise
                    logger.warning(f"Column {column_name} already exists")
        
        conn.commit()
        conn.close()
        logger.info("Database migration completed successfully")
        
        # Normalize existing dates after migration
        logger.info("Normalizing existing date fields...")
        normalize_existing_dates()
        
    except Exception as e:
        logger.error(f"Error migrating database: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    migrate_database()

