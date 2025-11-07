"""Main application for AEA JOE Automation Tool."""

import argparse
import logging
import sys
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Configure logging with datetime prefix
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Import modules
from database import (
    init_database, add_job, update_job, get_all_jobs, mark_expired, update_fit_score,
    create_backup_if_changed
)
from scraper import download_job_data, parse_job_listings, identify_new_postings
from processor import extract_job_details, parse_deadlines, classify_position
from matcher import load_portfolio, calculate_fit_score, rank_jobs
from config.settings import VERBOSE, DATABASE_PATH


def setup_logging(verbose: bool = False):
    """Configure logging level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger().setLevel(level)
    if verbose:
        logger.info("Verbose logging enabled")


def scrape_jobs() -> List[Dict[str, Any]]:
    """Scrape jobs from AEA JOE."""
    logger.info("Starting job scraping...")
    
    try:
        # Download data
        data = download_job_data()
        if not data:
            logger.error("Failed to download job data")
            return []
        
        # Parse listings
        jobs = parse_job_listings(data)
        if not jobs:
            logger.warning("No jobs parsed from downloaded data")
            return []
        
        logger.info(f"Successfully scraped {len(jobs)} jobs")
        return jobs
        
    except Exception as e:
        logger.error(f"Error during scraping: {e}", exc_info=True)
        return []


def process_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Process jobs with LLM to extract structured information."""
    logger.info(f"Processing {len(jobs)} jobs with LLM...")
    
    processed_jobs = []
    
    for i, job in enumerate(jobs, 1):
        try:
            logger.info(f"Processing job {i}/{len(jobs)}: {job.get('title', 'Unknown')}")
            
            # Extract job details
            description = job.get('description', '')
            if description:
                details = extract_job_details(description, job.get('raw_data'))
                job.update(details)
            
            # Parse deadline
            deadline_text = job.get('deadline', '')
            if deadline_text:
                parsed_deadline = parse_deadlines(deadline_text)
                if parsed_deadline:
                    job['deadline'] = parsed_deadline
            
            # Classify position
            title = job.get('title', '')
            if title and description:
                classification = classify_position(title, description[:500])
                job.update(classification)
            
            processed_jobs.append(job)
            
        except Exception as e:
            logger.error(f"Error processing job {job.get('job_id', 'unknown')}: {e}")
            # Continue with next job
            processed_jobs.append(job)
    
    logger.info(f"Processed {len(processed_jobs)} jobs")
    return processed_jobs


