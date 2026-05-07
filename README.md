# Local LLM Agent

![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)

A fully local AI assistant that connects a [Qwen](https://ollama.com/library/qwen3.5) language model (via [Ollama](https://ollama.com)) to a live MySQL project-management database. Ask natural-language questions about your projects, sprints, tasks, and team — the model picks the right database tools, queries them, and streams the answer back token-by-token through a WebSocket.

![Chat UI](Screenshot%202026-05-03%20185559.png)

---

## How it works

```
Browser ──WebSocket──▶ FastAPI ──▶ Ollama (Qwen)
                                       │
                          tool calls ◀─┘
                               │
                           MySQL DB
                     (projects / sprints / tasks / team)
```

1. The browser opens a WebSocket and sends the full conversation history as JSON.
2. FastAPI forwards it to Ollama with 8 read-only tool definitions attached.
3. Qwen decides which tools to call. FastAPI executes each SQL query and feeds the result back.
4. Once Qwen has enough data it streams the final answer token-by-token back through the WebSocket.
5. The UI renders each token in real time, with animated chips showing which tools were called.

---

## Tech stack

| Layer | Technology |
|---|---|
| LLM runtime | [Ollama](https://ollama.com) — local inference, no API key needed |
| Model | Qwen 3.5 9B (configurable via `OLLAMA_MODEL`) |
| API server | [FastAPI](https://fastapi.tiangolo.com) + Uvicorn |
| Streaming transport | WebSocket (`/chat`) |
| Database | MySQL via `mysql-connector-python` |
| Validation | Pydantic v2 |
| Frontend | Vanilla HTML/CSS/JS — zero build step, zero dependencies |
| Package manager | [uv](https://github.com/astral-sh/uv) |

---

## Project structure

```
local-LLM-agent/
├── main.py          # FastAPI app, WebSocket endpoint, Ollama auto-start
├── llm.py           # Agentic loop — tool-call rounds + streaming final answer
├── tools.py         # 8 tool definitions + SQL handler functions
├── database.py      # MySQL connection pool + query helper
├── models.py        # Pydantic request / response models
├── schema.sql       # CREATE TABLE + example data (copy-paste ready)
├── static/
│   └── index.html   # Chat UI (served at /)
├── test_ws.py       # CLI WebSocket smoke-test
├── test.http        # REST Client tests for HTTP endpoints
├── .env.example     # Environment variable template
├── requirements.txt
└── README.md
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | |
| [uv](https://github.com/astral-sh/uv) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [Ollama](https://ollama.com/download) | Must be installed; the server starts it automatically |
| MySQL 8+ | Running locally or accessible over the network |

---

## Installation

```bash
# 1. Clone / enter the project
cd local-LLM-agent

# 2. Create a virtual environment and install dependencies
uv venv
uv pip install -r requirements.txt

# 3. Pull the model (once)
ollama pull qwen3.5:9b
```

---

## Database setup

Run the provided SQL script to create the schema and load example data (3 projects, 9 sprints, 37 tasks, 5 team members):

```bash
mysql -u root -p < schema.sql
```

This creates a database called `project_db` with four tables:

| Table | Key columns |
|---|---|
| `projects` | id, name, description, team_members, progress %, status |
| `sprints` | id, project_id, name, goal, start_date, end_date, status |
| `tasks` | id, sprint_id, project_id, title, assigned_to, status, priority |
| `team_members` | id, name, role, email |

---

## Environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
# MySQL connection
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=project_db
MYSQL_USER=root
MYSQL_PASSWORD=your_password_here

# Ollama — optional, both default to the values shown
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3.5:9b
```

`OLLAMA_HOST` and `OLLAMA_MODEL` are optional. The server starts Ollama automatically if it is not already running.

---

## Running

```bash
uvicorn main:app --reload
```

On first start the server will:
1. Detect whether `ollama serve` is running — if not, spawn it and wait up to 20 s.
2. Open the MySQL connection pool.
3. Begin serving at `http://localhost:8000`.

Open **`http://localhost:8000`** in your browser to use the chat UI.

---

## API reference

### `GET /health`
Liveness check.
```json
{ "status": "ok" }
```

### `GET /tools`
Lists all available database tools.
```json
{
  "tools": [
    { "name": "get_all_projects", "description": "Fetch all projects…" },
    ...
  ]
}
```

### `WS /chat`
Main streaming endpoint.

**Send** (once per connection):
```json
{
  "messages": [
    { "role": "user", "content": "Which sprints are active?" }
  ],
  "system_prompt": null
}
```

**Receive** (stream of events):
```jsonc
{ "type": "tool_call", "tool": "get_active_sprints" }   // DB lookup in progress
{ "type": "token",     "content": "There are currently" } // answer streaming
{ "type": "token",     "content": " 2 active sprints…" }
{ "type": "done",      "tools_called": ["get_active_sprints"] } // end of stream
{ "type": "error",     "message": "…" }                  // only on failure
```

---

## Available tools

The LLM can call any of these read-only tools during a response:

| Tool | Description |
|---|---|
| `get_all_projects` | All projects with status and progress % |
| `get_project_details` | Full detail for one project by ID |
| `get_project_sprints` | All sprints for a project, ordered by date |
| `get_sprint_tasks` | All tasks inside a specific sprint |
| `get_project_tasks` | All tasks across a project |
| `get_team_members` | Everyone's name, role, and email |
| `get_tasks_by_assignee` | Tasks assigned to a named person |
| `get_active_sprints` | All active sprints joined with project name |

---

## CLI test

```bash
# Run the default smoke-test questions
python test_ws.py

# Ask a custom question
python test_ws.py "Who has the most in-progress tasks?"
```

---

## Switching models

Any Ollama model that supports tool calling works. Change `OLLAMA_MODEL` in `.env`:

```env
OLLAMA_MODEL=qwen3.5:9b      # default
OLLAMA_MODEL=qwen3.5:14b     # larger, more capable
OLLAMA_MODEL=llama3.1         # Meta Llama
OLLAMA_MODEL=mistral          # Mistral 7B
```

Then pull it first: `ollama pull <model-name>`

---

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
