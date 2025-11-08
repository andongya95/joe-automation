"""LLM parser for extracting structured information from job descriptions."""

import json
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, List, Callable, Tuple, TypeVar
from datetime import datetime

from config.settings import (
    LLM_PROVIDER,
    DEEPSEEK_API_KEY,
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
    MODEL_NAME,
    LLM_MAX_CONCURRENCY,
    LLM_MIN_CALL_INTERVAL,
)
from processor.level_normalizer import normalize_level_labels as _normalize_levels

# Configure logging with datetime prefix
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Rate limiting
_last_api_call = 0
_min_call_interval = LLM_MIN_CALL_INTERVAL
_rate_limit_lock = threading.Lock()

_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()


def _rate_limit():
    """Implement rate limiting for API calls."""
    global _last_api_call
    with _rate_limit_lock:
        elapsed = time.time() - _last_api_call
        sleep_time = _min_call_interval - elapsed
        if sleep_time < 0:
            sleep_time = 0
        # Reserve the next slot before releasing the lock to avoid race conditions
        _last_api_call = time.time() + sleep_time

    if sleep_time > 0:
        time.sleep(sleep_time)


def _get_executor(max_workers: Optional[int] = None) -> ThreadPoolExecutor:
    """Get or create a shared thread pool for LLM calls."""
    global _executor
    with _executor_lock:
        if _executor is None:
            workers = max(1, max_workers or LLM_MAX_CONCURRENCY)
            _executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="llm-worker")
        return _executor


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


def _clean_llm_json(response: str) -> Optional[Dict[str, Any]]:
    """Attempt to parse an LLM response containing JSON."""
    response = response.strip()
    if response.startswith("```"):
        parts = response.split("```")
        if len(parts) > 1:
            response = parts[1]
            if response.startswith("json"):
                response = response[4:]
        response = response.strip()

    try:
        return json.loads(response)
    except json.JSONDecodeError as err:
        logger.warning("Failed to parse LLM JSON response: %s", err)
        logger.debug("Response body: %s", response)
        return None


T = TypeVar('T')


def normalize_level_labels(raw_levels, job_title: str = "", job_description: str = "") -> List[str]:
    """Public wrapper around the level normalizer helper."""
    return _normalize_levels(raw_levels, job_title, job_description)


def execute_llm_tasks(
    tasks: List[Tuple[str, Callable[[], T]]],
    max_workers: Optional[int] = None
) -> Dict[str, Optional[T]]:
    """Execute multiple LLM callables concurrently.

    Args:
        tasks: List of tuples (task_id, callable) where callable returns the LLM response.
        max_workers: Optional cap on concurrency.

    Returns:
        Mapping of task_id to response (or None on failure).
    """

    if not tasks:
        return {}

    total_tasks = len(tasks)
    logger.info("Dispatching %d LLM task(s) with concurrency <= %d", total_tasks, max_workers or LLM_MAX_CONCURRENCY)

    executor = _get_executor(max_workers)
    futures = {executor.submit(task): task_id for task_id, task in tasks}
    results: Dict[str, Optional[T]] = {}
    completed = 0

    for future in as_completed(futures):
        task_id = futures[future]
        try:
            results[task_id] = future.result()
        except Exception as exc:  # noqa: BLE001
            logger.error("LLM task %s failed: %s", task_id, exc)
            results[task_id] = None
        finally:
            completed += 1
            if completed % 10 == 0 or completed == total_tasks:
                logger.info("LLM progress: %d/%d task(s) completed", completed, total_tasks)

    return results


