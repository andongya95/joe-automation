"""Scraper for downloading and parsing AEA JOE job postings."""

import logging
import hashlib
import requests
import pandas as pd
from typing import List, Dict, Any, Optional
from io import BytesIO

from config.settings import JOE_EXPORT_URL

# Configure logging with datetime prefix
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def download_job_data(url: Optional[str] = None) -> Optional[bytes]:
    """Download job data from AEA JOE export endpoint."""
    if url is None:
        url = JOE_EXPORT_URL
    
    try:
        logger.info(f"Downloading job data from {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        logger.info(f"Successfully downloaded {len(response.content)} bytes")
        return response.content
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download job data: {e}")
        return None


def generate_job_id(institution: str, title: str, additional_data: Optional[str] = None) -> str:
    """Generate a stable job ID from job data."""
    # Combine institution, title, and optional additional data
    combined = f"{institution}|{title}"
    if additional_data:
        combined += f"|{additional_data}"
    
    # Create hash for stable ID
    job_id = hashlib.md5(combined.encode('utf-8')).hexdigest()
    return job_id


def parse_job_listings(data: bytes) -> List[Dict[str, Any]]:
    """Parse XLS/XML data into structured job listings."""
    try:
        # Try to read as Excel file
        try:
            df = pd.read_excel(BytesIO(data), engine='openpyxl')
        except Exception:
            # If that fails, try reading as XML (some XLS files are actually XML)
            try:
                df = pd.read_xml(BytesIO(data))
            except Exception:
                # Last resort: try reading as CSV
                df = pd.read_csv(BytesIO(data))
        
        logger.info(f"Parsed {len(df)} job listings from data")
        
        jobs = []
        for _, row in df.iterrows():
            try:
                # Extract fields using actual AEA JOE column names
                # Use jp_id as primary identifier if available, otherwise generate one
                jp_id = str(row.get('jp_id', '')).strip()
                title = str(row.get('jp_title', '')).strip()
                institution = str(row.get('jp_institution', '')).strip()
                description = str(row.get('jp_full_text', '')).strip()
                location = str(row.get('locations', '')).strip()
                deadline = str(row.get('Application_deadline', '')).strip()
                posted_date = str(row.get('Date_Active', '')).strip()
                section = str(row.get('jp_section', '')).strip()
                keywords = str(row.get('jp_keywords', '')).strip()
                jel_classifications = str(row.get('JEL_Classifications', '')).strip()
                salary_range = str(row.get('jp_salary_range', '')).strip()
                
                # Use jp_id as job_id if available, otherwise generate one
                if jp_id:
                    job_id = jp_id
                else:
                    job_id = generate_job_id(institution, title, posted_date)
                
                job = {
                    'job_id': job_id,
                    'title': title,
                    'institution': institution,
                    'location': location,
                    'description': description,
                    'posted_date': posted_date,
                    'deadline': deadline,
                    'contact_info': '',  # Not available in AEA JOE export
                    'section': section,
                    'keywords': keywords,
                    'jel_classifications': jel_classifications,
                    'salary_range': salary_range,
                }
                
                # Store raw row data for LLM processing
                job['raw_data'] = row.to_dict()
                
                jobs.append(job)
            except Exception as e:
                logger.warning(f"Failed to parse job row: {e}")
                continue
        
        logger.info(f"Successfully parsed {len(jobs)} job listings")
        return jobs
        
    except Exception as e:
        logger.error(f"Failed to parse job listings: {e}")
        return []


def identify_new_postings(
    scraped_jobs: List[Dict[str, Any]],
    existing_job_ids: List[str]
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Identify new vs existing job postings."""
    existing_set = set(existing_job_ids)
    
    new_jobs = []
    existing_jobs = []
    
    for job in scraped_jobs:
        job_id = job.get('job_id')
        if job_id and job_id not in existing_set:
            new_jobs.append(job)
        else:
            existing_jobs.append(job)
    
    logger.info(f"Identified {len(new_jobs)} new jobs and {len(existing_jobs)} existing jobs")
    return new_jobs, existing_jobs

