"""Database operations for job postings."""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from config.settings import DATABASE_PATH
from database.models import JOB_POSTINGS_SCHEMA, CREATE_INDEXES

# Configure logging with datetime prefix
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = None
    try:
        # Ensure data directory exists
        db_path = Path(DATABASE_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()


def init_database():
    """Initialize the database with tables and indexes."""
    try:
        with get_db_connection() as conn:
            conn.executescript(JOB_POSTINGS_SCHEMA)
            conn.executescript(CREATE_INDEXES)
            logger.info(f"Database initialized at {DATABASE_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def add_job(job_data: Dict[str, Any]) -> bool:
    """Add a new job posting to the database."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO job_postings (
                    job_id, title, institution, position_type, field, level,
                    deadline, location, description, requirements, contact_info,
                    posted_date, last_updated, fit_score, application_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_data.get('job_id'),
                job_data.get('title'),
                job_data.get('institution'),
                job_data.get('position_type'),
                job_data.get('field'),
                job_data.get('level'),
                job_data.get('deadline'),
                job_data.get('location'),
                job_data.get('description'),
                job_data.get('requirements'),
                job_data.get('contact_info'),
                job_data.get('posted_date'),
                datetime.now().isoformat(),
                job_data.get('fit_score'),
                job_data.get('application_status', 'new')
            ))
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to add job {job_data.get('job_id')}: {e}")
        return False


def update_job(job_id: str, job_data: Dict[str, Any]) -> bool:
    """Update an existing job posting."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            # Build update query dynamically based on provided fields
            fields = []
            values = []
            for key, value in job_data.items():
                if key != 'job_id' and value is not None:
                    fields.append(f"{key} = ?")
                    values.append(value)
            
            if not fields:
                return False
            
            values.append(datetime.now().isoformat())  # last_updated
            values.append(job_id)
            
            query = f"""
                UPDATE job_postings 
                SET {', '.join(fields)}, last_updated = ?
                WHERE job_id = ?
            """
            cursor.execute(query, values)
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update job {job_id}: {e}")
        return False


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Get a job posting by ID."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM job_postings WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e}")
        return None


def get_all_jobs(
    status: Optional[str] = None,
    min_fit_score: Optional[float] = None,
    order_by: str = "fit_score DESC"
) -> List[Dict[str, Any]]:
    """Get all job postings with optional filters."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM job_postings WHERE 1=1"
            params = []
            
            if status:
                query += " AND application_status = ?"
                params.append(status)
            
            if min_fit_score is not None:
                query += " AND fit_score >= ?"
                params.append(min_fit_score)
            
            query += f" ORDER BY {order_by}"
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get jobs: {e}")
        return []


def mark_expired(deadline_threshold: Optional[str] = None) -> int:
    """Mark jobs as expired based on deadline."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            if deadline_threshold:
                cursor.execute("""
                    UPDATE job_postings 
                    SET application_status = 'expired'
                    WHERE deadline < ? AND application_status != 'expired'
                """, (deadline_threshold,))
            else:
                # Mark jobs with past deadlines
                cursor.execute("""
                    UPDATE job_postings 
                    SET application_status = 'expired'
                    WHERE deadline < date('now') AND application_status != 'expired'
                """)
            return cursor.rowcount
    except Exception as e:
        logger.error(f"Failed to mark expired jobs: {e}")
        return 0


def update_fit_score(job_id: str, fit_score: float) -> bool:
    """Update the fit score for a job."""
    return update_job(job_id, {'fit_score': fit_score})


def update_status(job_id: str, status: str) -> bool:
    """Update the application status for a job."""
    valid_statuses = ['new', 'applied', 'expired', 'rejected', 'accepted']
    if status not in valid_statuses:
        logger.warning(f"Invalid status '{status}', using 'new'")
        status = 'new'
    return update_job(job_id, {'application_status': status})

