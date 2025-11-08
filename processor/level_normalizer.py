"""Helpers to normalize LLM-provided level labels into canonical categories."""

from __future__ import annotations

from typing import Iterable, List, Sequence


CANONICAL_LEVEL_ORDER: Sequence[str] = (
    "Pre-doc",
    "Postdoc",
    "Assistant",
    "Associate",
    "Full",
    "Lecturer / Instructor",
    "Research",
    "Other",
)


def _tokenize(values: Iterable[str]) -> List[str]:
    tokens: List[str] = []
    for value in values:
        if not value:
            continue
        parts = [
            part.strip()
            for chunk in value.replace("/", ",").replace(";", ",").split(",")
            for part in chunk.split("|")
        ]
        tokens.extend(part for part in parts if part)
    return tokens


def _matches(text: str, *keywords: str) -> bool:
    lower = text.lower()
    return all(keyword in lower for keyword in keywords)


def _title_matches(title: str, *keywords: str) -> bool:
    return _matches(title, *keywords)


def _detect_pre_doc(tokens: List[str], job_title: str) -> bool:
    title = job_title.lower()
    if any(
        phrase in title
        for phrase in (
            "predoc",
            "pre-doc",
            "pre doc",
            "pre doctoral",
            "predoctoral",
        )
    ):
        return True
    if "research assistant" in title and ("predoctoral" in title or "pre-doctoral" in title):
        return True
    for token in tokens:
        token_lower = token.lower()
        if "pre" in token_lower and "doc" in token_lower:
            return True
        if "predoc" in token_lower:
            return True
    return False


def _detect_postdoc(tokens: List[str], job_title: str) -> bool:
    title = job_title.lower()
    if "postdoc" in title or "post-doc" in title or "postdoctoral" in title:
        return True
    for token in tokens:
        token_lower = token.lower()
        if "postdoc" in token_lower or "post-doc" in token_lower or "postdoctoral" in token_lower:
            return True
    return False


def _detect_assistant(tokens: List[str], job_title: str) -> bool:
    title = job_title.lower()
    if _title_matches(title, "assistant", "prof"):
        return True
    for token in tokens:
        token_lower = token.lower()
        if "assistant professor" in token_lower:
            return True
        if token_lower == "assistant" and ("professor" in title or "prof" in token_lower):
            return True
    return False


def _detect_associate(tokens: List[str], job_title: str) -> bool:
    title = job_title.lower()
    if _title_matches(title, "associate", "prof"):
        return True
    for token in tokens:
        token_lower = token.lower()
        if "associate professor" in token_lower:
            return True
        if token_lower == "associate" and ("professor" in title or "prof" in token_lower):
            return True
    return False


def _detect_full(tokens: List[str], job_title: str) -> bool:
    title = job_title.lower()
    if _title_matches(title, "full", "prof"):
        return True
    if "professor" in title and ("chair" in title or "distinguished" in title):
        return True
    for token in tokens:
        token_lower = token.lower()
        if "full professor" in token_lower:
            return True
        if token_lower == "full" and "professor" in title:
            return True
    return False


def _detect_lecturer(tokens: List[str], job_title: str) -> bool:
    title = job_title.lower()
    lecturer_keywords = ("lecturer", "instructor", "teaching professor", "professor of practice")
    if any(keyword in title for keyword in lecturer_keywords):
        return True
    for token in tokens:
        token_lower = token.lower()
        if any(keyword in token_lower for keyword in lecturer_keywords):
            return True
    return False


def _detect_research(tokens: List[str], job_title: str) -> bool:
    title = job_title.lower()
    research_keywords = ("research fellow", "research scientist", "research associate")
    if any(keyword in title for keyword in research_keywords):
        return True
    for token in tokens:
        token_lower = token.lower()
        if any(keyword in token_lower for keyword in research_keywords):
            return True
    return False


def normalize_level_labels(raw_levels, job_title: str = "", job_description: str = "") -> List[str]:
    """Normalize LLM supplied levels into canonical categories.

    Args:
        raw_levels: Level labels from the LLM (string or iterable of strings).
        job_title: Job title text (primary signal).
        job_description: Full job description (secondary signal).

    Returns:
        Ordered list of canonical level labels. Defaults to ["Other"].
    """
    if raw_levels is None:
        tokens = []
    elif isinstance(raw_levels, str):
        tokens = _tokenize([raw_levels])
    else:
        tokens = _tokenize(raw_levels)

    job_title = job_title or ""
    job_description = job_description or ""
    combined_tokens = tokens + _tokenize([job_description])

    is_pre_doc = _detect_pre_doc(combined_tokens, job_title)
    is_postdoc = _detect_postdoc(combined_tokens, job_title)
    is_assistant = _detect_assistant(combined_tokens, job_title)
    is_associate = _detect_associate(combined_tokens, job_title)
    is_full = _detect_full(combined_tokens, job_title)
    is_lecturer = _detect_lecturer(combined_tokens, job_title)
    is_research = _detect_research(combined_tokens, job_title)

    detected = []

    if is_pre_doc:
        detected.append("Pre-doc")
    if is_postdoc:
        detected.append("Postdoc")
    if is_assistant:
        detected.append("Assistant")
    if is_associate:
        detected.append("Associate")
    if is_full:
        detected.append("Full")
    if is_lecturer:
        detected.append("Lecturer / Instructor")
    if is_research and not (is_pre_doc or is_postdoc):
        detected.append("Research")

    if not detected:
        detected.append("Other")

    seen = set()
    ordered = []
    for level in CANONICAL_LEVEL_ORDER:
        if level in detected and level not in seen:
            ordered.append(level)
            seen.add(level)

    for level in detected:
        if level not in seen:
            ordered.append(level)
            seen.add(level)

    return ordered


