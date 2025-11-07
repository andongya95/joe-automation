"""Database migration script to add new columns."""

import sqlite3
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DATABASE_PATH

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


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
        
    except Exception as e:
        logger.error(f"Error migrating database: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    migrate_database()

