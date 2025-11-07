"""LLM-based evaluator for calculating portfolio/job fit scores."""

import json
import logging
from typing import Any, Dict, Optional, Tuple, List, Callable

from processor.llm_parser import _call_llm, execute_llm_tasks

# Configure logging with datetime prefix
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are an experienced economics job-market advisor. "
    "Given a candidate profile and a job posting, assess how well the candidate fits the job. "
    "Return JSON with the following structure only:\n"
    "{\n"
    "  \"score\": <integer 0-100>,\n"
    "  \"reasoning\": <string explanation (<= 200 words)>,\n"
    "  \"alignment\": {\n"
    "    \"research\": <string>,\n"
    "    \"teaching\": <string>,\n"
    "    \"other\": <string>\n"
    "  }\n"
    "}\n"
    "Focus on relevance between research areas, qualifications, teaching expectations, and institutional fit."
)


JOINT_SYSTEM_PROMPT = (
    "You are an experienced economics job-market advisor. Analyze the candidate profile and the job "
    "posting to assess BOTH fit and application difficulty. Return JSON with this schema only:\n"
    "{\n"
    "  \"fit_score\": <float 0-100>,\n"
    "  \"fit_reasoning\": <string explanation (<= 200 words)>,\n"
    "  \"fit_alignment\": {\n"
    "    \"research\": <string>,\n"
    "    \"teaching\": <string>,\n"
    "    \"other\": <string>\n"
    "  },\n"
    "  \"difficulty_score\": <float 0-100>,\n"
    "  \"difficulty_reasoning\": <string explanation (<= 120 words)>\n"
    "}\n"
    "Fit focuses on research/qualification alignment; difficulty reflects how challenging it is for the "
    "candidate to secure the role given institution selectivity and requirements."
)


def _truncate_text(text: str, max_length: int = 2000) -> str:
    """Truncate text to a maximum length while preserving word boundaries."""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_length:
        return text
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + " …"


def build_fit_prompt(job: Dict[str, Any], portfolio_summary: str) -> str:
    """Create a structured prompt for the LLM fit evaluation."""
    job_title = job.get('title') or 'Unknown Title'
    institution = job.get('institution') or 'Unknown Institution'
    position_type = job.get('position_type') or job.get('level') or 'N/A'
    location = job.get('location') or job.get('country') or 'N/A'
    description = _truncate_text(job.get('description', 'No description provided'), 2500)
    requirements = _truncate_text(job.get('requirements', 'No explicit requirements listed.'), 1500)

    prompt = (
        "Evaluate the candidate's fit for this economics job.\n\n"
        "== Candidate Summary ==\n"
        f"{portfolio_summary or 'No portfolio information provided.'}\n\n"
        "== Job Details ==\n"
        f"Title: {job_title}\n"
        f"Institution: {institution}\n"
        f"Position Type/Level: {position_type}\n"
        f"Location: {location}\n"
        "Description:\n"
        f"{description}\n\n"
        "Key Requirements:\n"
        f"{requirements}\n\n"
        "Return only the JSON structure described in the system prompt."
    )
    return prompt


def build_joint_prompt(job: Dict[str, Any], portfolio_summary: str) -> str:
    job_title = job.get('title') or 'Unknown Title'
    institution = job.get('institution') or 'Unknown Institution'
    position_type = job.get('position_type') or job.get('level') or 'N/A'
    location = job.get('location') or job.get('country') or 'N/A'
    description = _truncate_text(job.get('description', 'No description provided'), 2500)
    requirements = _truncate_text(job.get('requirements', 'No explicit requirements listed.'), 1500)

    prompt = (
        "Evaluate the candidate's overall fit and application difficulty for this economics job.\n\n"
        "== Candidate Summary ==\n"
        f"{portfolio_summary or 'No portfolio information provided.'}\n\n"
        "== Job Details ==\n"
        f"Title: {job_title}\n"
        f"Institution: {institution}\n"
        f"Position Type/Level: {position_type}\n"
        f"Location: {location}\n"
        "Description:\n"
        f"{description}\n\n"
        "Key Requirements:\n"
        f"{requirements}\n\n"
        "Return only the JSON structure specified in the system prompt."
    )
    return prompt


