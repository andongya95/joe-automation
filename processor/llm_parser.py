"""LLM parser for extracting structured information from job descriptions."""

import logging
import json
import time
from typing import Dict, Any, Optional, List
from datetime import datetime

from config.settings import (
    LLM_PROVIDER,
    DEEPSEEK_API_KEY,
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    MODEL_NAME,
)

# Configure logging with datetime prefix
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Rate limiting
_last_api_call = 0
_min_call_interval = 1.0  # Minimum seconds between API calls


def _rate_limit():
    """Implement rate limiting for API calls."""
    global _last_api_call
    elapsed = time.time() - _last_api_call
    if elapsed < _min_call_interval:
        time.sleep(_min_call_interval - elapsed)
    _last_api_call = time.time()


def _call_deepseek(prompt: str, system_prompt: str = "") -> Optional[str]:
    """Call DeepSeek API."""
    try:
        from openai import OpenAI
        
        if not DEEPSEEK_API_KEY:
            logger.error("DeepSeek API key not configured")
            return None
        
        _rate_limit()
        client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com"
        )
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.3,
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"DeepSeek API error: {e}")
        return None


def _call_openai(prompt: str, system_prompt: str = "") -> Optional[str]:
    """Call OpenAI API."""
    try:
        from openai import OpenAI
        
        if not OPENAI_API_KEY:
            logger.error("OpenAI API key not configured")
            return None
        
        _rate_limit()
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model=MODEL_NAME if MODEL_NAME != "deepseek-chat" else "gpt-4-turbo-preview",
            messages=messages,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return None


def _call_anthropic(prompt: str, system_prompt: str = "") -> Optional[str]:
    """Call Anthropic API."""
    try:
        import anthropic
        
        if not ANTHROPIC_API_KEY:
            logger.error("Anthropic API key not configured")
            return None
        
        _rate_limit()
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        
        system_msg = system_prompt if system_prompt else "You are a helpful assistant."
        
        response = client.messages.create(
            model=MODEL_NAME if MODEL_NAME != "deepseek-chat" else "claude-3-opus-20240229",
            max_tokens=4096,
            system=system_msg,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )
        
        return response.content[0].text
    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        return None


def _call_llm(prompt: str, system_prompt: str = "") -> Optional[str]:
    """Call the configured LLM provider."""
    provider = LLM_PROVIDER.lower()
    
    if provider == "deepseek":
        return _call_deepseek(prompt, system_prompt)
    elif provider == "openai":
        return _call_openai(prompt, system_prompt)
    elif provider == "anthropic":
        return _call_anthropic(prompt, system_prompt)
    else:
        logger.error(f"Unknown LLM provider: {provider}")
        return None


def extract_job_details(job_description: str, raw_data: Optional[Dict] = None) -> Dict[str, Any]:
    """Extract structured job details using LLM."""
    system_prompt = """You are an expert at parsing job postings. Extract structured information from job descriptions.
Return a JSON object with the following fields:
- position_type: Type of position (e.g., "Assistant Professor", "Postdoc", "Research Associate")
- field: Primary field of economics (e.g., "Public Economics", "Development Economics", "Microeconomics")
- level: Position level (e.g., "Assistant", "Associate", "Postdoc", "Senior")
- requirements: Key requirements and qualifications (as a string)
- research_areas: List of research areas mentioned
- teaching_load: Teaching requirements if mentioned
- location_preference: Geographic location preferences if mentioned
- extracted_deadline: Application deadline date extracted from the description text (in YYYY-MM-DD format, or null if not found)
- requires_separate_application: Boolean indicating if the job requires applying through a separate platform/portal (not just AEA JOE)
- application_portal_url: URL of the application portal/website if mentioned (e.g., "https://jobs.university.edu/apply"), or null if not found
- country: Country name extracted from location field (e.g., "United States", "Canada", "United Kingdom")
- application_materials: List of required application materials mentioned in the description (e.g., ["CV", "Cover Letter", "Research Statement", "Teaching Statement", "Writing Sample", "Transcripts"])
- references_separate_email: Boolean indicating if reference letters need to be sent to a separate email address (different from the main application)"""

    prompt = f"""Extract structured information from this job posting:

{job_description}

Return only valid JSON with the fields specified. 
- For extracted_deadline, parse any date mentioned in the text.
- For application_portal_url, look for URLs to application systems, HR portals, or university job sites.
- For country, extract the country name from the location information.
- For application_materials, list all required materials mentioned (CV, cover letter, statements, transcripts, etc.).
- For references_separate_email, check if references should be sent to a different email address than the main application."""
    
    try:
        response = _call_llm(prompt, system_prompt)
        if not response:
            return {}
        
        # Try to parse JSON response
        try:
            # Remove markdown code blocks if present
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
                response = response.strip()
            
            data = json.loads(response)
            logger.info("Successfully extracted job details")
            return data
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Response was: {response}")
            return {}
    except Exception as e:
        logger.error(f"Failed to extract job details: {e}")
        return {}


def parse_deadlines(deadline_text: str) -> Optional[str]:
    """Parse and normalize deadline dates."""
    if not deadline_text:
        return None
    
    # Try to extract date using LLM if text is complex
    if len(deadline_text) > 50 or any(word in deadline_text.lower() for word in ['until', 'by', 'before', 'extended']):
        system_prompt = "Extract the deadline date from text. Return only the date in YYYY-MM-DD format, or null if no date found."
        prompt = f"Extract the deadline date from: {deadline_text}\nReturn only YYYY-MM-DD or null."
        
        response = _call_llm(prompt, system_prompt)
        if response:
            response = response.strip().strip('"').strip("'")
            # Validate date format
            try:
                datetime.strptime(response, "%Y-%m-%d")
                return response
            except ValueError:
                pass
    
    # Try simple parsing
    try:
        # Common date formats
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y"]:
            try:
                date_obj = datetime.strptime(deadline_text.strip(), fmt)
                return date_obj.strftime("%Y-%m-%d")
            except ValueError:
                continue
    except Exception:
        pass
    
    return deadline_text.strip()  # Return as-is if parsing fails


def classify_position(title: str, description: str) -> Dict[str, str]:
    """Classify position level and type."""
    system_prompt = """Classify the job position. Return JSON with:
- level: "Assistant", "Associate", "Full", "Postdoc", "Other"
- type: "Tenure-track", "Tenured", "Non-tenure", "Postdoc", "Other"
- field_focus: Primary field (e.g., "Public Economics", "Development Economics")"""

    prompt = f"""Classify this position:

Title: {title}
Description: {description[:500]}

Return only valid JSON."""
    
    try:
        response = _call_llm(prompt, system_prompt)
        if not response:
            return {"level": "Other", "type": "Other", "field_focus": ""}
        
        # Parse JSON
        try:
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
                response = response.strip()
            
            data = json.loads(response)
            return data
        except json.JSONDecodeError:
            return {"level": "Other", "type": "Other", "field_focus": ""}
    except Exception as e:
        logger.error(f"Failed to classify position: {e}")
        return {"level": "Other", "type": "Other", "field_focus": ""}

