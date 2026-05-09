import asyncio
import os
import re
from datetime import date
from typing import Any

import httpx
import ollama
from dotenv import load_dotenv

load_dotenv()

_MODEL       = os.getenv("OLLAMA_MODEL", "qwen3:8b")
_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# ---------------------------------------------------------------------------
# Ollama-compatible tool definitions for the resume orchestrator
# ---------------------------------------------------------------------------

RESUME_TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "read_cv",
            "description": (
                "Read and extract text from the user's CV PDF file. "
                "Always call this first before any analysis."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_overleaf",
            "description": (
                "Read the user's Overleaf LaTeX (.tex) resume source file. "
                "Use this to see the resume structure, sections, and exact wording."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_jobs_multi",
            "description": (
                "Search for jobs across 12 job sites simultaneously (LinkedIn, Indeed, "
                "Glassdoor, Wuzzuf, Bayt, Naukrigulf, Remotive, WeWorkRemotely, Jobicy, "
                "Otta, Himalayas, Wellfound). Deduplicates results and ranks them by "
                "relevance to the candidate's CV keywords. Returns up to max_results "
                "scored, ranked jobs. Use this instead of search_jobs for comprehensive discovery."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Job search query, e.g. 'senior backend engineer Python'",
                    },
                    "location": {
                        "type": "string",
                        "description": "Target location, e.g. 'Cairo', 'Remote' (optional)",
                    },
                    "cv_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Keywords extracted from the candidate's CV for relevance scoring. "
                            "Pass the keyword list from cv_analyzer output."
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results to return (default 10)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_job_page",
            "description": (
                "Fetch the full text of a job posting URL. "
                "Use after search_jobs_multi to get the complete job description."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full URL of the job posting to fetch",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_cv_version",
            "description": (
                "Save a tailored CV version (LaTeX content) to disk and record it in the "
                "version tracker database. Call this automatically after producing a "
                "tailored cover letter for each job. Returns the saved filename."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "company": {
                        "type": "string",
                        "description": "Company name (used in filename)",
                    },
                    "role": {
                        "type": "string",
                        "description": "Job role/title (used in filename)",
                    },
                    "tex_content": {
                        "type": "string",
                        "description": "LaTeX content to save (cover letter or tailored CV)",
                    },
                    "match_score": {
                        "type": "number",
                        "description": "Match score 0.0–1.0 from gap_analyzer (divide % by 100)",
                    },
                },
                "required": ["company", "role", "tex_content", "match_score"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delegate_to_agent",
            "description": (
                "Spawn a specialized Qwen sub-agent to perform a focused analysis. "
                "agent_type options:\n"
                "  - 'cv_analyzer':            extract skills, experience, education, keywords from CV text\n"
                "  - 'job_analyzer':           extract requirements, tech stack, seniority from a job description\n"
                "  - 'gap_analyzer':           compare CV profile vs job requirements, identify missing skills\n"
                "  - 'tailoring_advisor':      suggest specific resume rewrites and keyword additions for a job\n"
                "  - 'company_research_agent': summarize company stage, culture signals, red/green flags, recommended tone\n"
                "  - 'cover_letter_agent':     write a 3-paragraph cover letter in plain text + LaTeX"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_type": {
                        "type": "string",
                        "enum": [
                            "cv_analyzer",
                            "job_analyzer",
                            "gap_analyzer",
                            "tailoring_advisor",
                            "company_research_agent",
                            "cover_letter_agent",
                        ],
                        "description": "The specialized sub-agent type to spawn",
                    },
                    "task": {
                        "type": "string",
                        "description": "Clear description of what the sub-agent should produce",
                    },
                    "context": {
                        "type": "string",
                        "description": "All relevant text/data the sub-agent needs to complete the task",
                    },
                },
                "required": ["agent_type", "task", "context"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Sub-agent system prompts
# ---------------------------------------------------------------------------

_SUB_AGENT_PROMPTS: dict[str, str] = {
    "cv_analyzer": (
        "You are a CV/resume analysis expert. "
        "Extract and return structured information: technical skills, programming languages, "
        "frameworks and tools, work experience (role, company, duration, key achievements), "
        "education, certifications, and strong resume keywords. "
        "End your response with a section called KEYWORDS that lists 20–30 single-word or "
        "short-phrase keywords separated by commas. Be thorough and use clear sections."
    ),
    "job_analyzer": (
        "You are a job requirements analyst. "
        "From the provided job description extract: required skills (must-have), "
        "nice-to-have skills, years of experience required, key responsibilities, "
        "tech stack, seniority level, and any implicit cultural or domain requirements. "
        "Use clear sections. Be precise."
    ),
    "gap_analyzer": (
        "You are a career gap analyst. "
        "Given a structured CV profile and job requirements, produce:\n"
        "1. MATCH: skills and experience the candidate has that align with the job\n"
        "2. GAPS: requirements missing from the CV or under-represented\n"
        "3. MATCH SCORE: an overall percentage (0–100) with a brief reason\n"
        "Be honest, specific, and reference exact CV/job details."
    ),
    "tailoring_advisor": (
        "You are an expert professional resume writer. "
        "Given a CV and job requirements, provide specific actionable suggestions:\n"
        "- Which existing bullet points to rewrite and how (provide example rewrites)\n"
        "- Keywords and phrases to add that match the job description\n"
        "- Sections to emphasize or reorder\n"
        "- Skills to highlight or downplay\n"
        "Keep all suggestions authentic to the candidate's real experience."
    ),
    "company_research_agent": (
        "You are a company research analyst specializing in recruiting signals. "
        "Given a company name and job description, provide:\n"
        "1. COMPANY STAGE: startup / scale-up / enterprise "
        "— infer from signals in the job description (team size, processes, funding hints)\n"
        "2. CULTURE SIGNALS: list 3–5 culture markers "
        "(e.g. fast-paced, data-driven, remote-friendly, process-heavy)\n"
        "3. GREEN FLAGS: specific positive signals from the job description for this candidate\n"
        "4. RED FLAGS: potential concerns "
        "(vague responsibilities, over-emphasis on hours, excessive requirements)\n"
        "5. RECOMMENDED TONE: formal / casual / mission-driven "
        "— with a one-sentence reason\n"
        "Be specific and reference actual phrases from the job description."
    ),
    "cover_letter_agent": (
        "You are a professional cover letter writer. "
        "Given a CV profile, job description, and gap analysis, write a cover letter "
        "following these STRICT rules:\n"
        "- Exactly 3 paragraphs: (1) opening hook, (2) evidence paragraph, (3) closing CTA\n"
        "- FORBIDDEN phrases: 'I am writing to apply', 'I am excited to', 'I am passionate', "
        "'I would be a great fit', 'to whom it may concern', any generic filler phrase\n"
        "- Lead with VALUE to the employer, not your enthusiasm\n"
        "- Mirror 1–2 key phrases from the job description naturally\n"
        "- Opening hook: start with a relevant achievement or insight — never 'My name is'\n"
        "- Evidence paragraph: 2–3 specific accomplishments with metrics where possible\n"
        "- Closing CTA: confident and specific, not desperate\n\n"
        "Output format:\n"
        "PLAIN TEXT VERSION:\n"
        "[3-paragraph letter]\n\n"
        "LATEX VERSION:\n"
        "\\begin{letter}{Company Name}\n"
        "\\opening{Dear Hiring Manager,}\n"
        "[letter body]\n"
        "\\closing{Best regards,}\n"
        "\\end{letter}"
    ),
}

# ---------------------------------------------------------------------------
# Synchronous tool handlers
# ---------------------------------------------------------------------------

def read_cv() -> str:
    path = os.getenv("CV_PDF_PATH", "cv.pdf")
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text if text.strip() else "PDF opened but no text extracted (may be image-based)."
    except FileNotFoundError:
        return (
            f"CV PDF not found at '{path}'. "
            "Set CV_PDF_PATH in .env to the correct path."
        )
    except ImportError:
        return "pypdf not installed. Run: uv add pypdf"
    except Exception as exc:
        return f"Error reading CV PDF: {exc}"


def read_overleaf() -> str:
    path = os.getenv("OVERLEAF_TEX_PATH", "cv.tex")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return (
            f".tex file not found at '{path}'. "
            "Set OVERLEAF_TEX_PATH in .env to the correct path."
        )
    except Exception as exc:
        return f"Error reading .tex file: {exc}"


def fetch_job_page(url: str) -> str:
    try:
        resp = httpx.get(
            url,
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )},
        )
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:5000]
    except Exception as exc:
        return f"Error fetching '{url}': {exc}"


def delegate_to_agent(agent_type: str, task: str, context: str) -> str:
    system = _SUB_AGENT_PROMPTS.get(
        agent_type, "You are a helpful career and resume assistant."
    )
    client = ollama.Client(host=_OLLAMA_HOST)
    response = client.chat(
        model=_MODEL,
        messages=[
            {"role": "system",  "content": system},
            {"role": "user",    "content": f"Task: {task}\n\nContext:\n{context}"},
        ],
    )
    return response.message.content


# ---------------------------------------------------------------------------
# Async tool handlers (Enhancement 3, 5)
# ---------------------------------------------------------------------------

async def _async_search_jobs_multi(args: dict) -> list[dict]:
    """Search 12 sites, cache results, deduplicate, score, and rank."""
    from tools.job_scrapers import JobScraper, deduplicate_jobs, score_job_relevance
    from tools.job_cache import JobCache

    query       = args.get("query", "")
    location    = args.get("location", "")
    cv_keywords = args.get("cv_keywords", [])
    max_results = int(args.get("max_results", 10))

    cache = JobCache()
    cached = await cache.get_all_for_query(query, max_age_hours=24)

    if cached:
        jobs = cached
    else:
        scraper = JobScraper()
        jobs = await asyncio.to_thread(scraper.scrape_all, query, location)
        for job in jobs:
            job["query"] = query
            await cache.set(job)

    jobs = deduplicate_jobs(jobs)

    for job in jobs:
        job["score"] = score_job_relevance(job, cv_keywords)

    jobs.sort(key=lambda j: j.get("score", 0), reverse=True)

    for rank, job in enumerate(jobs[:max_results], start=1):
        job["rank"] = rank

    return jobs[:max_results]


async def _async_delegate_to_agent(args: dict) -> str:
    """Run a sub-agent using the async streaming client so it never blocks the event loop."""
    agent_type = args.get("agent_type", "")
    task       = args.get("task", "")
    context    = args.get("context", "")
    system = _SUB_AGENT_PROMPTS.get(agent_type, "You are a helpful career and resume assistant.")
    client = ollama.AsyncClient(host=_OLLAMA_HOST)
    result = ""
    async for chunk in await client.chat(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": f"Task: {task}\n\nContext:\n{context}"},
        ],
        stream=True,
    ):
        result += chunk.message.content or ""
    # Strip Qwen3's <think>…</think> reasoning block — only return the actual structured output.
    # Without this, the think block consumes the entire history budget and the orchestrator
    # sees raw thinking text instead of the structured analysis it needs.
    if "</think>" in result:
        result = result.split("</think>", 1)[1].strip()
    return result


