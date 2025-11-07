"""Fit calculator for matching jobs to portfolio."""

import logging
import re
from typing import Dict, List, Any, Tuple

from .llm_fit_evaluator import (
    evaluate_fit_with_llm,
    evaluate_fit_with_llm_batch,
    evaluate_fit_and_difficulty,
)

from config.settings import RESEARCH_FOCAL_AREAS

# Configure logging with datetime prefix
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def calculate_research_alignment(job_description: str, job_field: str = "") -> float:
    """Calculate research area alignment score (0-100, 40% weight)."""
    score = 0.0
    max_score = 100.0
    
    # Combine description and field
    text = (job_description + " " + job_field).lower()
    
    # Check for research area keywords
    area_matches = 0
    for area in RESEARCH_FOCAL_AREAS:
        area_lower = area.lower()
        # Count occurrences
        count = text.count(area_lower)
        if count > 0:
            area_matches += 1
            # Bonus for multiple mentions
            score += min(30, count * 10)
    
    # Base score for matching areas
    if area_matches > 0:
        score += (area_matches / len(RESEARCH_FOCAL_AREAS)) * 40
    
    # Check for related keywords
    related_keywords = {
        'public economics': ['public policy', 'government', 'tax', 'fiscal', 'welfare'],
        'development economics': ['development', 'poverty', 'inequality', 'growth', 'emerging markets'],
        'microeconomics': ['micro', 'individual', 'consumer', 'firm', 'market structure'],
    }
    
    for area, keywords in related_keywords.items():
        if area.lower() in text:
            for keyword in keywords:
                if keyword in text:
                    score += 5
                    break
    
    return min(score, max_score)


def calculate_qualification_match(job_requirements: str, portfolio_text: str) -> float:
    """Calculate qualification match score (0-100, 30% weight)."""
    if not job_requirements or not portfolio_text:
        return 50.0  # Neutral score if missing data
    
    score = 50.0  # Start with neutral
    req_lower = job_requirements.lower()
    portfolio_lower = portfolio_text.lower()
    
    # Check for Ph.D. requirement
    if 'ph.d' in req_lower or 'phd' in req_lower or 'doctorate' in req_lower:
        if 'ph.d' in portfolio_lower or 'phd' in portfolio_lower:
            score += 20
    
    # Check for postdoc experience
    if 'postdoc' in req_lower or 'post-doc' in req_lower:
        if 'postdoc' in portfolio_lower or 'hku' in portfolio_lower:
            score += 15
    
    # Check for teaching experience
    if 'teaching' in req_lower:
        if 'teaching' in portfolio_lower:
            score += 10
    
    # Check for publication requirements
    if 'publication' in req_lower or 'research' in req_lower:
        if 'publication' in portfolio_lower or 'paper' in portfolio_lower:
            score += 10
    
    # Check for specific skills/fields
    field_keywords = ['econometrics', 'statistics', 'stata', 'r', 'python', 'data']
    matches = sum(1 for keyword in field_keywords if keyword in req_lower and keyword in portfolio_lower)
    score += min(15, matches * 5)
    
    return min(score, 100.0)


def calculate_position_level_match(job_level: str, job_title: str) -> float:
    """Calculate position level match score (0-100, 20% weight)."""
    # Assume user is looking for assistant professor positions
    # Adjust based on career stage
    target_levels = ['assistant', 'postdoc', 'junior']
    
    text = (job_level + " " + job_title).lower()
    
    score = 50.0  # Neutral
    
    # High match for assistant professor
    if 'assistant' in text and 'professor' in text:
        score = 90.0
    # Good match for postdoc
    elif 'postdoc' in text or 'post-doc' in text:
        score = 85.0
    # Lower match for associate/full (too senior)
    elif 'associate' in text or 'full professor' in text:
        score = 30.0
    # Check for tenure-track
    elif 'tenure-track' in text or 'tenure track' in text:
        score = 80.0
    # Non-tenure positions
    elif 'non-tenure' in text or 'lecturer' in text:
        score = 60.0
    
    return score


def calculate_institution_match(job_institution: str, job_location: str = "") -> float:
    """Calculate institution type match score (0-100, 10% weight)."""
    # This is a simplified version - could be enhanced with institution database
    score = 50.0  # Neutral
    
    text = (job_institution + " " + job_location).lower()
    
    # Prefer R1 universities (research-focused)
    r1_keywords = ['university', 'college', 'institute']
    if any(keyword in text for keyword in r1_keywords):
        score = 70.0
    
    # Lower preference for teaching-focused
    if 'community college' in text or 'teaching college' in text:
        score = 40.0
    
    # Geographic preferences could be added here
    # For now, neutral on geography
    
    return score


def _calculate_fit_score_rule_based(
    job: Dict[str, Any],
    portfolio: Dict[str, str]
) -> float:
    """Calculate overall fit score (0-100) using the heuristic algorithm."""
    # Extract job information
    job_description = str(job.get('description', ''))
    job_field = str(job.get('field', ''))
    job_requirements = str(job.get('requirements', ''))
    job_level = str(job.get('level', ''))
    job_title = str(job.get('title', ''))
    job_institution = str(job.get('institution', ''))
    job_location = str(job.get('location', ''))
    
    # Get portfolio text
    portfolio_text = portfolio.get('combined_text', '')
    
    # Calculate component scores
    research_score = calculate_research_alignment(job_description, job_field)
    qualification_score = calculate_qualification_match(job_requirements, portfolio_text)
    position_score = calculate_position_level_match(job_level, job_title)
    institution_score = calculate_institution_match(job_institution, job_location)
    
    # Weighted combination
    weights = {
        'research': 0.40,
        'qualification': 0.30,
        'position': 0.20,
        'institution': 0.10,
    }
    
    fit_score = (
        research_score * weights['research'] +
        qualification_score * weights['qualification'] +
        position_score * weights['position'] +
        institution_score * weights['institution']
    )
    
    logger.debug(
        f"Fit score for {job.get('title', 'Unknown')}: "
        f"research={research_score:.1f}, qual={qualification_score:.1f}, "
        f"position={position_score:.1f}, inst={institution_score:.1f}, "
        f"total={fit_score:.1f}"
    )
    
    return round(fit_score, 2)


