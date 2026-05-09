import asyncio
import json
import os
from collections.abc import AsyncGenerator

import ollama
from dotenv import load_dotenv

from resume_tools import (
    ASYNC_TOOLS,
    BLOCKING_TOOLS,
    RESUME_TOOL_DEFINITIONS,
    execute_resume_tool,
    execute_resume_tool_async,
)

load_dotenv()

MODEL        = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MAX_TOOL_ROUNDS = 20

ORCHESTRATOR_SYSTEM_PROMPT = """\
You are a resume tailoring orchestrator. You MUST always respond in English only.

## Hard rules — follow without exception
1. ALWAYS respond in English, regardless of what language appears in your reasoning.
2. NEVER ask the user to share, upload, or paste their CV or .tex file. \
   You have tools (read_cv, read_overleaf) that read them from disk — use those.
3. Call read_cv as your very first action whenever you need the resume content.

## Available tools
- read_cv               — reads the user's CV PDF from disk (call this first, always)
- read_overleaf         — reads the LaTeX resume source
- search_jobs_multi     — searches 12 job sites simultaneously; returns scored+ranked jobs
- fetch_job_page        — fetches full text of a job posting URL
- save_cv_version       — saves a tailored CV version (.tex) to disk automatically
- delegate_to_agent     — spawns a specialized Qwen sub-agent:
    • cv_analyzer            → extract structured skills/experience profile + keyword list
    • job_analyzer           → extract requirements, stack, seniority from a job description
    • gap_analyzer           → compare CV profile vs job requirements, find gaps + match score
    • tailoring_advisor      → suggest specific resume rewrites and keyword additions
    • company_research_agent → company stage, culture signals, red/green flags, recommended tone
    • cover_letter_agent     → 3-paragraph cover letter in plain text + LaTeX format

## Job Discovery Flow — follow this EXACTLY when the user asks to find jobs

### STEP 1 — DISCOVER
1. Call read_cv
2. Call delegate_to_agent(cv_analyzer) — obtain a structured profile and keyword list
3. Call search_jobs_multi with the search query, location, and cv_keywords from step 2
   The system will automatically display the ranked job list to the user.

### STEP 2 — WAIT FOR SELECTION
After search_jobs_multi returns, output ONLY this message (or a close equivalent) and STOP:
  "Here are the top jobs I found. Which would you like me to tailor your CV for?
   Reply with a number (e.g. '2'), multiple numbers ('1, 3, 5'), or 'all'."
DO NOT call any more tools until the user replies with their selection.

### STEP 3 — DEEP DIVE (per selected job)
For each job the user selected, run IN ORDER:
  1. fetch_job_page(url)                        — get full job description text
  2. delegate_to_agent(job_analyzer)            — extract requirements + stack
  3. delegate_to_agent(company_research_agent)  — culture / stage / tone signals
  4. delegate_to_agent(gap_analyzer)            — gaps + match score (0–100)
  5. delegate_to_agent(tailoring_advisor)       — concrete bullet rewrites + keywords
  6. delegate_to_agent(cover_letter_agent)      — 3-paragraph cover letter

If the user selected multiple jobs, process them sequentially. Separate each with:
  === [N] Job Title @ Company ===

### STEP 4 — SAVE
After each job's cover letter is produced, call save_cv_version with:
  company     = company name from the job listing
  role        = job title from the job listing
  tex_content = the LaTeX cover letter produced by cover_letter_agent
  match_score = numeric score from gap_analyzer divided by 100 (e.g. 73% → 0.73)
Then tell the user: "Saved as [filename returned by save_cv_version]."

### STEP 5 — FOLLOW-UP LOOP
After processing all selected jobs, ask:
  "Want me to search for more jobs, refine any of these CVs, or update an application status?"

## Clarifying questions
Ask at most 2–3 focused questions when you genuinely need:
  target role, location preference, remote/onsite preference,
  specific companies, or seniority level.
Ask these BEFORE calling search_jobs_multi, not after.

## Follow-up turns
Remember what you already read — do not re-read the CV unless the user asks.\
"""

_client = ollama.AsyncClient(host=OLLAMA_HOST)

_PREVIEW_MAX      = 600
_HISTORY_RESULT_MAX = 6000


def _display_args(name: str, args: dict) -> dict:
    if name == "delegate_to_agent":
        ctx = args.get("context", "")
        return {
            "agent_type": args.get("agent_type"),
            "task":       args.get("task", ""),
            "context":    f"[{len(ctx):,} chars — not shown]",
        }
    if name == "search_jobs_multi":
        return {
            "query":       args.get("query", ""),
            "location":    args.get("location", ""),
            "cv_keywords": f"[{len(args.get('cv_keywords', []))} keywords]",
            "max_results": args.get("max_results", 10),
        }
    return dict(args)


def _preview(result: object) -> str:
    if isinstance(result, (list, dict)):
        text = json.dumps(result, default=str, indent=2)
    else:
        text = str(result)
    return text[:_PREVIEW_MAX] + (" …" if len(text) > _PREVIEW_MAX else "")


