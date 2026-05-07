import asyncio
import json
import os
from collections.abc import AsyncGenerator

import ollama
from dotenv import load_dotenv

from resume_tools import BLOCKING_TOOLS, RESUME_TOOL_DEFINITIONS, execute_resume_tool

load_dotenv()

MODEL = os.getenv("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MAX_TOOL_ROUNDS = 20

ORCHESTRATOR_SYSTEM_PROMPT = """\
You are a resume tailoring orchestrator. You MUST always respond in English only.

## Hard rules — follow without exception
1. ALWAYS respond in English, regardless of what language appears in your reasoning.
2. NEVER ask the user to share, upload, or paste their CV or .tex file. \
   You have tools (read_cv, read_overleaf) that read them from disk — use those.
3. Call read_cv as your very first action whenever you need the resume content. \
   Do not wait for the user to provide it.

## When to ask the user questions
You SHOULD ask short, focused clarifying questions when you genuinely need information \
that is not in the CV and cannot be inferred. Good examples:
- Target role or industry (e.g. "Are you aiming for backend, ML, or full-stack roles?")
- Preferred location or remote preference
- Seniority level or company size preference
- Specific companies or job boards to focus on
- Whether they have a particular job posting in mind

Ask at most 2–3 questions at a time, and only when the answer would meaningfully change \
what you search for or recommend.

## Tools available
- read_cv           — reads the user's CV PDF from disk (call this first, always)
- read_overleaf     — reads the LaTeX resume source
- search_jobs       — searches DuckDuckGo for job listings
- fetch_job_page    — fetches full text of a job posting URL
- delegate_to_agent — spawns a specialized Qwen sub-agent:
    • cv_analyzer       → extract structured skills/experience profile
    • job_analyzer      → extract requirements from a job description
    • gap_analyzer      → compare CV profile vs job requirements, find gaps
    • tailoring_advisor → suggest specific resume rewrites and keyword additions

## Workflow
1. Call read_cv (and read_overleaf if LaTeX structure is useful)
2. Delegate to cv_analyzer to extract a structured profile
3. If you still need job preferences, ask the user now (role, location, seniority)
4. Call search_jobs with targeted queries
5. Call fetch_job_page on 2–3 relevant results
6. Delegate to job_analyzer, gap_analyzer, tailoring_advisor as needed
7. Summarise findings clearly in English

In follow-up turns, remember what you already read — do not re-read the CV unless asked.\
"""

_client = ollama.AsyncClient(host=OLLAMA_HOST)

_PREVIEW_MAX = 600
# Qwen3 uses XML internally for tool calls; large tool results corrupt the context.
# Keep history entries short — enough for the model to reason, not so long it breaks.
_HISTORY_RESULT_MAX = 3000


def _display_args(name: str, args: dict) -> dict:
    """Return args safe for display — truncate large context fields."""
    if name == "delegate_to_agent":
        ctx = args.get("context", "")
        return {
            "agent_type": args.get("agent_type"),
            "task": args.get("task", ""),
            "context": f"[{len(ctx):,} chars — not shown]",
        }
    return dict(args)


def _preview(result) -> str:
    """Truncate a tool result to a readable preview string."""
    if isinstance(result, (list, dict)):
        text = json.dumps(result, default=str, indent=2)
    else:
        text = str(result)
    return text[:_PREVIEW_MAX] + (" …" if len(text) > _PREVIEW_MAX else "")


async def _call_tool(name: str, args: dict):
    """Run blocking tools in a thread pool so we don't freeze the event loop."""
    if name in BLOCKING_TOOLS:
        return await asyncio.to_thread(execute_resume_tool, name, args)
    return execute_resume_tool(name, args)


async def run_resume_agent_stream(
    messages: list[dict],
    system_prompt: str | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Async generator yielding WebSocket-ready event dicts:

    Tool events (non-agent tools):
      {"type": "tool_start",  "tool": "<name>",        "args": {...}}
      {"type": "tool_end",    "tool": "<name>",        "preview": "<str>"}

    Sub-agent delegation events:
      {"type": "agent_start", "agent": "<type>",       "task": "<str>", "args": {...}}
      {"type": "agent_end",   "agent": "<type>",       "preview": "<str>"}

    Answer streaming:
      {"type": "token",       "content": "<str>"}
      {"type": "done",        "tools_called": [...]}
      {"type": "error",       "message": "<str>"}
    """
    system = system_prompt or ORCHESTRATOR_SYSTEM_PROMPT
    current_messages: list[dict] = [{"role": "system", "content": system}, *messages]
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
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            name = tc.function.name
            args = tc.function.arguments or {}
            tools_called.append(name)
            display = _display_args(name, args)

            if name == "delegate_to_agent":
                yield {
                    "type": "agent_start",
                    "agent": args.get("agent_type", "agent"),
                    "task": args.get("task", ""),
                    "args": display,
                }
            else:
                yield {"type": "tool_start", "tool": name, "args": display}

            try:
                result = await _call_tool(name, args)
                result_str = json.dumps(result, default=str)
                preview = _preview(result)
            except Exception as exc:
                result_str = json.dumps({"error": str(exc)})
                preview = f"Error: {exc}"

            # Truncate before storing in history to prevent XML context corruption
            if len(result_str) > _HISTORY_RESULT_MAX:
                result_str = result_str[:_HISTORY_RESULT_MAX] + " ...[truncated]"

            current_messages.append({"role": "tool", "content": result_str})

            if name == "delegate_to_agent":
                yield {
                    "type": "agent_end",
                    "agent": args.get("agent_type", "agent"),
                    "preview": preview,
                }
            else:
                yield {"type": "tool_end", "tool": name, "preview": preview}

    else:
        yield {"type": "done", "tools_called": tools_called, "error": "max tool rounds reached"}
        return

    # Stream final answer, stripping any <think>…</think> block Qwen3 emits
    buf = ""
    past_think = False
    async for chunk in await _client.chat(
        model=MODEL,
        messages=current_messages,
        stream=True,
    ):
        content = chunk.message.content
        if not content:
            continue

        if past_think:
            yield {"type": "token", "content": content}
            continue

        buf += content
        if "</think>" in buf:
            past_think = True
            after = buf.split("</think>", 1)[1]
            buf = ""
            if after:
                yield {"type": "token", "content": after}
        elif "<think>" not in buf and len(buf) > 20:
            # Model has no think block — flush buffer and stream normally
            past_think = True
            yield {"type": "token", "content": buf}
            buf = ""

    if buf and past_think is False:
        yield {"type": "token", "content": buf}

    yield {"type": "done", "tools_called": tools_called}
