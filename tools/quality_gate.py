from __future__ import annotations

import re
from typing import Optional

try:
    from dateutil import parser as _dateparser
    from datetime import datetime, timezone

    def _days_since(date_str: str) -> Optional[float]:
        try:
            dt = _dateparser.parse(date_str, ignoretz=True)
            now = datetime.now()
            return (now - dt).total_seconds() / 86400
        except Exception:
            return None
except ImportError:
    def _days_since(date_str: str) -> Optional[float]:  # type: ignore[misc]
        return None


_SENIOR_TITLES = re.compile(
    r"\b(senior|lead|principal|staff|director|vp|head of)\b",
    re.IGNORECASE,
)

_BAD_PHRASES = re.compile(
    r"\b(unpaid|commission only|equity only|no salary)\b",
    re.IGNORECASE,
)

_REMOTE_PHRASES = re.compile(
    r"\b(remote|fully remote|work from home|wfh|distributed|anywhere|location independent)\b",
    re.IGNORECASE,
)

_REGION_PHRASES = re.compile(
    r"\b(egypt|mena|emea|africa|middle east|north africa|worldwide|global|international"
    r"|all countries|open to all|any country|globally)\b",
    re.IGNORECASE,
)

_SOURCES = [
    "LinkedIn", "Indeed", "Glassdoor", "Wuzzuf", "Bayt",
    "NaukriGulf", "Remotive", "WeWorkRemotely", "Jobicy",
    "Otta", "Himalayas", "Wellfound",
]


def apply_quality_gate(jobs: list[dict]) -> list[dict]:
    """Augment each job with quality_score, rejection_reason, and flagged_senior."""
    result = []
    for job in jobs:
        job = dict(job)

        url = (job.get("url") or "").strip()
        description = job.get("description") or ""
        title = job.get("title") or ""
        date_posted = job.get("date_posted") or ""

        has_url = bool(url)
        desc_long = len(description) >= 80
        has_bad_phrase = bool(_BAD_PHRASES.search(description))

        days_old = _days_since(date_posted) if date_posted else None
        expired = days_old is not None and days_old > 30

        # weighted quality score
        score = 0.0
        if has_url:
            score += 0.3
        if desc_long:
            score += 0.3
        if not expired:
            score += 0.2
        if not has_bad_phrase:
            score += 0.2

        # first failing hard rule wins as rejection reason
        rejection_reason: Optional[str] = None
        if not has_url:
            rejection_reason = "no_url"
        elif not desc_long:
            rejection_reason = "description_too_short"
        elif has_bad_phrase:
            rejection_reason = "bad_compensation_phrase"
        elif expired:
            rejection_reason = "posting_expired"
        elif score < 0.5:
            rejection_reason = "low_quality_score"

        # remote / region signals — check title + description + location field
        haystack = f"{title} {description} {job.get('location') or ''}"
        job["quality_score"] = round(score, 3)
        job["rejection_reason"] = rejection_reason
        job["flagged_senior"] = bool(_SENIOR_TITLES.search(title))
        job["remote_friendly"] = bool(_REMOTE_PHRASES.search(haystack))
        job["region_open"] = bool(_REGION_PHRASES.search(haystack))

        result.append(job)

    return result
