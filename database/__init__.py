"""Database module for job posting storage and management."""

from .job_db import (
    init_database,
    add_job,
    update_job,
    get_job,
    get_all_jobs,
    mark_expired,
    update_fit_score,
    update_status,
)
from .backup import (
    create_backup,
    create_backup_if_changed,
    list_backups,
    restore_backup,
    delete_backup,
)

__all__ = [
    "init_database",
    "add_job",
    "update_job",
    "get_job",
    "get_all_jobs",
    "mark_expired",
    "update_fit_score",
    "update_status",
    "create_backup",
    "create_backup_if_changed",
    "list_backups",
    "restore_backup",
    "delete_backup",
]

