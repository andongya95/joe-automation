"""Flask web application for visualizing job postings."""

import logging
import hashlib
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for
from werkzeug.utils import secure_filename
from pathlib import Path
import os
from typing import Dict, Any, Optional, Tuple, List

from database import (
    get_all_jobs, get_job, update_job, init_database,
    add_job, mark_expired, create_backup_if_changed, needs_llm_processing, needs_fit_recompute
)
from scraper import download_job_data, parse_job_listings
from processor import (
    extract_job_details,
    parse_deadlines,
    classify_position,
    extract_job_details_batch,
    parse_deadlines_batch,
    classify_position_batch,
)
from config.settings import PORTFOLIO_PATH, LLM_MAX_CONCURRENCY, LLM_PROCESSING_BATCH_SIZE
from matcher import (
    load_portfolio,
    evaluate_position_track_batch,
)
from matcher.fit_calculator import score_job_with_joint_prompt

# Configure logging with datetime prefix
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


# Configure file upload
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _job_needs_llm(job: Dict[str, Any]) -> bool:
    """Check if a job needs LLM processing."""
    return needs_llm_processing(job)


def _job_needs_fit_recompute(job: Dict[str, Any], portfolio_hash: str) -> bool:
    """Check if a job needs fit/difficulty recomputation."""
    return needs_fit_recompute(job, portfolio_hash)


@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')


@app.route('/portfolio')
def portfolio_page():
    """Render the portfolio management page."""
    return render_template('portfolio.html')