async def _async_save_cv_version(args: dict) -> dict:
    """Save a tailored CV version and return the filename."""
    from tools.cv_versions import CVVersionTracker

    company     = args.get("company", "company")
    role        = args.get("role", "role")
    tex_content = args.get("tex_content", "")
    match_score = float(args.get("match_score", 0.0))

    tracker    = CVVersionTracker()
    version_id = await tracker.save_version(company, role, tex_content, match_score)
    version    = await tracker.get_version(version_id)

    today    = date.today().strftime("%Y-%m-%d")
    safe_co  = re.sub(r"[^\w]", "_", company.lower())[:30].strip("_")
    safe_rol = re.sub(r"[^\w]", "_", role.lower())[:30].strip("_")
    filename = f"cv_{safe_co}_{safe_rol}_{today}.tex"

    return {
        "id":       version_id,
        "filename": filename,
        "status":   "saved",
        "path":     version.get("file_path", "") if version else "",
    }


# ---------------------------------------------------------------------------
# Dispatcher tables
# ---------------------------------------------------------------------------

_HANDLERS: dict[str, Any] = {
    "read_cv":           lambda a: read_cv(),
    "read_overleaf":     lambda a: read_overleaf(),
    "fetch_job_page":    lambda a: fetch_job_page(a["url"]),
    "delegate_to_agent": lambda a: delegate_to_agent(
        a["agent_type"], a["task"], a["context"]
    ),
}

_ASYNC_HANDLERS: dict[str, Any] = {
    "search_jobs_multi":  _async_search_jobs_multi,
    "save_cv_version":    _async_save_cv_version,
    "delegate_to_agent":  _async_delegate_to_agent,
}

# Tools that are synchronous but block (run in thread pool)
BLOCKING_TOOLS: set[str] = {"fetch_job_page"}

# Tools that are natively async (awaited directly in the orchestrator)
ASYNC_TOOLS: set[str] = set(_ASYNC_HANDLERS.keys())


def execute_resume_tool(name: str, args: dict) -> Any:
    handler = _HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Unknown resume tool: {name!r}")
    return handler(args)


async def execute_resume_tool_async(name: str, args: dict) -> Any:
    handler = _ASYNC_HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Unknown async resume tool: {name!r}")
    return await handler(args)
