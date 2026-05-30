# Local LLM Job Workbench

A fully local, privacy-first job search and resume tailoring workbench powered by **Ollama + Qwen3**. No external API keys — everything runs on your machine.

---

## What it does

- **Search jobs** across 12 job sites simultaneously (LinkedIn, Indeed, Glassdoor, Wuzzuf, Bayt, NaukriGulf, Remotive, WeWorkRemotely, Jobicy, Otta, Himalayas, Wellfound)
- **Score and rank** results against your CV keywords using an LLM fit score (0–100%)
- **Filter** by minimum fit score, remote-friendly, MENA/EMEA/Africa open, and hide senior roles
- **Tailor your CV** for a specific job — an orchestrator agent reads your PDF, analyzes the job, finds gaps, and writes a cover letter
- **Track applications** in a Kanban pipeline: Saved → Applied → Interview → Offer
- **Cache jobs** locally so results survive page refreshes and navigation

---

## Architecture

```
Browser (React SPA)
    │
    ├── REST  ──▶  FastAPI  ──▶  Job scrapers (12 sites)
    │                     ──▶  Quality gate + LLM ranker
    │                     ──▶  SQLite job cache
    │
    └── WebSocket  ──▶  FastAPI  ──▶  Ollama (Qwen3) orchestrator
                                           │
                                  tool calls + sub-agents
                                           │
                         ┌─────────────────┴──────────────────┐
                         │                                      │
                    Local tools                           Sub-agents
              (read_cv, fetch_job_page,             cv_analyzer, job_analyzer,
               search_jobs_multi,                   gap_analyzer, tailoring_advisor,
               save_cv_version)                     cover_letter_agent, company_research_agent
```

---

## Setup

### 1. Install dependencies

```bash
uv pip install -r requirements.txt
```

### 2. Configure `.env`

```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:8b          # or any model you have pulled

CV_PDF_PATH=AE_New.pdf         # path to your CV PDF
OVERLEAF_TEX_PATH=main.tex     # path to your LaTeX resume source (optional)
```

### 3. Build the frontend

```bash
cd frontend
npm install
npm run build
```

### 4. Start the server

```bash
uvicorn main:app --reload
```

Open **http://localhost:8000** in your browser.

---

## Views

### Jobs
Search bar + source checkboxes + filter bar. Type a job title and press Search. Results are scored by the LLM and cached in `localStorage` so they survive refresh. Each card shows:
- Source badge, fit score bar, matched keywords
- Remote / MENA·EMEA·Africa badges (auto-detected from job text)
- Senior role warning badge
- **Save** button → status dropdown (Saved / Applied / Interview / Offer / Rejected)
- **Tailor CV** button → navigates to Resume view with job context pre-loaded

### Resume
Chat interface connected via WebSocket to the Qwen3 orchestrator. When navigated from a job card, automatically sends the job title, company, URL, and description so the agent can start immediately. Shows live tool/agent progress during processing (e.g. "Calling tool: read_cv…", "Running gap_analyzer agent…").

### Pipeline
Kanban board with four columns: **Saved / Applied / Interview / Offer**. Drag cards between columns to update status. Click a card to open a side panel with the full job description and a notes field.

### Chat
General-purpose chat with the same Qwen3 agent — ask anything about your CV or job search.

---

## Sub-agents

| Sub-agent | What it does |
|---|---|
| `cv_analyzer` | Extracts structured skills, experience, and keyword list from your CV |
| `job_analyzer` | Pulls requirements, tech stack, and seniority from a job description |
| `gap_analyzer` | Compares CV vs job requirements, produces a match score with specific gaps |
| `tailoring_advisor` | Suggests bullet rewrites, keywords to add, and sections to reorder |
| `cover_letter_agent` | Writes a 3-paragraph cover letter in plain text + LaTeX |
| `company_research_agent` | Researches company stage, culture signals, and recommended tone |

---

## API reference

### `POST /jobs/search`
Scrapes all sources, applies quality gate, caches results, returns augmented job list with `url_hash`, `quality_score`, `rejection_reason`, `flagged_senior`, `remote_friendly`, `region_open`.

### `POST /jobs/rank`
Takes a list of jobs + CV keywords, scores each with LLM, returns jobs with `fit_score`, `fit_reason`, `matched_keywords`.

### `PATCH /jobs/{url_hash}/status`
Updates application status. Valid values: `new`, `saved`, `applied`, `interview`, `offer`, `rejected`.

### `PATCH /jobs/{url_hash}/notes`
Saves freeform notes for a job.

### `GET /jobs/pipeline`
Returns `{ saved: [...], applied: [...], interview: [...], offer: [...] }`.

### `WS /resume/chat`
Main resume agent stream. Send `{ messages: [...] }`, receive a stream of events:

```jsonc
{ "type": "tool_start",  "tool": "read_cv", "args": {} }
{ "type": "tool_end",    "tool": "read_cv", "preview": "…" }
{ "type": "agent_start", "agent": "cv_analyzer", "task": "…", "args": {} }
{ "type": "agent_end",   "agent": "cv_analyzer", "preview": "…" }
{ "type": "job_list",    "jobs": [...] }
{ "type": "awaiting_selection" }
{ "type": "token",       "content": "…" }
{ "type": "done",        "tools_called": ["read_cv", "cv_analyzer", …] }
{ "type": "error",       "message": "…" }
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `qwen3:8b` | Model to use for all LLM calls |
| `CV_PDF_PATH` | `cv.pdf` | Path to your CV PDF |
| `OVERLEAF_TEX_PATH` | `main.tex` | Path to your LaTeX resume source |
