"""Portfolio reader for loading and parsing job market materials."""

import logging
from pathlib import Path
from typing import Dict, Optional

from config.settings import PORTFOLIO_PATH
from processor.text_processor import extract_text_from_pdf, clean_text

# Configure logging with datetime prefix
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_portfolio() -> Dict[str, str]:
    """Load portfolio materials (CV, research statement, teaching statement)."""
    portfolio_dir = Path(PORTFOLIO_PATH)
    portfolio = {
        'cv': None,
        'research_statement': None,
        'teaching_statement': None,
    }
    
    if not portfolio_dir.exists():
        logger.warning(f"Portfolio directory not found: {portfolio_dir}")
        return portfolio
    
    # Load CV
    cv_path = portfolio_dir / "cv.pdf"
    if cv_path.exists():
        cv_text = extract_text_from_pdf(str(cv_path))
        if cv_text:
            portfolio['cv'] = cv_text
            logger.info(f"Loaded CV from {cv_path}")
        else:
            logger.warning(f"Failed to extract text from CV: {cv_path}")
    else:
        logger.warning(f"CV not found: {cv_path}")
    
    # Load research statement
    research_path = portfolio_dir / "research_statement.pdf"
    if research_path.exists():
        research_text = extract_text_from_pdf(str(research_path))
        if research_text:
            portfolio['research_statement'] = research_text
            logger.info(f"Loaded research statement from {research_path}")
        else:
            logger.warning(f"Failed to extract text from research statement: {research_path}")
    else:
        logger.warning(f"Research statement not found: {research_path}")
    
    # Load teaching statement (optional)
    teaching_path = portfolio_dir / "teaching_statement.pdf"
    if teaching_path.exists():
        teaching_text = extract_text_from_pdf(str(teaching_path))
        if teaching_text:
            portfolio['teaching_statement'] = teaching_text
            logger.info(f"Loaded teaching statement from {teaching_path}")
        else:
            logger.warning(f"Failed to extract text from teaching statement: {teaching_path}")
    
    # Combine all text for analysis
    all_text = []
    for key, text in portfolio.items():
        if text:
            all_text.append(text)
    
    portfolio['combined_text'] = clean_text('\n\n'.join(all_text))
    
    logger.info(f"Portfolio loaded: CV={portfolio['cv'] is not None}, "
                f"Research={portfolio['research_statement'] is not None}, "
                f"Teaching={portfolio['teaching_statement'] is not None}")
    
    return portfolio


def extract_qualifications(portfolio: Dict[str, str]) -> Dict[str, any]:
    """Extract key qualifications from portfolio."""
    qualifications = {
        'education': [],
        'experience': [],
        'research_areas': [],
        'publications': [],
        'skills': [],
    }
    
    combined_text = portfolio.get('combined_text', '').lower()
    
    # Extract research areas (from config or portfolio)
    from config.settings import RESEARCH_FOCAL_AREAS
    for area in RESEARCH_FOCAL_AREAS:
        if area.lower() in combined_text:
            qualifications['research_areas'].append(area)
    
    # Look for common qualification keywords
    if 'ph.d' in combined_text or 'phd' in combined_text or 'doctorate' in combined_text:
        qualifications['education'].append('Ph.D. in Economics')
    
    if 'postdoc' in combined_text or 'post-doc' in combined_text:
        qualifications['experience'].append('Postdoc experience')
    
    if 'hku' in combined_text or 'hong kong' in combined_text:
        qualifications['experience'].append('Postdoc at HKU')
    
    return qualifications

