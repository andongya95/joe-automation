#!/usr/bin/env python3
"""Script to verify partial LLM processing progress is saved."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import get_all_jobs, needs_llm_processing

def check_progress():
    """Check how many jobs have been processed vs still need processing."""
    all_jobs = get_all_jobs()
    total = len(all_jobs)
    
    # Count jobs that still need LLM processing
    needs_processing = sum(1 for job in all_jobs if needs_llm_processing(job))
    processed = total - needs_processing
    
    # Count jobs with position_track (key indicator of LLM processing)
    has_position_track = sum(1 for job in all_jobs if job.get('position_track'))
    
    # Count jobs with other LLM fields
    has_extracted_deadline = sum(1 for job in all_jobs if job.get('extracted_deadline'))
    has_application_portal = sum(1 for job in all_jobs if job.get('application_portal_url'))
    has_country = sum(1 for job in all_jobs if job.get('country'))
    
    print("=" * 60)
    print("LLM Processing Progress Check")
    print("=" * 60)
    print(f"Total jobs: {total}")
    print(f"Jobs still needing processing: {needs_processing}")
    print(f"Jobs processed: {processed} ({processed/total*100:.1f}%)")
    print()
    print("Field completion:")
    print(f"  - position_track: {has_position_track}/{total} ({has_position_track/total*100:.1f}%)")
    print(f"  - extracted_deadline: {has_extracted_deadline}/{total} ({has_extracted_deadline/total*100:.1f}%)")
    print(f"  - application_portal_url: {has_application_portal}/{total} ({has_application_portal/total*100:.1f}%)")
    print(f"  - country: {has_country}/{total} ({has_country/total*100:.1f}%)")
    print()
    
    if needs_processing > 0:
        print("✅ Partial progress detected!")
        print(f"   {processed} jobs have been saved to the database.")
        print(f"   If processing was interrupted, you can resume by clicking 'Process with LLM' again.")
    else:
        print("✅ All jobs have been processed!")
    
    print("=" * 60)

if __name__ == "__main__":
    check_progress()