def evaluate_fit_with_llm(job: Dict[str, Any], portfolio: Dict[str, str]) -> Optional[Tuple[float, Dict[str, Any]]]:
    """Call the configured LLM to score the job fit.

    Returns a tuple of (score, metadata) where metadata includes reasoning/alignment.
    Returns None if the LLM call fails or the response cannot be parsed.
    """

    portfolio_text = portfolio.get('combined_text') or ""
    if not portfolio_text:
        logger.warning("Portfolio text missing; skipping LLM fit evaluation.")
        return None

    portfolio_summary = _truncate_text(portfolio_text, 2500)
    prompt = build_fit_prompt(job, portfolio_summary)

    try:
        response = _call_llm(prompt, SYSTEM_PROMPT)
        if not response:
            logger.error("LLM returned empty response for fit evaluation.")
            return None

        response = response.strip()
        if response.startswith("```"):
            parts = response.split("```")
            if len(parts) > 1:
                response = parts[1]
                if response.startswith("json"):
                    response = response[4:]
            response = response.strip()

        data = json.loads(response)
        score = data.get('score')

        if score is None:
            logger.error("LLM fit response missing 'score' field.")
            return None

        try:
            score_value = float(score)
        except (TypeError, ValueError):
            logger.error("LLM fit response returned non-numeric score: %s", score)
            return None

        metadata = {
            'reasoning': data.get('reasoning', ''),
            'alignment': data.get('alignment', {}),
        }

        logger.info("LLM fit score computed successfully: %.2f", score_value)
        return score_value, metadata

    except json.JSONDecodeError as json_error:
        logger.error("Failed to parse LLM fit response as JSON: %s", json_error)
        logger.debug("Raw LLM response: %s", response)
        return None
    except Exception as exc:
        logger.error("Error during LLM fit evaluation: %s", exc)
        return None


def evaluate_fit_with_llm_batch(
    jobs: List[Dict[str, Any]],
    portfolio: Dict[str, str],
    max_workers: int = 3
) -> Dict[str, Tuple[float, Dict[str, Any]]]:
    """Evaluate multiple jobs concurrently using the LLM.

    Returns a mapping of job_id to (score, metadata). Jobs without IDs are skipped.
    """

    if not jobs:
        return {}

    portfolio_text = portfolio.get('combined_text') or ""
    if not portfolio_text:
        logger.warning("Portfolio text missing; skipping batch LLM evaluation.")
        return {}

    max_workers = max(1, max_workers)
    results: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    jobs_with_id = [(job.get('job_id'), job) for job in jobs if job.get('job_id')]

    if not jobs_with_id:
        return {}

    def make_task(job_inner: Dict[str, Any]) -> Callable[[], Optional[Tuple[float, Dict[str, Any]]]]:
        def task() -> Optional[Tuple[float, Dict[str, Any]]]:
            return evaluate_fit_with_llm(job_inner, portfolio)

        return task

    tasks = [(job_id, make_task(job)) for job_id, job in jobs_with_id]
    task_results = execute_llm_tasks(tasks, max_workers=max_workers)

    for job_id, result in task_results.items():
        if result:
            results[job_id] = result

    return results


def evaluate_fit_and_difficulty(job: Dict[str, Any], portfolio: Dict[str, str]) -> Optional[Dict[str, Any]]:
    """Run a single LLM call that returns both fit and difficulty information.

    Returns a dictionary containing fit/difficulty scores and reasoning, or None on failure.
    """

    portfolio_text = portfolio.get('combined_text') or ""
    if not portfolio_text:
        logger.warning("Portfolio text missing; skipping joint fit/difficulty evaluation.")
        return None

    portfolio_summary = _truncate_text(portfolio_text, 2500)
    prompt = build_joint_prompt(job, portfolio_summary)

    try:
        response = _call_llm(prompt, JOINT_SYSTEM_PROMPT)
        if not response:
            logger.error("LLM returned empty response for joint fit/difficulty evaluation.")
            return None

        response = response.strip()
        if response.startswith("```"):
            parts = response.split("```")
            if len(parts) > 1:
                response = parts[1]
                if response.startswith("json"):
                    response = response[4:]
            response = response.strip()

        data = json.loads(response)

        fit_score = data.get('fit_score')
        difficulty_score = data.get('difficulty_score')

        if fit_score is None or difficulty_score is None:
            logger.error("Joint LLM response missing required scores: %s", response)
            return None

        try:
            fit_score_value = float(fit_score)
            difficulty_score_value = float(difficulty_score)
        except (TypeError, ValueError):
            logger.error("Joint LLM response returned non-numeric scores: %s", response)
            return None

        result = {
            'fit_score': max(0.0, min(fit_score_value, 100.0)),
            'fit_reasoning': data.get('fit_reasoning', ''),
            'fit_alignment': data.get('fit_alignment', {}),
            'difficulty_score': max(0.0, min(difficulty_score_value, 100.0)),
            'difficulty_reasoning': data.get('difficulty_reasoning', ''),
        }

        logger.info(
            "Joint LLM fit/difficulty computed successfully: fit=%.2f, difficulty=%.2f",
            result['fit_score'],
            result['difficulty_score'],
        )

        return result

    except json.JSONDecodeError as json_error:
        logger.error("Failed to parse joint LLM response as JSON: %s", json_error)
        logger.debug("Raw LLM response: %s", response)
        return None
    except Exception as exc:
        logger.error("Error during joint fit/difficulty evaluation: %s", exc)
        return None


