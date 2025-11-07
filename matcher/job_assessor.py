"""LLM-based job assessment utilities (position track + difficulty)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from processor.llm_parser import _call_llm, _clean_llm_json, execute_llm_tasks

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


TRACK_OPTIONS = [
    "junior tenure-track",
    "senior tenure-track",
    "teaching",
    "industry",
    "non-tenure track",
    "other academia",
]

POSITION_TRACK_SYSTEM_PROMPT = (
    "You are an expert academic career advisor. Review the job posting and assign it to"
    " one of the predefined categories. Use domain knowledge about economics job market"
    " roles. Respond ONLY with JSON in the following shape:\n"
    "{\n"
    "  \"track_label\": <one of: junior tenure-track, senior tenure-track, teaching, industry, non-tenure track, other academia>,\n"
    "  \"reasoning\": <short explanation>\n"
    "}\n"
    "Junior tenure-track generally means assistant-level or early-career tenure-track positions."
    " Senior tenure-track implies associate/full rank or leadership roles. Teaching refers to"
    " lecturer/instructor/teaching professor roles. Industry covers private-sector, consulting,"
    " or non-academic employers. Non-tenure track covers research associate, visiting, postdoc,"
    " adjunct, or contract academic positions. Other academia is a catch-all for remaining"
    " academic roles (e.g., research centers) not fitting the earlier buckets."
)


DIFFICULTY_SYSTEM_PROMPT = (
    "You are advising a candidate about the difficulty of securing a specific job."
    " Consider the candidate portfolio summary, institution reputation, experience level,"
    " and description requirements. Provide a feasibility score between 0 and 100 (0 = impossible, 100 = guaranteed)."
    " The candidate is early-career, with strengths aligned to the provided portfolio summary."
    " Return ONLY JSON: {\"difficulty_score\": <0-100 float>, \"reasoning\": <string>}\n"
    "General guidance:\n"
    "- Senior tenure-track roles (associate/full) should be near 0.\n"
    "- Top 30 US universities for assistant professor are <5.\n"
    "- Top 5 China universities assistant professor around 10.\n"
    "- Adjust sensibly for less selective institutions or non-tenure roles."
)


def _truncate(text: str, max_len: int) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    last_space = truncated.rfind(' ')
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + " …"


def _build_job_snapshot(job: Dict[str, Any]) -> str:
    parts = [
        f"Title: {job.get('title') or 'Unknown'}",
        f"Institution: {job.get('institution') or 'Unknown'}",
        f"Position Type: {job.get('position_type') or job.get('level') or 'N/A'}",
        f"Field: {job.get('field') or 'N/A'}",
        f"Location: {job.get('location') or job.get('country') or 'N/A'}",
        f"Status: {job.get('application_status') or 'N/A'}",
    ]
    requirements = _truncate(str(job.get('requirements') or ''), 1500)
    description = _truncate(str(job.get('description') or ''), 2000)
    parts.append(f"Requirements:\n{requirements or 'Not specified.'}")
    parts.append(f"Description:\n{description or 'Not specified.'}")
    return "\n".join(parts)


def _evaluate_position_track(job: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    prompt = _build_job_snapshot(job)
    response = _call_llm(prompt, POSITION_TRACK_SYSTEM_PROMPT)
    if not response:
        return None
    data = _clean_llm_json(response)
    if not data:
        return None
    track = (data.get('track_label') or '').strip().lower()
    if track not in TRACK_OPTIONS:
        return None
    reasoning = (data.get('reasoning') or '').strip()
    return track, reasoning


def evaluate_position_track_batch(
    jobs: List[Dict[str, Any]],
    max_workers: Optional[int] = None
) -> Dict[str, Tuple[str, str]]:
    jobs_with_id = [(job.get('job_id'), job) for job in jobs if job.get('job_id')]
    if not jobs_with_id:
        return {}

    tasks = [
        (job_id, lambda job=job: _evaluate_position_track(job))
        for job_id, job in jobs_with_id
    ]
    results = execute_llm_tasks(tasks, max_workers=max_workers)
    return {job_id: result for job_id, result in results.items() if result}


def _evaluate_difficulty(job: Dict[str, Any], portfolio_summary: str) -> Optional[Tuple[float, str]]:
    snapshot = _build_job_snapshot(job)
    portfolio_snippet = _truncate(portfolio_summary, 2000)
    prompt = (
        f"Candidate Portfolio Summary:\n{portfolio_snippet or 'Not provided.'}\n\n"
        f"Job Snapshot:\n{snapshot}\n\n"
        "Estimate the feasibility for THIS candidate."
    )
    response = _call_llm(prompt, DIFFICULTY_SYSTEM_PROMPT)
    if not response:
        return None
    data = _clean_llm_json(response)
    if not data:
        return None
    try:
        score = float(data.get('difficulty_score'))
    except (TypeError, ValueError):
        return None
    score = max(0.0, min(score, 100.0))
    reasoning = (data.get('reasoning') or '').strip()
    return score, reasoning


def evaluate_difficulty_batch(
    jobs: List[Dict[str, Any]],
    portfolio: Dict[str, str],
    max_workers: Optional[int] = None
) -> Dict[str, Tuple[float, str]]:
    portfolio_summary = portfolio.get('combined_text') or ''
    if not jobs or not portfolio_summary:
        return {}

    jobs_with_id = [(job.get('job_id'), job) for job in jobs if job.get('job_id')]
    if not jobs_with_id:
        return {}

    tasks = [
        (job_id, lambda job=job: _evaluate_difficulty(job, portfolio_summary))
        for job_id, job in jobs_with_id
    ]
    results = execute_llm_tasks(tasks, max_workers=max_workers)
    return {job_id: result for job_id, result in results.items() if result}