def _needs_llm_processing(job: Dict[str, Any]) -> bool:
    """Determine whether a job still needs LLM processing for enriched fields."""
    # Helper to check if a string field has meaningful content
    def has_text(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != ''
        return True

    enriched_values = [
        job.get('extracted_deadline'),
        job.get('application_portal_url'),
        job.get('country'),
        job.get('application_materials'),
    ]
    boolean_enriched = [
        job.get('requires_separate_application'),
        job.get('references_separate_email'),
    ]

    has_enriched_text = any(has_text(val) for val in enriched_values)
    has_enriched_bool = any(bool(val) for val in boolean_enriched)

    # If none of the enriched fields have values, the job still needs processing
    return not (has_enriched_text or has_enriched_bool)


def process_jobs_incrementally(limit: Optional[int] = None, skip_processed: bool = True) -> int:
    """Process jobs from database with LLM one by one, saving after each API call."""
    logger.info("Starting incremental LLM processing...")
    
    try:
        # Get jobs that need processing (those without LLM-processed fields)
        all_jobs = get_all_jobs()
        
        if skip_processed:
            jobs_to_process = [
                j for j in all_jobs
                if _needs_llm_processing(j)
            ]
        else:
            jobs_to_process = all_jobs
        
        if limit:
            jobs_to_process = jobs_to_process[:limit]
        
        logger.info(f"Found {len(jobs_to_process)} jobs to process")
        
        processed_count = 0
        
        for i, job in enumerate(jobs_to_process, 1):
            try:
                job_id = job.get('job_id')
                logger.info(f"Processing job {i}/{len(jobs_to_process)}: {job.get('title', 'Unknown')[:60]} (ID: {job_id})")
                
                # Extract job details
                description = job.get('description', '')
                update_data = {}
                
                if description:
                    details = extract_job_details(description, {})
                    if details:
                        # Filter to only include valid database fields
                        valid_fields = {
                            'position_type', 'field', 'level', 'requirements',
                            'extracted_deadline', 'application_portal_url', 'requires_separate_application',
                            'country', 'application_materials', 'references_separate_email'
                        }
                        filtered_details = {k: v for k, v in details.items() if k in valid_fields}
                        # Convert research_areas list to string if present and add to requirements
                        if 'research_areas' in details and details['research_areas']:
                            research_areas_str = ', '.join(details['research_areas']) if isinstance(details['research_areas'], list) else str(details['research_areas'])
                            if 'requirements' in filtered_details:
                                filtered_details['requirements'] += f"\nResearch Areas: {research_areas_str}"
                            else:
                                filtered_details['requirements'] = f"Research Areas: {research_areas_str}"
                        # Convert boolean to integer for database
                        if 'requires_separate_application' in filtered_details:
                            filtered_details['requires_separate_application'] = bool(filtered_details['requires_separate_application'])
                        if 'references_separate_email' in filtered_details:
                            filtered_details['references_separate_email'] = bool(filtered_details['references_separate_email'])
                        # Convert application_materials list to string if present
                        if 'application_materials' in filtered_details and isinstance(filtered_details['application_materials'], list):
                            filtered_details['application_materials'] = ', '.join(filtered_details['application_materials'])
                        update_data.update(filtered_details)
                
                # Parse deadline
                deadline_text = job.get('deadline', '')
                if deadline_text:
                    parsed_deadline = parse_deadlines(deadline_text)
                    if parsed_deadline and parsed_deadline != deadline_text:
                        update_data['deadline'] = parsed_deadline
                
                # Classify position
                title = job.get('title', '')
                if title and description:
                    classification = classify_position(title, description[:500])
                    if classification:
                        # Map field_focus to field if field not already set
                        if 'field_focus' in classification and not update_data.get('field'):
                            update_data['field'] = classification.get('field_focus', '')
                        if 'level' in classification:
                            update_data['level'] = classification.get('level', '')
                        if 'type' in classification:
                            update_data['position_type'] = classification.get('type', '')
                
                # Filter update_data to only include valid database columns
                valid_db_fields = {
                    'title', 'institution', 'position_type', 'field', 'level',
                    'deadline', 'extracted_deadline', 'location', 'country', 'description', 'requirements',
                    'contact_info', 'posted_date', 'fit_score', 'application_status',
                    'application_portal_url', 'requires_separate_application',
                    'application_materials', 'references_separate_email'
                }
                filtered_update = {k: v for k, v in update_data.items() if k in valid_db_fields}
                
                # Save immediately after processing
                if filtered_update:
                    update_job(job_id, filtered_update)
                    processed_count += 1
                    logger.info(f"Saved updates for job {job_id}")
                else:
                    logger.warning(f"No updates extracted for job {job_id}")
                
            except Exception as e:
                logger.error(f"Error processing job {job.get('job_id', 'unknown')}: {e}")
                continue
        
        logger.info(f"Incremental processing complete: {processed_count} jobs updated")
        return processed_count
        
    except Exception as e:
        logger.error(f"Error during incremental processing: {e}", exc_info=True)
        return 0


def match_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Match jobs with portfolio and calculate fit scores."""
    logger.info("Loading portfolio...")
    
    try:
        portfolio = load_portfolio()
        if not portfolio.get('combined_text'):
            logger.warning("No portfolio text available, skipping matching")
            return jobs
        
        logger.info("Calculating fit scores...")
        
        matched_jobs = []
        for job in jobs:
            try:
                fit_score = calculate_fit_score(job, portfolio)
                job['fit_score'] = fit_score
                matched_jobs.append(job)
            except Exception as e:
                logger.error(f"Error calculating fit score for {job.get('job_id')}: {e}")
                job['fit_score'] = 0.0
                matched_jobs.append(job)
        
        # Rank jobs by fit score
        ranked_jobs = rank_jobs(matched_jobs)
        logger.info(f"Matched and ranked {len(ranked_jobs)} jobs")
        
        return ranked_jobs
        
    except Exception as e:
        logger.error(f"Error during matching: {e}", exc_info=True)
        return jobs


def update_database(jobs: List[Dict[str, Any]]) -> tuple[int, int]:
    """Update database with processed jobs."""
    logger.info("Updating database...")
    
    try:
        # Get existing job IDs
        existing_jobs = get_all_jobs()
        existing_ids = {job['job_id'] for job in existing_jobs}
        
        new_count = 0
        updated_count = 0
        
        for job in jobs:
            job_id = job.get('job_id')
            if not job_id:
                logger.warning("Job missing job_id, skipping")
                continue
            
            # Prepare job data for database
            db_job = {
                'job_id': job_id,
                'title': job.get('title'),
                'institution': job.get('institution'),
                'position_type': job.get('position_type'),
                'field': job.get('field'),
                'level': job.get('level'),
                'deadline': job.get('deadline'),
                'extracted_deadline': job.get('extracted_deadline'),
                'location': job.get('location'),
                'country': job.get('country'),
                'description': job.get('description'),
                'requirements': job.get('requirements'),
                'contact_info': job.get('contact_info'),
                'posted_date': job.get('posted_date'),
                'fit_score': job.get('fit_score'),
                'application_status': job.get('application_status', 'new'),
                'application_portal_url': job.get('application_portal_url'),
                'requires_separate_application': job.get('requires_separate_application', False),
                'application_materials': job.get('application_materials'),
                'references_separate_email': job.get('references_separate_email', False),
            }
            
            if job_id in existing_ids:
                # Update existing job - preserve user-edited fields
                existing_job = next((j for j in existing_jobs if j['job_id'] == job_id), None)
                if existing_job:
                    # Preserve user-edited fields that shouldn't be overwritten by scraped data
                    # Only update fields that come from the source (scraped data)
                    # Preserve: application_status, fit_score (if manually set)
                    preserved_fields = {}
                    if existing_job.get('application_status') and existing_job.get('application_status') != 'new':
                        # Preserve user-set status (applied, rejected, expired, etc.)
                        preserved_fields['application_status'] = existing_job.get('application_status')
                    if existing_job.get('fit_score') is not None and db_job.get('fit_score') is None:
                        # Preserve fit_score if scraped data doesn't have one
                        preserved_fields['fit_score'] = existing_job.get('fit_score')
                    
                    # Remove preserved fields from db_job so they don't get overwritten
                    for field in preserved_fields:
                        db_job.pop(field, None)
                    
                    # Update with scraped data (without preserved fields)
                    if update_job(job_id, db_job):
                        updated_count += 1
                else:
                    # Fallback if existing job not found
                    if update_job(job_id, db_job):
                        updated_count += 1
            else:
                # Add new job
                if add_job(db_job):
                    new_count += 1
        
        logger.info(f"Database updated: {new_count} new jobs, {updated_count} updated jobs")
        
        # Mark expired jobs
        expired_count = mark_expired()
        if expired_count > 0:
            logger.info(f"Marked {expired_count} jobs as expired")
        
        return new_count, updated_count
        
    except Exception as e:
        logger.error(f"Error updating database: {e}", exc_info=True)
        return 0, 0


def export_to_csv(output_path: str = "data/exports/job_matches.csv") -> bool:
    """Export job matches to CSV with all relevant fields."""
    # Ensure output directory exists
    from pathlib import Path
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Exporting jobs to {output_path}...")
    
    try:
        # Get all jobs, sorted by fit score
        jobs = get_all_jobs(order_by="fit_score DESC")
        
        if not jobs:
            logger.warning("No jobs to export")
            return False
        
        # Prepare CSV data with key fields only (for visualization)
        fieldnames = [
            'job_id', 'title', 'institution', 'position_type', 'field', 'level',
            'deadline', 'extracted_deadline', 'location', 'country', 'fit_score', 'application_status',
            'posted_date', 'application_portal_url', 'requires_separate_application',
            'application_materials', 'references_separate_email'
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for job in jobs:
                row = {field: job.get(field, '') for field in fieldnames}
                writer.writerow(row)
        
        # Calculate summary statistics
        total_jobs = len(jobs)
        new_jobs = sum(1 for j in jobs if j.get('application_status') == 'new')
        jobs_with_scores = [j for j in jobs if j.get('fit_score')]
        avg_fit_score = sum(j.get('fit_score', 0) or 0 for j in jobs_with_scores) / len(jobs_with_scores) if jobs_with_scores else 0
        
        logger.info(f"Exported {total_jobs} jobs to {output_path}")
        logger.info(f"Summary: {new_jobs} new jobs, average fit score: {avg_fit_score:.2f}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error exporting to CSV: {e}", exc_info=True)
        return False


def import_from_csv(csv_path: str) -> tuple[int, int]:
    """Import changes from CSV file and update database."""
    logger.info(f"Importing changes from {csv_path}...")
    
    try:
        if not Path(csv_path).exists():
            logger.error(f"CSV file not found: {csv_path}")
            return 0, 0
        
        updated_count = 0
        error_count = 0
        
        with open(csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row_num, row in enumerate(reader, 2):  # Start at 2 (1 is header)
                try:
                    job_id = row.get('job_id', '').strip()
                    if not job_id:
                        logger.warning(f"Row {row_num}: Missing job_id, skipping")
                        error_count += 1
                        continue
                    
                    # Check if job exists
                    existing_job = get_job(job_id)
                    if not existing_job:
                        logger.warning(f"Row {row_num}: Job {job_id} not found in database, skipping")
                        error_count += 1
                        continue
                    
                    # Prepare update data (only non-empty fields)
                    update_data = {}
                    for key, value in row.items():
                        if key != 'job_id' and value and value.strip():
                            # Convert fit_score to float if present
                            if key == 'fit_score':
                                try:
                                    update_data[key] = float(value)
                                except ValueError:
                                    logger.warning(f"Row {row_num}: Invalid fit_score '{value}', skipping")
                                    continue
                            else:
                                update_data[key] = value.strip()
                    
                    # Update job if there are changes
                    if update_data:
                        if update_job(job_id, update_data):
                            updated_count += 1
                            logger.debug(f"Updated job {job_id} from CSV row {row_num}")
                        else:
                            error_count += 1
                            logger.warning(f"Failed to update job {job_id} from row {row_num}")
                    else:
                        logger.debug(f"Row {row_num}: No changes for job {job_id}")
                
                except Exception as e:
                    logger.error(f"Error processing CSV row {row_num}: {e}")
                    error_count += 1
                    continue
        
        logger.info(f"CSV import complete: {updated_count} jobs updated, {error_count} errors")
        return updated_count, error_count
        
    except Exception as e:
        logger.error(f"Error importing from CSV: {e}", exc_info=True)
        return 0, 0


def print_summary():
    """Print summary statistics."""
    try:
        jobs = get_all_jobs()
        total = len(jobs)
        
        if total == 0:
            logger.info("No jobs in database")
            return
        
        new_count = sum(1 for j in jobs if j.get('application_status') == 'new')
        applied_count = sum(1 for j in jobs if j.get('application_status') == 'applied')
        expired_count = sum(1 for j in jobs if j.get('application_status') == 'expired')
        
        jobs_with_scores = [j for j in jobs if j.get('fit_score')]
        avg_fit = sum(j.get('fit_score', 0) for j in jobs_with_scores) / len(jobs_with_scores) if jobs_with_scores else 0
        
        logger.info("=" * 50)
        logger.info("Database Summary")
        logger.info("=" * 50)
        logger.info(f"Total jobs: {total}")
        logger.info(f"  New: {new_count}")
        logger.info(f"  Applied: {applied_count}")
        logger.info(f"  Expired: {expired_count}")
        if jobs_with_scores:
            logger.info(f"Average fit score: {avg_fit:.2f}")
            top_jobs = sorted(jobs_with_scores, key=lambda x: x.get('fit_score', 0), reverse=True)[:5]
            logger.info("\nTop 5 matches:")
            for i, job in enumerate(top_jobs, 1):
                logger.info(f"  {i}. {job.get('title', 'Unknown')} at {job.get('institution', 'Unknown')} "
                          f"(Score: {job.get('fit_score', 0):.2f})")
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"Error printing summary: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AEA JOE Automation Tool - Scrape, process, and match job postings"
    )
    parser.add_argument(
        '--update',
        action='store_true',
        help='Force update job database'
    )
    parser.add_argument(
        '--match',
        action='store_true',
        help='Run portfolio matching algorithm'
    )
    parser.add_argument(
        '--export',
        action='store_true',
        help='Export results to CSV'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable detailed logging'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data/exports/job_matches.csv',
        help='Output CSV file path (default: data/exports/job_matches.csv)'
    )
    parser.add_argument(
        '--process',
        action='store_true',
        help='Process jobs with LLM incrementally (saves after each job)'
    )
    parser.add_argument(
        '--process-limit',
        type=int,
        default=None,
        help='Limit number of jobs to process with LLM'
    )
    parser.add_argument(
        '--import-csv',
        type=str,
        default=None,
        help='Import changes from CSV file and update database'
    )
    parser.add_argument(
        '--web',
        action='store_true',
        help='Start web server for database visualization'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5000,
        help='Port for web server (default: 5000)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose or VERBOSE)
    
    logger.info("AEA JOE Automation Tool starting...")
    
    # Initialize database
    try:
        init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)
    
    # Main workflow
    jobs = []
    
    # Step 1: Scrape and save raw data (if --update)
    if args.update:
        # Create backup before updating
        backup_path = create_backup_if_changed()
        if backup_path:
            logger.info(f"Database backed up before update: {backup_path}")
        
        jobs = scrape_jobs()
        if jobs:
            # Save scraped data to database first (without LLM processing)
            new_count, updated_count = update_database(jobs)
            logger.info(f"Scraped data saved: {new_count} new, {updated_count} updated")
        else:
            logger.warning("No jobs scraped, continuing with existing database")
    else:
        logger.info("Skipping scraping (use --update to force update)")
    
    # Step 2: Process with LLM incrementally (if --process)
    if args.process:
        processed_count = process_jobs_incrementally(limit=args.process_limit)
        logger.info(f"LLM processing complete: {processed_count} jobs processed")
    
    # Step 3: Match with portfolio (if --match)
    if args.match:
        jobs = get_all_jobs()
        if jobs:
            jobs = match_jobs(jobs)
            # Update fit scores in database
            for job in jobs:
                if job.get('fit_score') is not None:
                    update_fit_score(job['job_id'], job['fit_score'])
    
    # Step 4: Import from CSV (if --import-csv)
    if args.import_csv:
        updated_count, error_count = import_from_csv(args.import_csv)
        logger.info(f"CSV import complete: {updated_count} updated, {error_count} errors")
    
    # Step 5: Export (if --export)
    if args.export:
        export_to_csv(args.output)
    
    # Print summary
    print_summary()
    
    # Start web server if requested
    if args.web:
        from webapp.app import run_web_server
        logger.info("Starting web server...")
        run_web_server(host='127.0.0.1', port=args.port, debug=args.verbose)
    else:
        logger.info("Tool execution complete")


if __name__ == "__main__":
    main()