EXTRACT_SYSTEM_PROMPT = """You are an expert at parsing job postings. Extract structured information from job descriptions.
Return a JSON object with the following fields:
- position_type: Type of position (e.g., "Assistant Professor", "Postdoc", "Research Associate")
- field: Primary field of economics (e.g., "Public Economics", "Development Economics", "Microeconomics")
- level: Position level(s) - focus on the JOB TITLE when mapping to one or more of these canonical labels: "Pre-doc", "Postdoc", "Assistant", "Associate", "Full", "Lecturer / Instructor", "Research", "Other". If multiple apply, return all as a forward-slash-separated string preserving the order found in the title (e.g., "Assistant / Associate").
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


def _build_extract_prompt(job_description: str) -> str:
    return (
        "Extract structured information from this job posting:\n\n"
        f"{job_description}\n\n"
        "Return only valid JSON with the fields specified.\n"
        "- For extracted_deadline, parse any date mentioned in the text.\n"
        "- For application_portal_url, look for URLs to application systems, HR portals, or university job sites.\n"
        "- For country, extract the country name from the location information.\n"
        "- For level, prioritize the job title and map it into the canonical labels: Pre-doc, Postdoc, Assistant, Associate, Full, Lecturer / Instructor, Research, Other. Return the applicable labels using a single forward-slash-separated string (e.g., \"Assistant / Associate\").\n"
        "- For application_materials, list all required materials mentioned (CV, cover letter, statements, transcripts, etc.).\n"
        "- For references_separate_email, check if references should be sent to a different email address than the main application."
    )


def extract_job_details(job_description: str, raw_data: Optional[Dict] = None) -> Dict[str, Any]:
    """Extract structured job details using LLM."""
    try:
        prompt = _build_extract_prompt(job_description)
        response = _call_llm(prompt, EXTRACT_SYSTEM_PROMPT)
        if not response:
            return {}

        data = _clean_llm_json(response)
        if data:
            title_hint = ""
            if raw_data:
                title_hint = raw_data.get("title", "") or ""
                if not job_description and raw_data.get("description"):
                    job_description = raw_data.get("description", "")
            normalized_levels = normalize_level_labels(
                data.get("level"),
                job_title=title_hint,
                job_description=job_description,
            )
            data["level"] = " / ".join(normalized_levels) if normalized_levels else ""
            logger.info("Successfully extracted job details")
            return data
        return {}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to extract job details: %s", exc)
        return {}


def extract_job_details_batch(
    items: List[Tuple[str, str]],
    max_workers: Optional[int] = None
) -> Dict[str, Dict[str, Any]]:
    """Batch version of extract_job_details.

    Args:
        items: List of tuples (identifier, job_description).
    """

    if not items:
        return {}

    def make_task(description: str) -> Callable[[], Dict[str, Any]]:
        prompt = _build_extract_prompt(description)

        def task() -> Dict[str, Any]:
            response = _call_llm(prompt, EXTRACT_SYSTEM_PROMPT)
            if not response:
                return {}
            data = _clean_llm_json(response)
            return data or {}

        return task

    tasks = [(identifier, make_task(description)) for identifier, description in items]
    responses = execute_llm_tasks(tasks, max_workers=max_workers)

    return {identifier: result or {} for identifier, result in responses.items()}


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


def parse_deadlines_batch(
    items: List[Tuple[str, str]],
    max_workers: Optional[int] = None
) -> Dict[str, Optional[str]]:
    """Batch deadline parser using LLM where beneficial."""

    def make_task(text: str) -> Callable[[], Optional[str]]:
        system_prompt = "Extract the deadline date from text. Return only the date in YYYY-MM-DD format, or null if no date found."
        prompt = f"Extract the deadline date from: {text}\nReturn only YYYY-MM-DD or null."

        def task() -> Optional[str]:
            response = _call_llm(prompt, system_prompt)
            if not response:
                return None
            response_clean = response.strip().strip('"').strip("'")
            try:
                datetime.strptime(response_clean, "%Y-%m-%d")
                return response_clean
            except ValueError:
                return None

        return task

    tasks = [(identifier, make_task(text)) for identifier, text in items]
    results = execute_llm_tasks(tasks, max_workers=max_workers)
    return results


CLASSIFY_SYSTEM_PROMPT = """Classify the job position. Return JSON with:
- level: Position level(s) mapped to the canonical labels "Pre-doc", "Postdoc", "Assistant", "Associate", "Full", "Lecturer / Instructor", "Research", or "Other". Use the JOB TITLE as the primary signal. If multiple ranks are valid, return all as a forward-slash-separated string in ascending seniority (e.g., "Assistant / Associate").
- type: "Tenure-track", "Tenured", "Non-tenure", "Postdoc", "Other"
- field_focus: Primary field (e.g., "Public Economics", "Development Economics")"""


def _build_classify_prompt(title: str, description: str) -> str:
    return (
        "Classify this position:\n\n"
        f"Title: {title}\n"
        f"Description: {description[:500]}\n\n"
        "Return only valid JSON.\n"
        "For level field: Prioritize the job title and map into the canonical labels: Pre-doc, Postdoc, Assistant, Associate, Full, Lecturer / Instructor, Research, Other. Include every applicable label using forward slashes (e.g., \"Assistant / Associate\")."
    )


def classify_position(title: str, description: str) -> Dict[str, str]:
    """Classify position level and type."""
    try:
        prompt = _build_classify_prompt(title, description)
        response = _call_llm(prompt, CLASSIFY_SYSTEM_PROMPT)
        if not response:
            return {"level": "Other", "type": "Other", "field_focus": ""}

        data = _clean_llm_json(response)
        if data:
            normalized_levels = normalize_level_labels(
                data.get("level"),
                job_title=title,
                job_description=description,
            )
            data["level"] = " / ".join(normalized_levels) if normalized_levels else ""
            return data
        return {"level": "Other", "type": "Other", "field_focus": ""}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to classify position: %s", exc)
        return {"level": "Other", "type": "Other", "field_focus": ""}


def classify_position_batch(
    items: List[Tuple[str, str, str]],
    max_workers: Optional[int] = None
) -> Dict[str, Dict[str, str]]:
    """Batch classifier for job positions."""

    def make_task(title: str, description: str) -> Callable[[], Dict[str, str]]:
        prompt = _build_classify_prompt(title, description)

        def task() -> Dict[str, str]:
            response = _call_llm(prompt, CLASSIFY_SYSTEM_PROMPT)
            if not response:
                return {"level": "Other", "type": "Other", "field_focus": ""}
            data = _clean_llm_json(response)
            if data:
                normalized_levels = normalize_level_labels(
                    data.get("level"),
                    job_title=title,
                    job_description=description,
                )
                data["level"] = " / ".join(normalized_levels) if normalized_levels else ""
                return data
            return {"level": "Other", "type": "Other", "field_focus": ""}

        return task

    tasks = [
        (
            identifier,
            make_task(title, description)
        )
        for identifier, title, description in items
    ]

    responses = execute_llm_tasks(tasks, max_workers=max_workers)
    return {
        identifier: result or {"level": "Other", "type": "Other", "field_focus": ""}
        for identifier, result in responses.items()
    }

