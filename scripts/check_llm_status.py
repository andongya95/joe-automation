from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DATABASE_PATH


def main() -> None:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    total = cur.execute("SELECT COUNT(*) FROM job_postings").fetchone()[0]

    with_llm = cur.execute(
        """
        SELECT COUNT(*) FROM job_postings
        WHERE extracted_deadline IS NOT NULL
           OR application_portal_url IS NOT NULL
           OR requires_separate_application IS NOT NULL
        """
    ).fetchone()[0]

    with_new = cur.execute(
        """
        SELECT COUNT(*) FROM job_postings
        WHERE (application_materials IS NOT NULL AND TRIM(application_materials) != '')
           OR references_separate_email IS NOT NULL
        """
    ).fetchone()[0]

    with_country = cur.execute(
        """
        SELECT COUNT(*) FROM job_postings
        WHERE country IS NOT NULL AND TRIM(country) != ''
        """
    ).fetchone()[0]

    not_processed = cur.execute(
        """
        SELECT COUNT(*) FROM job_postings
        WHERE extracted_deadline IS NULL
          AND application_portal_url IS NULL
          AND (requires_separate_application IS NULL OR requires_separate_application = 0)
          AND (country IS NULL OR TRIM(country) = '')
          AND (application_materials IS NULL OR TRIM(application_materials) = '')
          AND (references_separate_email IS NULL OR references_separate_email = 0)
        """
    ).fetchone()[0]

    print(f"Total jobs: {total}")
    print(f"Jobs with any LLM fields: {with_llm}")
    print(f"Jobs with materials/refs info: {with_new}")
    print(f"Jobs with country: {with_country}")
    print(f"Jobs missing all new fields: {not_processed}")

    if not_processed:
        sample = cur.execute(
            """
            SELECT job_id, title, institution
            FROM job_postings
            WHERE extracted_deadline IS NULL
              AND application_portal_url IS NULL
              AND (requires_separate_application IS NULL OR requires_separate_application = 0)
              AND (country IS NULL OR TRIM(country) = '')
              AND (application_materials IS NULL OR TRIM(application_materials) = '')
              AND (references_separate_email IS NULL OR references_separate_email = 0)
            LIMIT 5
            """
        ).fetchall()
        print("\nSample jobs missing LLM data:")
        for row in sample:
            print(f" - {row['job_id']} | {row['title']} | {row['institution']}")

    conn.close()


if __name__ == "__main__":
    main()
