

## Resume tailoring agent

Open **`http://localhost:8000/resume`** to access a second agent that reads your CV, searches for jobs, and advises you on how to tailor your resume for each role — all locally, no external API keys.

### How it works

```
Browser ──WebSocket──▶ FastAPI /resume/chat ──▶ Ollama (Qwen) orchestrator
                                                        │
                                             tool calls ◀─┘
                                                  │
                             ┌────────────────────┴──────────────────────┐
                             │                                            │
                        External tools                              Sub-agents
                  (read_cv, read_overleaf,                    spawned via Ollama
                   search_jobs, fetch_job_page)               on the same model
```

1. The orchestrator calls `read_cv` first to extract your CV from a local PDF.
2. It optionally reads `read_overleaf` to inspect the exact LaTeX source of your resume.
3. If it needs job-search preferences (role, location, seniority) it asks you directly.
4. It calls `search_jobs` to query DuckDuckGo for relevant postings, then `fetch_job_page` to pull the full text of promising listings.
5. It delegates focused analysis tasks to specialized sub-agents — each is a separate Qwen call with a tailored system prompt.
6. Once all analysis is done it streams the final recommendation token-by-token back to the UI.

### Sub-agents

| Sub-agent | What it does |
|---|---|
| `cv_analyzer` | Extracts structured skills, experience, education, and keywords from your CV text |
| `job_analyzer` | Pulls requirements, tech stack, seniority level, and key responsibilities from a job description |
| `gap_analyzer` | Compares your CV profile against job requirements and produces a match score with specific gaps |
| `tailoring_advisor` | Suggests concrete bullet-point rewrites, keywords to add, and sections to reorder for a target role |

### Resume tools

| Tool | Description |
|---|---|
| `read_cv` | Reads and extracts text from your CV PDF (configured via `CV_PDF_PATH`) |
| `read_overleaf` | Reads the LaTeX `.tex` resume source (configured via `OVERLEAF_TEX_PATH`) |
| `search_jobs` | Searches DuckDuckGo for job listings matching a query |
| `fetch_job_page` | Fetches the full text of a job posting URL |
| `delegate_to_agent` | Spawns one of the four specialized sub-agents above |

### Environment variables

Add these to your `.env` file:

```env
# Paths to your resume files (defaults shown)
CV_PDF_PATH=cv.pdf
OVERLEAF_TEX_PATH=cv.tex
```

The agent reads both files from disk — you never need to paste or upload your CV in the chat.

### Resume API reference

#### `GET /resume`
Serves the resume chat UI.

#### `GET /resume/tools`
Lists all resume tools.

#### `GET /resume/config`
Returns the currently configured file paths.
```json
{ "cv_pdf_path": "cv.pdf", "overleaf_tex_path": "cv.tex" }
```

#### `WS /resume/chat`
Main streaming endpoint — same request/response shape as `/chat`.

**Send:**
```json
{
  "messages": [{ "role": "user", "content": "Find ML engineer roles and tell me how my CV fits" }],
  "system_prompt": null
}
```

**Receive (stream of events):**
```jsonc
{ "type": "tool_start",  "tool": "read_cv",        "args": {} }
{ "type": "tool_end",    "tool": "read_cv",        "preview": "Abdullah Elbarrany…" }
{ "type": "agent_start", "agent": "cv_analyzer",   "task": "Extract structured profile", "args": {…} }
{ "type": "agent_end",   "agent": "cv_analyzer",   "preview": "Skills: Python, FastAPI…" }
{ "type": "tool_start",  "tool": "search_jobs",    "args": { "query": "ML engineer remote 2024" } }
{ "type": "tool_end",    "tool": "search_jobs",    "preview": "[{\"title\": \"…\"}]" }
{ "type": "token",       "content": "Based on your CV, here are the top matches…" }
{ "type": "done",        "tools_called": ["read_cv", "cv_analyzer", "search_jobs", …] }
```
