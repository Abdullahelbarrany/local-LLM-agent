from __future__ import annotations

import json
import os
import re

import ollama

from tools.job_scrapers import score_job_relevance

MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

_LLM_CAP = 20  # score up to 20 jobs per search
_LLM_THRESHOLD = 0.0  # always qualify for LLM — keyword score used only for ordering

_JSON_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def _extract_matched(job: dict, cv_keywords: list[str]) -> list[str]:
    haystack = (
        (job.get("title") or "") + " " + (job.get("description") or "")
    ).lower()
    return [kw for kw in cv_keywords if kw.lower() in haystack]


async def _llm_rate(
    client: ollama.AsyncClient,
    job: dict,
    cv_keywords: list[str],
) -> tuple[int, str]:
    desc_snippet = (job.get("description") or "").strip()[:400]
    desc_part = f"Description: {desc_snippet}" if desc_snippet else "(No description available — infer from title and company only.)"
    keywords_str = ", ".join(cv_keywords[:30])
    prompt = (
        f"Rate this job's fit for a candidate with these skills: {keywords_str}.\n"
        f"Job title: {job.get('title','(no title)')} at {job.get('company','(no company)')}.\n"
        f"{desc_part}\n"
        'Reply with JSON only, no markdown: {"score": <integer 1-10>, "reason": "<one sentence>"}'
    )
    try:
        resp = await client.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            think=False,
            options={"num_predict": 80},
        )
        raw = resp.message.content or ""
        m = _JSON_RE.search(raw)
        if m:
            data = json.loads(m.group())
            score = max(1, min(10, int(data.get("score", 5))))
            reason = str(data.get("reason", "")).strip() or "No reason provided."
            return score * 10, reason
    except Exception:
        pass
    return 50, "Score estimated deterministically."


async def rank_jobs(jobs: list[dict], cv_keywords: list[str]) -> list[dict]:
    """Return jobs augmented with fit_score (0-100), fit_reason, matched_keywords."""
    client = ollama.AsyncClient(host=OLLAMA_HOST)

    # Step 1: keyword scores for all jobs
    scored = []
    for job in jobs:
        kw_score = score_job_relevance(job, cv_keywords)
        matched = _extract_matched(job, cv_keywords)
        scored.append((job, kw_score, matched))

    # Step 2: all jobs qualify; sort by keyword score descending, cap at _LLM_CAP
    llm_candidates = sorted(
        enumerate(scored), key=lambda x: x[1][1], reverse=True
    )
    llm_set = {i for i, _ in llm_candidates[:_LLM_CAP]}

    result = []
    for i, (job, kw_score, matched) in enumerate(scored):
        job = dict(job)
        if i in llm_set:
            fit_score, fit_reason = await _llm_rate(client, job, cv_keywords)
        else:
            fit_score = int(kw_score * 100)
            fit_reason = "Score based on keyword overlap." if kw_score > 0 else "No keyword match found."

        job["fit_score"] = fit_score
        job["fit_reason"] = fit_reason
        job["matched_keywords"] = matched
        result.append(job)

    return result
