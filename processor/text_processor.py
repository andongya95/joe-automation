"""Text processing utilities for cleaning and extracting text."""

import re
import logging
from typing import Optional
from pathlib import Path

try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

# Configure logging with datetime prefix
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def clean_text(text: str) -> str:
    """Clean and normalize text."""
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove special characters but keep basic punctuation
    text = text.strip()
    
    # Normalize encoding issues
    text = text.encode('utf-8', errors='ignore').decode('utf-8')
    
    return text


def extract_text_from_pdf(pdf_path: str) -> Optional[str]:
    """Extract text from a PDF file."""
    pdf_file = Path(pdf_path)
    
    if not pdf_file.exists():
        logger.warning(f"PDF file not found: {pdf_path}")
        return None
    
    try:
        # Try pdfplumber first (better for complex layouts)
        if HAS_PDFPLUMBER:
            with pdfplumber.open(pdf_path) as pdf:
                text_parts = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                return clean_text('\n'.join(text_parts))
        
        # Fallback to PyPDF2
        if HAS_PYPDF2:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text_parts = []
                for page in pdf_reader.pages:
                    text_parts.append(page.extract_text())
                return clean_text('\n'.join(text_parts))
        
        logger.error("No PDF library available (pdfplumber or PyPDF2)")
        return None
        
    except Exception as e:
        logger.error(f"Failed to extract text from PDF {pdf_path}: {e}")
        return None

