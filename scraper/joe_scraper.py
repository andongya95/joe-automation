"""Scraper for downloading and parsing AEA JOE job postings."""

import logging
import hashlib
import requests
import pandas as pd
from typing import List, Dict, Any, Optional
from io import BytesIO
from bs4 import BeautifulSoup
import re

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
                # Handle dates - pandas may return Timestamp objects
                deadline_raw = row.get('Application_deadline')
                if deadline_raw is not None and hasattr(deadline_raw, 'strftime'):
                    # It's a pandas Timestamp or datetime object
                    deadline = deadline_raw.strftime("%Y-%m-%d")
                elif pd.notna(deadline_raw):
                    deadline = str(deadline_raw).strip()
                else:
                    deadline = ''
                
                posted_date_raw = row.get('Date_Active')
                if posted_date_raw is not None and hasattr(posted_date_raw, 'strftime'):
                    # It's a pandas Timestamp or datetime object
                    posted_date = posted_date_raw.strftime("%Y-%m-%d")
                elif pd.notna(posted_date_raw):
                    posted_date = str(posted_date_raw).strip()
                else:
                    posted_date = ''
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


def scrape_listing_by_id(job_id: str) -> Optional[Dict[str, Any]]:
    """Scrape a single AEA JOE listing by ID from the HTML page.
    
    Args:
        job_id: The AEA JOE listing ID (e.g., "12345")
        
    Returns:
        Dictionary with job data in the same format as parse_job_listings, or None if failed
    """
    url = f"https://www.aeaweb.org/joe/listing.php?JOE_ID={job_id}"
    
    try:
        logger.info(f"Scraping listing {job_id} from {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract job details from the HTML page
        # The structure may vary, so we'll try to extract common fields
        job = {
            'job_id': job_id,
            'title': '',
            'institution': '',
            'location': '',
            'description': '',
            'posted_date': '',
            'deadline': '',
            'contact_info': '',
            'section': '',
            'keywords': '',
            'jel_classifications': '',
            'salary_range': '',
        }
        
        # Try to find the main content area
        # AEA JOE pages typically have structured content
        # Look for common patterns in the HTML
        
        # Title - usually in a heading or specific div
        title_elem = soup.find('h1') or soup.find('h2') or soup.find(class_=re.compile(r'title', re.I))
        if title_elem:
            job['title'] = title_elem.get_text(strip=True)
        
        # Institution - often near the title
        inst_elem = soup.find(string=re.compile(r'institution', re.I))
        if inst_elem:
            parent = inst_elem.find_parent()
            if parent:
                # Get text after "Institution:" or similar
                text = parent.get_text(strip=True)
                if ':' in text:
                    job['institution'] = text.split(':', 1)[1].strip()
        
        # Description - usually in a div with class containing "description" or "full_text"
        desc_elem = soup.find(class_=re.compile(r'description|full.text|content', re.I))
        if desc_elem:
            job['description'] = desc_elem.get_text(separator='\n', strip=True)
        
        # If description is still empty, try to get all paragraph text
        if not job['description']:
            paragraphs = soup.find_all('p')
            if paragraphs:
                job['description'] = '\n'.join(p.get_text(strip=True) for p in paragraphs)
        
        # Location
        loc_elem = soup.find(string=re.compile(r'location', re.I))
        if loc_elem:
            parent = loc_elem.find_parent()
            if parent:
                text = parent.get_text(strip=True)
                if ':' in text:
                    job['location'] = text.split(':', 1)[1].strip()
        
        # Deadline
        deadline_elem = soup.find(string=re.compile(r'deadline|application.deadline', re.I))
        if deadline_elem:
            parent = deadline_elem.find_parent()
            if parent:
                text = parent.get_text(strip=True)
                # Try to extract date
                date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)
                if date_match:
                    job['deadline'] = date_match.group(1)
        
        # Posted date
        posted_elem = soup.find(string=re.compile(r'posted|date.active', re.I))
        if posted_elem:
            parent = posted_elem.find_parent()
            if parent:
                text = parent.get_text(strip=True)
                date_match = re.search(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', text)
                if date_match:
                    job['posted_date'] = date_match.group(1)
        
        # JEL Classifications
        jel_elem = soup.find(string=re.compile(r'jel|classification', re.I))
        if jel_elem:
            parent = jel_elem.find_parent()
            if parent:
                text = parent.get_text(strip=True)
                if ':' in text:
                    job['jel_classifications'] = text.split(':', 1)[1].strip()
        
        # If we couldn't extract much, try downloading the full export and filtering
        # This is a fallback if HTML parsing doesn't work well
        if not job['title'] and not job['institution']:
            logger.warning(f"Could not extract job details from HTML for {job_id}, trying export method")
            return scrape_listing_from_export(job_id)
        
        logger.info(f"Successfully scraped listing {job_id}: {job.get('title', 'N/A')}")
        return job
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download listing {job_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to parse listing {job_id}: {e}")
        return None


def scrape_listing_from_export(job_id: str) -> Optional[Dict[str, Any]]:
    """Scrape a listing by downloading the full export and filtering for the specific ID.
    
    This is a fallback method when HTML parsing doesn't work well.
    
    Args:
        job_id: The AEA JOE listing ID
        
    Returns:
        Dictionary with job data, or None if not found
    """
    try:
        logger.info(f"Attempting to find listing {job_id} in full export")
        data = download_job_data()
        if not data:
            return None
        
        jobs = parse_job_listings(data)
        for job in jobs:
            if job.get('job_id') == job_id:
                logger.info(f"Found listing {job_id} in export")
                return job
        
        logger.warning(f"Listing {job_id} not found in export")
        return None
        
    except Exception as e:
        logger.error(f"Failed to scrape listing {job_id} from export: {e}")
        return None

