"""Database schema definitions for job postings."""

# SQL schema for job_postings table
JOB_POSTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS job_postings (
    job_id TEXT PRIMARY KEY,
    title TEXT,
    institution TEXT,
    position_type TEXT,
    field TEXT,
    level TEXT,
    deadline DATE,
    location TEXT,
    description TEXT,
    requirements TEXT,
    contact_info TEXT,
    posted_date DATE,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fit_score REAL,
    application_status TEXT DEFAULT 'new'
);
"""

# Index for faster queries
CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_fit_score ON job_postings(fit_score DESC);
CREATE INDEX IF NOT EXISTS idx_deadline ON job_postings(deadline);
CREATE INDEX IF NOT EXISTS idx_status ON job_postings(application_status);
CREATE INDEX IF NOT EXISTS idx_last_updated ON job_postings(last_updated);
"""