def calculate_fit_score(
    job: Dict[str, Any],
    portfolio: Dict[str, str],
    use_llm: bool = True
) -> float:
    """Calculate overall fit score, preferring the LLM evaluator with heuristic fallback."""

    if use_llm:
        llm_result = evaluate_fit_with_llm(job, portfolio)
        if llm_result:
            score, metadata = llm_result
            clamped_score = max(0.0, min(score, 100.0))
            job['fit_reasoning'] = metadata.get('reasoning', '')
            job['fit_alignment'] = metadata.get('alignment', {})
            return round(clamped_score, 2)

    # Fallback to heuristic scoring if LLM unavailable or fails
    heuristic_score = _calculate_fit_score_rule_based(job, portfolio)
    job.setdefault('fit_reasoning', 'Heuristic fit score used (LLM unavailable).')
    return heuristic_score


def calculate_fit_scores_batch(
    jobs: List[Dict[str, Any]],
    portfolio: Dict[str, str],
    use_llm: bool = True,
    max_workers: int = 3
) -> List[Dict[str, Any]]:
    """Calculate fit scores for multiple jobs, using concurrent LLM calls when available."""

    if not jobs:
        return []

    llm_results: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    if use_llm:
        llm_results = evaluate_fit_with_llm_batch(jobs, portfolio, max_workers=max_workers)

    scored_jobs: List[Dict[str, Any]] = []

    for job in jobs:
        job_id = job.get('job_id')
        llm_result = llm_results.get(job_id) if job_id else None

        if llm_result:
            score, metadata = llm_result
            clamped_score = max(0.0, min(score, 100.0))
            job['fit_score'] = round(clamped_score, 2)
            job['fit_reasoning'] = metadata.get('reasoning', '')
            job['fit_alignment'] = metadata.get('alignment', {})
        else:
            job['fit_score'] = _calculate_fit_score_rule_based(job, portfolio)
            job.setdefault('fit_reasoning', 'Heuristic fit score used (LLM unavailable).')

        scored_jobs.append(job)

    return rank_jobs(scored_jobs)


def score_job_with_joint_prompt(
    job: Dict[str, Any],
    portfolio: Dict[str, str],
    force: bool = False,
) -> Tuple[Dict[str, Any], bool, bool]:
    """Score a single job using the joint fit/difficulty LLM prompt (with fallbacks).

    Returns a tuple of (job, recomputed, llm_success).
    """

    job_id = job.get('job_id')
    needs_recompute = force or job.get('fit_score') is None or job.get('difficulty_score') is None

    if not job_id:
        return job, False, False

    if not needs_recompute:
        return job, False, False

    llm_result = evaluate_fit_and_difficulty(job, portfolio)

    if llm_result:
        job['fit_score'] = round(llm_result['fit_score'], 2)
        job['fit_reasoning'] = llm_result.get('fit_reasoning', '')
        job['fit_alignment'] = llm_result.get('fit_alignment', {})
        job['difficulty_score'] = round(llm_result['difficulty_score'], 2)
        job['difficulty_reasoning'] = llm_result.get('difficulty_reasoning', '')
        return job, True, True

    # Fallbacks when LLM fails
    job['fit_score'] = _calculate_fit_score_rule_based(job, portfolio)
    job.setdefault('fit_reasoning', 'Heuristic fit score used (LLM unavailable).')

    if force or job.get('difficulty_score') is None:
        job['difficulty_score'] = job.get('difficulty_score') or 50.0
    if force or not job.get('difficulty_reasoning'):
        job['difficulty_reasoning'] = job.get(
            'difficulty_reasoning',
            'LLM difficulty estimation unavailable; heuristic default applied.',
        )

    return job, True, False


def calculate_fit_scores_with_difficulty(
    jobs: List[Dict[str, Any]],
    portfolio: Dict[str, str],
    force: bool = False,
) -> List[Dict[str, Any]]:
    """Sequentially calculate fit and difficulty scores using the joint prompt."""

    if not jobs:
        return []

    scored_jobs: List[Dict[str, Any]] = []

    for job in jobs:
        # Work on a mutable copy to avoid side effects when caller reuses dicts
        updated_job = dict(job)
        score_job_with_joint_prompt(updated_job, portfolio, force=force)
        scored_jobs.append(updated_job)

    return rank_jobs(scored_jobs)


def rank_jobs(jobs: List[Dict[str, Any]], reverse: bool = True) -> List[Dict[str, Any]]:
    """Rank jobs by fit score."""
    # Sort by fit_score descending (highest first)
    sorted_jobs = sorted(
        jobs,
        key=lambda x: x.get('fit_score', 0.0),
        reverse=reverse
    )
    return sorted_jobs

