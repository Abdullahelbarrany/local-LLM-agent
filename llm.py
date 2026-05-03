import json
import os
from collections.abc import AsyncGenerator

import ollama
from dotenv import load_dotenv

from tools import TOOL_DEFINITIONS, execute_tool

load_dotenv()

MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MAX_TOOL_ROUNDS = 10

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful project management assistant. "
    "You have access to a live database with projects, sprints, tasks, and team members. "
    "Use the provided tools to look up accurate data before answering. "
    "Be concise and factual."
)

_client = ollama.AsyncClient(host=OLLAMA_HOST)


async def run_agent_stream(
    messages: list[dict],
    system_prompt: str | None = None,
) -> AsyncGenerator[dict, None]:
    """
    Async generator that yields WebSocket-ready event dicts:
      {"type": "tool_call", "tool": "<name>"}    — each tool the model invokes
      {"type": "token",     "content": "<str>"}  — streamed tokens of the final answer
      {"type": "done",      "tools_called": [...]} — end-of-stream sentinel
    """
    system = system_prompt or DEFAULT_SYSTEM_PROMPT
    current_messages: list[dict] = [{"role": "system", "content": system}, *messages]
    tools_called: list[str] = []

    # ── Tool-calling phase (non-streaming so we can inspect tool_calls) ──────
    for _ in range(MAX_TOOL_ROUNDS):
        response = await _client.chat(
            model=MODEL,
            messages=current_messages,
            tools=TOOL_DEFINITIONS,
        )
        msg = response.message

        if not msg.tool_calls:
            # No more tool calls → fall through to streaming phase
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
            yield {"type": "tool_call", "tool": name}

            try:
                result = execute_tool(name, args)
                result_str = json.dumps(result, default=str)
            except Exception as exc:
                result_str = json.dumps({"error": str(exc)})

            current_messages.append({"role": "tool", "content": result_str})

    else:
        # Loop exhausted without break — hit MAX_TOOL_ROUNDS
        yield {"type": "done", "tools_called": tools_called, "error": "max tool rounds reached"}
        return

    # ── Streaming phase — final answer ───────────────────────────────────────
    async for chunk in await _client.chat(
        model=MODEL,
        messages=current_messages,
        stream=True,
    ):
        content = chunk.message.content
        if content:
            yield {"type": "token", "content": content}

    yield {"type": "done", "tools_called": tools_called}
