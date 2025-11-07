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
    extracted_deadline DATE,
    location TEXT,
    country TEXT,
    description TEXT,
    application_materials TEXT,
    references_separate_email INTEGER DEFAULT 0,
    requirements TEXT,
    contact_info TEXT,
    posted_date DATE,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fit_score REAL,
    application_status TEXT DEFAULT 'new',
    application_portal_url TEXT,
    requires_separate_application INTEGER DEFAULT 0,
    position_track TEXT,
    difficulty_score REAL,
    difficulty_reasoning TEXT,
    fit_updated_at TIMESTAMP,
    fit_portfolio_hash TEXT
);
"""

# Index for faster queries
CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_fit_score ON job_postings(fit_score DESC);
CREATE INDEX IF NOT EXISTS idx_deadline ON job_postings(deadline);
CREATE INDEX IF NOT EXISTS idx_status ON job_postings(application_status);
CREATE INDEX IF NOT EXISTS idx_last_updated ON job_postings(last_updated);
CREATE INDEX IF NOT EXISTS idx_position_track ON job_postings(position_track);
CREATE INDEX IF NOT EXISTS idx_fit_updated ON job_postings(fit_updated_at);
"""