async def _call_tool(name: str, args: dict) -> object:
    """Dispatch a tool call. Async tools are awaited directly; blocking sync
    tools run in a thread pool; lightweight sync tools run in-line."""
    if name in ASYNC_TOOLS:
        return await execute_resume_tool_async(name, args)
    if name in BLOCKING_TOOLS:
        return await asyncio.to_thread(execute_resume_tool, name, args)
    return execute_resume_tool(name, args)


async def run_resume_agent_stream(
    messages: list[dict],
    system_prompt: str | None = None,
    session_ctx: list[dict] | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Async generator yielding WebSocket-ready event dicts.

    Pass `session_ctx` (a mutable list) to enable persistent multi-turn sessions.
    The list is populated on the first call and extended on subsequent calls so
    that tool results, job URLs, and prior analysis remain in the model's context.

    Tool events:
      {"type": "tool_start",        "tool": "<name>",   "args": {...}}
      {"type": "tool_end",          "tool": "<name>",   "preview": "<str>"}

    Sub-agent events:
      {"type": "agent_start",       "agent": "<type>",  "task": "<str>", "args": {...}}
      {"type": "agent_end",         "agent": "<type>",  "preview": "<str>"}

    Job discovery events (Enhancement 7):
      {"type": "job_list",          "jobs": [...]}
      {"type": "awaiting_selection"}

    Answer streaming:
      {"type": "token",             "content": "<str>"}
      {"type": "done",              "tools_called": [...]}
      {"type": "error",             "message": "<str>"}
    """
    system = system_prompt or ORCHESTRATOR_SYSTEM_PROMPT

    if session_ctx is None:
        # Stateless mode (backward-compat): fresh context each call
        current_messages: list[dict] = [{"role": "system", "content": system}, *messages]
    elif not session_ctx:
        # First call of a persistent session — seed the list in place
        session_ctx.append({"role": "system", "content": system})
        session_ctx.extend(messages)
        current_messages = session_ctx
    else:
        # Follow-up turn — just append the new user messages
        session_ctx.extend(messages)
        current_messages = session_ctx

    tools_called: list[str] = []

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = await _client.chat(
                model=MODEL,
                messages=current_messages,
                tools=RESUME_TOOL_DEFINITIONS,
            )
        except Exception as exc:
            yield {"type": "error", "message": f"Model error: {exc}"}
            return

        msg = response.message

        if not msg.tool_calls:
            break

        current_messages.append({
            "role":       "assistant",
            "content":    msg.content or "",
            "tool_calls": [
                {"function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            name    = tc.function.name
            args    = tc.function.arguments or {}
            display = _display_args(name, args)
            tools_called.append(name)

            # Emit start event
            if name == "delegate_to_agent":
                yield {
                    "type":  "agent_start",
                    "agent": args.get("agent_type", "agent"),
                    "task":  args.get("task", ""),
                    "args":  display,
                }
            else:
                yield {"type": "tool_start", "tool": name, "args": display}

            # Execute
            raw_result = None
            try:
                raw_result = await _call_tool(name, args)
                result_str = json.dumps(raw_result, default=str)
                preview    = _preview(raw_result)
            except Exception as exc:
                result_str = json.dumps({"error": str(exc)})
                preview    = f"Error: {exc}"

            # Truncate before storing — large tool results corrupt Qwen3 XML context
            if len(result_str) > _HISTORY_RESULT_MAX:
                result_str = result_str[:_HISTORY_RESULT_MAX] + " …[truncated]"

            current_messages.append({"role": "tool", "content": result_str})

            # Emit end event
            if name == "delegate_to_agent":
                yield {
                    "type":    "agent_end",
                    "agent":   args.get("agent_type", "agent"),
                    "preview": preview,
                }
            else:
                yield {"type": "tool_end", "tool": name, "preview": preview}

            # Enhancement 7: after job search, push the ranked list to the frontend
            if name == "search_jobs_multi" and isinstance(raw_result, list) and raw_result:
                yield {"type": "job_list",          "jobs": raw_result}
                yield {"type": "awaiting_selection"}

    else:
        yield {
            "type":        "done",
            "tools_called": tools_called,
            "error":        "max tool rounds reached",
        }
        return

    # Stream final answer, stripping Qwen3's <think>…</think> block
    buf        = ""
    past_think = False
    final_text = ""
    async for chunk in await _client.chat(
        model=MODEL,
        messages=current_messages,
        stream=True,
    ):
        content = chunk.message.content
        if not content:
            continue

        if past_think:
            final_text += content
            yield {"type": "token", "content": content}
            continue

        buf += content
        if "</think>" in buf:
            past_think = True
            after = buf.split("</think>", 1)[1]
            buf   = ""
            if after:
                final_text += after
                yield {"type": "token", "content": after}
        elif "<think>" not in buf and len(buf) > 20:
            # Model has no think block — flush buffer and stream normally
            past_think = True
            final_text += buf
            yield {"type": "token", "content": buf}
            buf = ""

    if buf and not past_think:
        final_text += buf
        yield {"type": "token", "content": buf}

    # Store the assistant's response in the persistent session so the next turn
    # has full context (including which jobs were listed, URLs, analysis, etc.)
    if session_ctx is not None and final_text:
        current_messages.append({"role": "assistant", "content": final_text})

    yield {"type": "done", "tools_called": tools_called}