@app.route('/api/jobs', methods=['GET'])
def api_get_jobs():
    """Get all jobs with optional filters."""
    try:
        # Get query parameters
        status = request.args.get('status', None)
        field = request.args.get('field', None)
        level = request.args.get('level', None)
        min_fit_score = request.args.get('min_fit_score', None)
        search = request.args.get('search', None)
        sort_by = request.args.get('sort_by', 'fit_score')
        order = request.args.get('order', 'desc')
        
        # Get all jobs
        jobs = get_all_jobs(status=status, min_fit_score=float(min_fit_score) if min_fit_score else None)
        
        # Apply additional filters
        if field:
            jobs = [j for j in jobs if j.get('field', '').lower() == field.lower()]
        
        if level:
            jobs = [j for j in jobs if j.get('level', '').lower() == level.lower()]
        
        # Apply text search
        if search:
            search_lower = search.lower()
            jobs = [j for j in jobs if (
                search_lower in (j.get('title', '') or '').lower() or
                search_lower in (j.get('institution', '') or '').lower() or
                search_lower in (j.get('description', '') or '').lower() or
                search_lower in (j.get('field', '') or '').lower()
            )]
        
        # Sort jobs (handle None values safely)
        reverse_order = (order.lower() == 'desc')
        if sort_by == 'fit_score':
            jobs.sort(key=lambda x: (x.get('fit_score') or 0) if x.get('fit_score') is not None else 0, reverse=reverse_order)
        elif sort_by == 'deadline':
            jobs.sort(key=lambda x: x.get('deadline') or '', reverse=reverse_order)
        elif sort_by == 'institution':
            jobs.sort(key=lambda x: (x.get('institution') or '').lower() if x.get('institution') else '', reverse=reverse_order)
        elif sort_by == 'title':
            jobs.sort(key=lambda x: (x.get('title') or '').lower() if x.get('title') else '', reverse=reverse_order)
        elif sort_by == 'posted_date':
            jobs.sort(key=lambda x: x.get('posted_date') or '', reverse=reverse_order)
        else:
            # Default sort by fit_score
            jobs.sort(key=lambda x: (x.get('fit_score') or 0) if x.get('fit_score') is not None else 0, reverse=True)
        
        return jsonify({
            'success': True,
            'count': len(jobs),
            'jobs': jobs
        })
    except Exception as e:
        logger.error(f"Error in api_get_jobs: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/jobs/<job_id>', methods=['GET'])
def api_get_job(job_id: str):
    """Get a single job by ID."""
    try:
        job = get_job(job_id)
        if job:
            return jsonify({
                'success': True,
                'job': job
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404
    except Exception as e:
        logger.error(f"Error in api_get_job: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/jobs/<job_id>', methods=['PUT'])
def api_update_job(job_id: str):
    """Update a job."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Check if job exists
        existing_job = get_job(job_id)
        if not existing_job:
            return jsonify({
                'success': False,
                'error': 'Job not found'
            }), 404
        
        # Update job
        success = update_job(job_id, data)
        if success:
            updated_job = get_job(job_id)
            return jsonify({
                'success': True,
                'job': updated_job
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update job'
            }), 500
    except Exception as e:
        logger.error(f"Error in api_update_job: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stats', methods=['GET'])
def api_get_stats():
    """Get summary statistics."""
    try:
        all_jobs = get_all_jobs()
        
        total = len(all_jobs)
        stats = {
            'total': total,
            'by_status': {},
            'avg_fit_score': 0.0,
            'by_field': {},
            'by_level': {}
        }
        
        if total == 0:
            return jsonify({
                'success': True,
                'stats': stats
            })
        
        # Count by status
        for job in all_jobs:
            status = job.get('application_status') or 'new'
            stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
            
            # Count by field
            field = job.get('field') or 'Unknown'
            stats['by_field'][field] = stats['by_field'].get(field, 0) + 1
            
            # Count by level
            level = job.get('level') or 'Unknown'
            stats['by_level'][level] = stats['by_level'].get(level, 0) + 1
        
        # Calculate average fit score
        jobs_with_scores = [j for j in all_jobs if j.get('fit_score') is not None]
        if jobs_with_scores:
            stats['avg_fit_score'] = sum(j.get('fit_score', 0) for j in jobs_with_scores) / len(jobs_with_scores)
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Error in api_get_stats: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _match_job_batch_web(
    job_batch: List[Dict[str, Any]],
    portfolio: Dict[str, str],
    portfolio_hash: str,
    force: bool = False,
) -> Tuple[int, int, List[Dict[str, Any]], int]:
    """Process a batch sequentially for the web API.

    Returns: (batch_saved, batch_errors, sample_results, heuristic_fallbacks)
    """

    timestamp = datetime.now().isoformat()

    batch_saved = 0
    batch_errors = 0
    heuristic_fallbacks = 0
    sample_results: List[Dict[str, Any]] = []

    for index, job in enumerate(job_batch, 1):
        job_id = job.get('job_id')
        if not job_id:
            logger.warning("Skipping job without ID at batch index %d", index)
            continue

        _, recomputed, llm_success = score_job_with_joint_prompt(job, portfolio, force=force)

        if not recomputed:
            logger.info(
                "[Web] Skipping job %s (ID: %s); scores already populated.",
                job.get('title', 'Unknown')[:60],
                job_id,
            )
            continue

        if not llm_success:
            heuristic_fallbacks += 1

        job['fit_updated_at'] = timestamp
        job['fit_portfolio_hash'] = portfolio_hash

        response_sample = {
            'job_id': job.get('job_id'),
            'title': job.get('title'),
            'fit_score': job.get('fit_score'),
            'position_track': job.get('position_track'),
            'difficulty_score': job.get('difficulty_score'),
            'reasoning': job.get('fit_reasoning'),
            'difficulty_reasoning': job.get('difficulty_reasoning'),
        }

        try:
            update_payload = {
                'fit_score': job.get('fit_score'),
                'difficulty_score': job.get('difficulty_score'),
                'difficulty_reasoning': job.get('difficulty_reasoning'),
                'fit_updated_at': timestamp,
                'fit_portfolio_hash': portfolio_hash,
            }
            if update_job(job_id, update_payload):
                batch_saved += 1
                if len(sample_results) < 5:
                    sample_results.append(response_sample)
            else:
                batch_errors += 1
        except Exception as exc:
            logger.error(f"Error updating job {job_id}: {exc}")
            batch_errors += 1

    return batch_saved, batch_errors, sample_results, heuristic_fallbacks


@app.route('/api/match', methods=['POST'])
def api_match_jobs():
    """Calculate fit scores using portfolio materials and update database."""
    try:
        logger.info("Match fit scores triggered from web interface")

        portfolio = load_portfolio()
        combined_text = portfolio.get('combined_text')
        if not combined_text:
            return jsonify({
                'success': False,
                'error': 'Portfolio text unavailable. Upload CV/research statement first.'
            }), 400

        jobs = get_all_jobs()
        if not jobs:
            return jsonify({
                'success': False,
                'error': 'No jobs available to match.'
            }), 400

        request_payload = request.get_json() or {}
        force = bool(request_payload.get('force'))

        jobs_with_ids = [job for job in jobs if job.get('job_id')]
        portfolio_hash = hashlib.sha256(combined_text.encode('utf-8')).hexdigest()

        if force:
            jobs_to_score = jobs_with_ids
        else:
            jobs_to_score = [job for job in jobs_with_ids if _job_needs_fit_recompute(job, portfolio_hash)]

        if not jobs_to_score:
            return jsonify({
                'success': True,
                'message': 'Fit scores already up-to-date; skipped recompute.',
                'updated_count': 0,
                'error_count': 0,
                'heuristic_fallbacks': 0,
                'sample': [],
                'recomputed': 0,
                'skipped': len(jobs_with_ids),
                'force': force,
            })

        logger.info(f"Matching {len(jobs_to_score)} jobs (batch size: {LLM_PROCESSING_BATCH_SIZE})")
        
        total_saved = 0
        total_errors = 0
        heuristic_fallbacks = 0
        sample_results = []
        
        # Process in batches
        for batch_start in range(0, len(jobs_to_score), LLM_PROCESSING_BATCH_SIZE):
            batch_end = min(batch_start + LLM_PROCESSING_BATCH_SIZE, len(jobs_to_score))
            job_batch = jobs_to_score[batch_start:batch_end]
            batch_num = (batch_start // LLM_PROCESSING_BATCH_SIZE) + 1
            total_batches = (len(jobs_to_score) + LLM_PROCESSING_BATCH_SIZE - 1) // LLM_PROCESSING_BATCH_SIZE
            
            logger.info(f"Matching batch {batch_num}/{total_batches} ({len(job_batch)} jobs)...")
            
            batch_saved, batch_errors, batch_samples, batch_fallbacks = _match_job_batch_web(
                job_batch,
                portfolio,
                portfolio_hash,
                force=force,
            )
            total_saved += batch_saved
            total_errors += batch_errors
            heuristic_fallbacks += batch_fallbacks
            sample_results.extend(batch_samples[:5 - len(sample_results)])  # Add samples up to 5 total
            
            logger.info(f"Match batch {batch_num} complete: {batch_saved} saved, {batch_errors} errors. Total: {total_saved}/{len(jobs_to_score)}")

        return jsonify({
            'success': True,
            'message': f'Fit scores updated: {total_saved} jobs, {total_errors} update errors',
            'updated_count': total_saved,
            'error_count': total_errors,
            'heuristic_fallbacks': heuristic_fallbacks,
            'sample': sample_results,
            'recomputed': total_saved,
            'skipped': len(jobs_with_ids) - total_saved,
            'force': force,
        })

    except Exception as e:
        logger.error(f"Error in api_match_jobs: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/fields', methods=['GET'])
def api_get_fields():
    """Get list of unique fields."""
    try:
        all_jobs = get_all_jobs()
        fields = sorted(set(j.get('field') or '' for j in all_jobs if j.get('field')), key=lambda x: x or '')
        return jsonify({
            'success': True,
            'fields': fields
        })
    except Exception as e:
        logger.error(f"Error in api_get_fields: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/countries', methods=['GET'])
def api_get_countries():
    """Get list of unique countries."""
    try:
        all_jobs = get_all_jobs()
        countries = sorted(set(j.get('country') or '' for j in all_jobs if j.get('country')), key=lambda x: x or '')
        return jsonify({
            'success': True,
            'countries': countries
        })
    except Exception as e:
        logger.error(f"Error in api_get_countries: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/levels', methods=['GET'])
def api_get_levels():
    """Get list of unique levels."""
    try:
        all_jobs = get_all_jobs()
        levels = sorted(set(j.get('level') or '' for j in all_jobs if j.get('level')), key=lambda x: x or '')
        return jsonify({
            'success': True,
            'levels': levels
        })
    except Exception as e:
        logger.error(f"Error in api_get_levels: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/scrape', methods=['POST'])
def api_scrape_jobs():
    """Trigger job scraping and update database."""
    try:
        logger.info("Scraping triggered from web interface")
        
        # Create backup before scraping
        backup_path = create_backup_if_changed()
        backup_created = backup_path is not None
        if backup_created:
            logger.info(f"Database backed up before scraping: {backup_path}")
        
        # Download job data
        data = download_job_data()
        if not data:
            return jsonify({
                'success': False,
                'error': 'Failed to download job data'
            }), 500
        
        # Parse job listings
        jobs = parse_job_listings(data)
        if not jobs:
            return jsonify({
                'success': False,
                'error': 'No jobs parsed from downloaded data'
            }), 500
        
        # Get existing job IDs
        existing_jobs = get_all_jobs()
        existing_ids = {job['job_id'] for job in existing_jobs}
        
        # Identify new vs existing jobs
        new_jobs = []
        updated_jobs = []
        
        for job in jobs:
            job_id = job.get('job_id')
            if not job_id:
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
                'location': job.get('location'),
                'description': job.get('description'),
                'requirements': job.get('requirements'),
                'contact_info': job.get('contact_info'),
                'posted_date': job.get('posted_date'),
                'fit_score': job.get('fit_score'),
                'application_status': job.get('application_status', 'new'),
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
                        updated_jobs.append(job_id)
                else:
                    # Fallback if existing job not found
                    if update_job(job_id, db_job):
                        updated_jobs.append(job_id)
            else:
                # Add new job
                if add_job(db_job):
                    new_jobs.append(job_id)
        
        # Mark expired jobs
        mark_expired()

        try:
            pending_llm = sum(
                1 for job in get_all_jobs()
                if needs_llm_processing(job)
            )
        except Exception as pending_error:  # noqa: BLE001
            logger.debug("Failed to compute pending LLM jobs: %s", pending_error)
            pending_llm = None
        
        return jsonify({
            'success': True,
            'message': f'Scraping complete: {len(new_jobs)} new jobs, {len(updated_jobs)} updated',
            'new_count': len(new_jobs),
            'updated_count': len(updated_jobs),
            'total_scraped': len(jobs),
            'backup_created': backup_created,
            'backup_path': backup_path if backup_created else None,
            'pending_llm': pending_llm
        })
        
    except Exception as e:
        logger.error(f"Error in api_scrape_jobs: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/process', methods=['POST'])
def api_process_jobs():
    """Trigger LLM processing for unprocessed jobs."""
    try:
        logger.info("LLM processing triggered from web interface")
        
        # Get limit from request if provided
        data = request.get_json() or {}
        limit = data.get('limit', None)
        
        # Get jobs that need processing
        all_jobs = get_all_jobs()
        jobs_to_process = [j for j in all_jobs if _job_needs_llm(j)]
        
        if limit:
            jobs_to_process = jobs_to_process[:limit]
        
        logger.info(f"Processing {len(jobs_to_process)} jobs with LLM (batch size: {LLM_PROCESSING_BATCH_SIZE})")
        
        total_processed = 0
        total_errors = 0
        
        # Process in batches
        for batch_start in range(0, len(jobs_to_process), LLM_PROCESSING_BATCH_SIZE):
            batch_end = min(batch_start + LLM_PROCESSING_BATCH_SIZE, len(jobs_to_process))
            job_batch = jobs_to_process[batch_start:batch_end]
            batch_num = (batch_start // LLM_PROCESSING_BATCH_SIZE) + 1
            total_batches = (len(jobs_to_process) + LLM_PROCESSING_BATCH_SIZE - 1) // LLM_PROCESSING_BATCH_SIZE
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(job_batch)} jobs)...")
            
            # Process this batch
            batch_processed, batch_errors = _process_job_batch_web(job_batch)
            total_processed += batch_processed
            total_errors += batch_errors
            
            logger.info(f"Batch {batch_num} complete: {batch_processed} saved, {batch_errors} errors. Total: {total_processed}/{len(jobs_to_process)}")

        return jsonify({
            'success': True,
            'message': f'LLM processing complete: {total_processed} jobs processed, {total_errors} errors',
            'processed_count': total_processed,
            'error_count': total_errors,
            'total_processed': len(jobs_to_process)
        })
        
    except Exception as e:
        logger.error(f"Error in api_process_jobs: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def _process_job_batch_web(job_batch: List[Dict[str, Any]]) -> Tuple[int, int]:
    """Process a single batch of jobs with LLM and save immediately (web version)."""
    # Helper to check if a value is meaningful (not None, not empty string)
    def has_meaningful_value(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != ''
        if isinstance(value, bool):
            return True  # Booleans are always meaningful
        return True

    # Prepare batch LLM inputs
    description_inputs = [
        (job['job_id'], job['description'])
        for job in job_batch
        if job.get('job_id') and job.get('description')
    ]
    detail_results = extract_job_details_batch(description_inputs, max_workers=LLM_MAX_CONCURRENCY)

    deadline_inputs = []
    for job in job_batch:
        deadline_text = job.get('deadline')
        if not deadline_text:
            continue
        if len(deadline_text) > 50 or any(word in deadline_text.lower() for word in ['until', 'by', 'before', 'extended']):
            deadline_inputs.append((job['job_id'], deadline_text))
    deadline_results = parse_deadlines_batch(deadline_inputs, max_workers=LLM_MAX_CONCURRENCY)

    classify_inputs = [
        (job['job_id'], job.get('title', ''), job.get('description', ''))
        for job in job_batch
        if job.get('job_id') and job.get('title') and job.get('description')
    ]
    classify_results = classify_position_batch(classify_inputs, max_workers=LLM_MAX_CONCURRENCY)

    position_track_results = evaluate_position_track_batch(job_batch, max_workers=LLM_MAX_CONCURRENCY)

    # Process and save each job in the batch
    batch_processed = 0
    batch_errors = 0
    for job in job_batch:
        try:
            job_id = job.get('job_id')
            description = job.get('description', '')
            update_data: Dict[str, Any] = {}
            existing_job = get_job(job_id) if job_id else {}
            
            details = detail_results.get(job_id, {}) if job_id else {}
            if details:
                valid_fields = {
                    'position_type', 'field', 'level', 'requirements',
                    'extracted_deadline', 'application_portal_url', 'requires_separate_application',
                    'country', 'application_materials', 'references_separate_email'
                }
                filtered_details = {k: v for k, v in details.items() if k in valid_fields and has_meaningful_value(v)}
                
                for key, new_value in filtered_details.items():
                    existing_value = existing_job.get(key)
                    if not has_meaningful_value(existing_value) or (key in ('requirements', 'application_materials') and has_meaningful_value(new_value)):
                        if key == 'requirements' and existing_value and has_meaningful_value(new_value):
                            if new_value not in existing_value:
                                update_data[key] = f"{existing_value}\n{new_value}"
                        else:
                            update_data[key] = new_value
                
                if 'research_areas' in details and details['research_areas']:
                    research_areas_str = ', '.join(details['research_areas']) if isinstance(details['research_areas'], list) else str(details['research_areas'])
                    if 'requirements' in update_data:
                        update_data['requirements'] += f"\nResearch Areas: {research_areas_str}"
                    elif not existing_job.get('requirements'):
                        update_data['requirements'] = f"Research Areas: {research_areas_str}"
                
                if 'requires_separate_application' in filtered_details:
                    update_data['requires_separate_application'] = bool(filtered_details['requires_separate_application'])
                if 'references_separate_email' in filtered_details:
                    update_data['references_separate_email'] = bool(filtered_details['references_separate_email'])
                if 'application_materials' in filtered_details and isinstance(filtered_details['application_materials'], list):
                    update_data['application_materials'] = ', '.join(filtered_details['application_materials'])

            deadline_text = job.get('deadline', '')
            parsed_deadline = None
            if job_id and job_id in deadline_results:
                parsed_deadline = deadline_results[job_id]
            elif deadline_text:
                parsed_deadline = parse_deadlines(deadline_text)
            if parsed_deadline and parsed_deadline != deadline_text and has_meaningful_value(parsed_deadline):
                update_data['deadline'] = parsed_deadline

            classification = classify_results.get(job_id) if job_id else None
            if not classification and job.get('title') and description:
                classification = classify_position(job.get('title', ''), description[:500])
            if classification:
                if 'field_focus' in classification and has_meaningful_value(classification.get('field_focus')):
                    if not has_meaningful_value(existing_job.get('field')) and not update_data.get('field'):
                        update_data['field'] = classification.get('field_focus', '')
                if 'level' in classification and has_meaningful_value(classification.get('level')):
                    if not has_meaningful_value(existing_job.get('level')) and 'level' not in update_data:
                        update_data['level'] = classification.get('level', '')
                if 'type' in classification and has_meaningful_value(classification.get('type')):
                    if not has_meaningful_value(existing_job.get('position_type')) and 'position_type' not in update_data:
                        update_data['position_type'] = classification.get('type', '')

            track_result = position_track_results.get(job_id) if job_id else None
            if track_result:
                update_data['position_track'] = track_result[0]
            elif not job.get('position_track'):
                update_data.setdefault('position_track', 'other academia')

            valid_db_fields = {
                'title', 'institution', 'position_type', 'field', 'level',
                'deadline', 'extracted_deadline', 'location', 'country', 'description', 'requirements',
                'contact_info', 'posted_date', 'fit_score', 'application_status',
                'application_portal_url', 'requires_separate_application',
                'application_materials', 'references_separate_email',
                'position_track', 'difficulty_score', 'difficulty_reasoning'
            }
            filtered_update = {k: v for k, v in update_data.items() if k in valid_db_fields and has_meaningful_value(v)}

            if filtered_update:
                update_job(job_id, filtered_update)
                batch_processed += 1
            else:
                batch_errors += 1

        except Exception as e:
            logger.error(f"Error processing job {job.get('job_id', 'unknown')}: {e}")
            batch_errors += 1
            continue
    
    return batch_processed, batch_errors


@app.route('/api/jobs/batch', methods=['PUT'])
def api_update_jobs_batch():
    """Update multiple jobs at once."""
    try:
        data = request.get_json()
        if not data or 'updates' not in data:
            return jsonify({
                'success': False,
                'error': 'No updates provided'
            }), 400
        
        updates = data['updates']
        updated_count = 0
        error_count = 0
        
        for job_id, job_data in updates.items():
            try:
                existing_job = get_job(job_id)
                if not existing_job:
                    error_count += 1
                    continue
                
                if update_job(job_id, job_data):
                    updated_count += 1
                else:
                    error_count += 1
            except Exception as e:
                logger.error(f"Error updating job {job_id}: {e}")
                error_count += 1
        
        return jsonify({
            'success': True,
            'message': f'Batch update complete: {updated_count} updated, {error_count} errors',
            'updated_count': updated_count,
            'error_count': error_count
        })
        
    except Exception as e:
        logger.error(f"Error in api_update_jobs_batch: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/portfolio', methods=['GET'])
def api_get_portfolio():
    """Get portfolio file status."""
    try:
        portfolio_dir = Path(PORTFOLIO_PATH)
        portfolio_dir.mkdir(parents=True, exist_ok=True)
        
        expected_files = {
            'cv.pdf': 'CV',
            'research_statement.pdf': 'Research Statement',
            'teaching_statement.pdf': 'Teaching Statement'
        }
        
        files_status = []
        for filename, display_name in expected_files.items():
            file_path = portfolio_dir / filename
            exists = file_path.exists()
            try:
                size = file_path.stat().st_size if exists else 0
                size_mb = round(size / (1024 * 1024), 2) if exists else 0
            except Exception:
                size = 0
                size_mb = 0
            
            files_status.append({
                'filename': filename,
                'display_name': display_name,
                'exists': exists,
                'size': size,
                'size_mb': size_mb
            })
        
        # Also check for any other files in portfolio directory
        other_files = []
        if portfolio_dir.exists():
            try:
                for file_path in portfolio_dir.iterdir():
                    if file_path.is_file() and file_path.name not in expected_files:
                        try:
                            size = file_path.stat().st_size
                            size_mb = round(size / (1024 * 1024), 2)
                        except Exception:
                            size = 0
                            size_mb = 0
                        
                        other_files.append({
                            'filename': file_path.name,
                            'display_name': file_path.name,
                            'exists': True,
                            'size': size,
                            'size_mb': size_mb
                        })
            except Exception as e:
                logger.warning(f"Error listing other files: {e}")
        
        # Get portfolio text status
        portfolio = load_portfolio()
        portfolio_status = {
            'cv_loaded': portfolio.get('cv') is not None,
            'research_loaded': portfolio.get('research_statement') is not None,
            'teaching_loaded': portfolio.get('teaching_statement') is not None,
            'combined_text_length': len(portfolio.get('combined_text', ''))
        }
        
        return jsonify({
            'success': True,
            'files': files_status,
            'other_files': other_files,
            'portfolio_status': portfolio_status,
            'portfolio_path': str(portfolio_dir)
        })
    except Exception as e:
        logger.error(f"Error in api_get_portfolio: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/portfolio/upload', methods=['POST'])
def api_upload_portfolio():
    """Upload a portfolio file."""
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': f'File type not allowed. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'
            }), 400
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({
                'success': False,
                'error': f'File too large. Maximum size: {MAX_FILE_SIZE / (1024 * 1024)}MB'
            }), 400
        
        # Get target filename from form or use original
        target_filename = request.form.get('target_filename', file.filename)
        if not target_filename:
            target_filename = file.filename
        
        # Secure the filename
        target_filename = secure_filename(target_filename)
        
        # Ensure portfolio directory exists
        portfolio_dir = Path(PORTFOLIO_PATH)
        portfolio_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = portfolio_dir / target_filename
        file.save(str(file_path))
        
        logger.info(f"Uploaded portfolio file: {target_filename} ({file_size} bytes)")
        
        return jsonify({
            'success': True,
            'message': f'File uploaded successfully: {target_filename}',
            'filename': target_filename,
            'size': file_size
        })
        
    except Exception as e:
        logger.error(f"Error in api_upload_portfolio: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/portfolio/<filename>', methods=['DELETE'])
def api_delete_portfolio_file(filename):
    """Delete a portfolio file."""
    try:
        # Secure filename
        filename = secure_filename(filename)
        file_path = Path(PORTFOLIO_PATH) / filename
        
        if not file_path.exists():
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
        
        # Prevent deleting files outside portfolio directory
        if not str(file_path.resolve()).startswith(str(Path(PORTFOLIO_PATH).resolve())):
            return jsonify({
                'success': False,
                'error': 'Invalid file path'
            }), 400
        
        file_path.unlink()
        logger.info(f"Deleted portfolio file: {filename}")
        
        return jsonify({
            'success': True,
            'message': f'File deleted: {filename}'
        })
        
    except Exception as e:
        logger.error(f"Error in api_delete_portfolio_file: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/portfolio/<filename>', methods=['GET'])
def api_download_portfolio_file(filename):
    """Download/view a portfolio file."""
    try:
        # Secure filename
        filename = secure_filename(filename)
        file_path = Path(PORTFOLIO_PATH) / filename
        
        if not file_path.exists():
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
        
        # Prevent accessing files outside portfolio directory
        if not str(file_path.resolve()).startswith(str(Path(PORTFOLIO_PATH).resolve())):
            return jsonify({
                'success': False,
                'error': 'Invalid file path'
            }), 400
        
        return send_file(str(file_path), as_attachment=False)
        
    except Exception as e:
        logger.error(f"Error in api_download_portfolio_file: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/backups', methods=['GET'])
def api_list_backups():
    """List all database backups."""
    try:
        from database.backup import list_backups
        backups = list_backups()
        return jsonify({
            'success': True,
            'backups': backups,
            'count': len(backups)
        })
    except Exception as e:
        logger.error(f"Error in api_list_backups: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/backups/<backup_filename>', methods=['POST'])
def api_restore_backup(backup_filename):
    """Restore database from a backup."""
    try:
        from database.backup import restore_backup
        success = restore_backup(backup_filename)
        if success:
            return jsonify({
                'success': True,
                'message': f'Database restored from backup: {backup_filename}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to restore backup'
            }), 500
    except Exception as e:
        logger.error(f"Error in api_restore_backup: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/backups/<backup_filename>', methods=['DELETE'])
def api_delete_backup(backup_filename):
    """Delete a backup file."""
    try:
        from database.backup import delete_backup
        success = delete_backup(backup_filename)
        if success:
            return jsonify({
                'success': True,
                'message': f'Backup deleted: {backup_filename}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to delete backup'
            }), 500
    except Exception as e:
        logger.error(f"Error in api_delete_backup: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/backup', methods=['POST'])
def api_create_backup():
    """Manually create a database backup."""
    try:
        from database.backup import create_backup
        backup_path = create_backup()
        if backup_path:
            return jsonify({
                'success': True,
                'message': 'Backup created successfully',
                'backup_path': backup_path
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to create backup'
            }), 500
    except Exception as e:
        logger.error(f"Error in api_create_backup: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


def run_web_server(host='127.0.0.1', port=5000, debug=False):
    """Run the Flask web server."""
    logger.info(f"Starting web server on http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)

