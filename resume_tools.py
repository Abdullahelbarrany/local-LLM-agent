import os
import re
from typing import Any

import httpx
import ollama
from dotenv import load_dotenv

load_dotenv()

_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
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
            "name": "search_jobs",
            "description": (
                "Search DuckDuckGo for job listings matching a query. "
                "Returns titles, URLs, and snippets. Use specific queries like "
                "'machine learning engineer remote 2024'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Job search query, e.g. 'software engineer Python remote'",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results to return (default 6, max 10)",
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
                "Use after search_jobs to get the complete job description and requirements."
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
            "name": "delegate_to_agent",
            "description": (
                "Spawn a specialized Qwen sub-agent to perform a focused analysis. "
                "agent_type options:\n"
                "  - 'cv_analyzer': extract skills, experience, education, keywords from CV text\n"
                "  - 'job_analyzer': extract requirements, tech stack, seniority from a job description\n"
                "  - 'gap_analyzer': compare CV profile vs job requirements, identify missing skills\n"
                "  - 'tailoring_advisor': suggest specific resume rewrites and keyword additions for a job"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_type": {
                        "type": "string",
                        "enum": ["cv_analyzer", "job_analyzer", "gap_analyzer", "tailoring_advisor"],
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
        "Be thorough and use clear sections."
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
        "3. MATCH SCORE: an overall percentage with a brief reason\n"
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
}

# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def read_cv() -> str:
    path = os.getenv("CV_PDF_PATH", "cv.pdf")
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text if text.strip() else "PDF opened but no text extracted (may be image-based scan)."
    except FileNotFoundError:
        return (
            f"CV PDF not found at '{path}'. "
            "Set the CV_PDF_PATH environment variable to the correct path."
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
            "Set the OVERLEAF_TEX_PATH environment variable to the correct path."
        )
    except Exception as exc:
        return f"Error reading .tex file: {exc}"


def search_jobs(query: str, max_results: int = 6) -> list[dict]:
    max_results = min(max_results, 10)
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
        ]
    except ImportError:
        return [{"error": "ddgs not installed. Run: uv pip install ddgs"}]
    except Exception as exc:
        return [{"error": f"Search failed: {exc}"}]


def fetch_job_page(url: str) -> str:
    try:
        resp = httpx.get(
            url,
            timeout=15,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )
        text = re.sub(r"<[^>]+>", " ", resp.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:5000]
    except Exception as exc:
        return f"Error fetching '{url}': {exc}"


def delegate_to_agent(agent_type: str, task: str, context: str) -> str:
    system = _SUB_AGENT_PROMPTS.get(agent_type, "You are a helpful career and resume assistant.")
    client = ollama.Client(host=_OLLAMA_HOST)
    response = client.chat(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": f"Task: {task}\n\nContext:\n{context}"},
        ],
    )
    return response.message.content

# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_HANDLERS: dict[str, Any] = {
    "read_cv":           lambda a: read_cv(),
    "read_overleaf":     lambda a: read_overleaf(),
    "search_jobs":       lambda a: search_jobs(a["query"], a.get("max_results", 6)),
    "fetch_job_page":    lambda a: fetch_job_page(a["url"]),
    "delegate_to_agent": lambda a: delegate_to_agent(a["agent_type"], a["task"], a["context"]),
}

# Tools that block and must run in a thread pool
BLOCKING_TOOLS = {"search_jobs", "fetch_job_page", "delegate_to_agent"}


def execute_resume_tool(name: str, args: dict) -> Any:
    handler = _HANDLERS.get(name)
    if handler is None:
        raise ValueError(f"Unknown resume tool: {name!r}")
    return handler(args)
