"""LLM-based evaluator for calculating portfolio/job fit scores."""

import json
import logging
from typing import Any, Dict, Optional, Tuple, List, Callable

from config.prompt_loader import DEFAULT_PROMPTS, get_prompts
from processor.llm_parser import _call_llm, execute_llm_tasks

# Configure logging with datetime prefix
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


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


def _load_prompts() -> Tuple[str, str]:
    prompts = get_prompts()
    system_prompt = prompts.get("system_prompt") or DEFAULT_PROMPTS["system_prompt"]
    user_prompt = prompts.get("user_prompt") or DEFAULT_PROMPTS["user_prompt"]
    return system_prompt, user_prompt


def build_joint_prompt(job: Dict[str, Any], portfolio_summary: str, prompt_template: Optional[str] = None) -> str:
    job_title = job.get('title') or 'Unknown Title'
    institution = job.get('institution') or 'Unknown Institution'
    position_type = job.get('position_type') or job.get('level') or 'N/A'
    location = job.get('location') or job.get('country') or 'N/A'
    description = _truncate_text(job.get('description', 'No description provided'), 2500)
    requirements = _truncate_text(job.get('requirements', 'No explicit requirements listed.'), 1500)

    if prompt_template is None:
        _, prompt_template = _load_prompts()

    prompt = prompt_template.format(
        portfolio_summary=portfolio_summary or 'No portfolio information provided.',
        job_title=job_title,
        institution=institution,
        position_type=position_type,
        location=location,
        description=description,
        requirements=requirements,
    )
    return prompt


def evaluate_fit_with_llm(
    job: Dict[str, Any],
    portfolio: Dict[str, str],
    prompts: Optional[Tuple[str, str]] = None,
) -> Optional[Tuple[float, Dict[str, Any]]]:
    """Call the configured LLM to score the job fit.

    Returns a tuple of (score, metadata) where metadata includes reasoning/alignment.
    Returns None if the LLM call fails or the response cannot be parsed.
    """

    portfolio_text = portfolio.get('combined_text') or ""
    if not portfolio_text:
        logger.warning("Portfolio text missing; skipping LLM fit evaluation.")
        return None

    portfolio_summary = _truncate_text(portfolio_text, 2500)
    if prompts is None:
        system_prompt, user_prompt = _load_prompts()
    else:
        system_prompt, user_prompt = prompts
    prompt = build_joint_prompt(job, portfolio_summary, prompt_template=user_prompt)

    try:
        response = _call_llm(prompt, system_prompt)
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
        score = data.get('fit_score', data.get('score'))

        if score is None:
            logger.error("LLM fit response missing 'fit_score'/'score' field.")
            return None

        try:
            score_value = float(score)
        except (TypeError, ValueError):
            logger.error("LLM fit response returned non-numeric score: %s", score)
            return None

        metadata = {
            'reasoning': data.get('fit_reasoning', data.get('reasoning', '')),
            'alignment': data.get('fit_alignment', data.get('alignment', {})),
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

    prompts_pair = _load_prompts()

    def make_task(job_inner: Dict[str, Any]) -> Callable[[], Optional[Tuple[float, Dict[str, Any]]]]:
        def task() -> Optional[Tuple[float, Dict[str, Any]]]:
            return evaluate_fit_with_llm(job_inner, portfolio, prompts=prompts_pair)

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
    system_prompt, user_prompt = _load_prompts()
    prompt = build_joint_prompt(job, portfolio_summary, prompt_template=user_prompt)

    try:
        response = _call_llm(prompt, system_prompt)
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


def evaluate_fit_and_difficulty_batch(
    jobs: List[Dict[str, Any]],
    portfolio: Dict[str, str],
    max_workers: Optional[int] = None
) -> Dict[str, Dict[str, Any]]:
    """Evaluate multiple jobs concurrently using the joint fit/difficulty LLM prompt.

    Returns a mapping of job_id to result dictionary containing fit/difficulty scores and reasoning.
    Jobs without IDs are skipped.
    """

    if not jobs:
        return {}

    portfolio_text = portfolio.get('combined_text') or ""
    if not portfolio_text:
        logger.warning("Portfolio text missing; skipping batch joint fit/difficulty evaluation.")
        return {}

    from config.settings import LLM_MAX_CONCURRENCY
    max_workers = max_workers or LLM_MAX_CONCURRENCY
    max_workers = max(1, max_workers)

    jobs_with_id = [(job.get('job_id'), job) for job in jobs if job.get('job_id')]

    if not jobs_with_id:
        return {}

    prompts_pair = _load_prompts()
    portfolio_summary = _truncate_text(portfolio_text, 2500)

    def make_task(job_inner: Dict[str, Any]) -> Callable[[], Optional[Dict[str, Any]]]:
        def task() -> Optional[Dict[str, Any]]:
            return evaluate_fit_and_difficulty(job_inner, portfolio)

        return task

    tasks = [(job_id, make_task(job)) for job_id, job in jobs_with_id]
    task_results = execute_llm_tasks(tasks, max_workers=max_workers)

    results: Dict[str, Dict[str, Any]] = {}
    for job_id, result in task_results.items():
        if result:
            results[job_id] = result

    return results


