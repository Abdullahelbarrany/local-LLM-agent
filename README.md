# Local LLM Agent

A fully local AI assistant that connects a [Qwen](https://ollama.com/library/qwen2.5) language model (via [Ollama](https://ollama.com)) to a live MySQL project-management database. Ask natural-language questions about your projects, sprints, tasks, and team — the model picks the right database tools, queries them, and streams the answer back token-by-token through a WebSocket.

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
| Model | Qwen 2.5 (configurable via `OLLAMA_MODEL`) |
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
ollama pull qwen2.5
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
OLLAMA_MODEL=qwen2.5
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
OLLAMA_MODEL=qwen2.5:14b     # larger, more capable
OLLAMA_MODEL=llama3.1         # Meta Llama
OLLAMA_MODEL=mistral          # Mistral 7B
```

Then pull it first: `ollama pull <model-name>`
