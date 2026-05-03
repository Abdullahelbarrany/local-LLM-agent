"""Quick WebSocket smoke-test. Run with: python test_ws.py"""
import asyncio
import json
import sys
import websockets

URL = "ws://localhost:8000/chat"

TESTS = [
    "Give me a summary of all projects and their current status.",
    "Which sprints are currently active?",
    "What tasks are assigned to Alice?",
]


async def chat(question: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"Q: {question}")
    print("─" * 60)

    async with websockets.connect(URL) as ws:
        await ws.send(json.dumps({"messages": [{"role": "user", "content": question}]}))

        async for raw in ws:
            event = json.loads(raw)
            match event["type"]:
                case "tool_call":
                    print(f"[tool] {event['tool']}")
                case "token":
                    print(event["content"], end="", flush=True)
                case "done":
                    print(f"\n[done] tools used: {event.get('tools_called', [])}")
                    break
                case "error":
                    print(f"[error] {event['message']}")
                    break


async def main() -> None:
    questions = sys.argv[1:] or TESTS
    for q in questions:
        await chat(q)


if __name__ == "__main__":
    asyncio.run(main())
