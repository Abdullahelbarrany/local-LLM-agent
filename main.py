import subprocess
import time
import urllib.request
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from database import get_pool
from llm import OLLAMA_HOST, run_agent_stream
from models import ChatRequest
from tools import TOOL_DEFINITIONS


def _ensure_ollama_running() -> None:
    """Start `ollama serve` if the daemon is not already responding."""
    url = f"{OLLAMA_HOST}/api/tags"
    try:
        urllib.request.urlopen(url, timeout=2)
        print("[info] Ollama is already running.")
        return
    except Exception:
        pass

    print("[info] Starting Ollama...")
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(20):
        time.sleep(1)
        try:
            urllib.request.urlopen(url, timeout=2)
            print("[info] Ollama is ready.")
            return
        except Exception:
            pass

    print("[warn] Ollama did not respond after 20 s — continuing anyway.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_ollama_running()
    try:
        get_pool()
    except Exception as exc:
        print(f"[warn] Could not connect to MySQL on startup: {exc}")
    yield


app = FastAPI(
    title="Local LLM Agent",
    description="Qwen via Ollama with MySQL tool calling",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse("static/index.html")


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.get("/tools", tags=["meta"])
def list_tools():
    return {
        "tools": [
            {
                "name": t["function"]["name"],
                "description": t["function"]["description"],
            }
            for t in TOOL_DEFINITIONS
        ]
    }


@app.websocket("/chat")
async def chat_ws(websocket: WebSocket):
    """
    WebSocket endpoint. Send one JSON message to start a session:
      {"messages": [{"role": "user", "content": "..."}], "system_prompt": null}

    The server streams back:
      {"type": "tool_call", "tool": "<name>"}     — while querying the DB
      {"type": "token",     "content": "<str>"}   — streamed answer tokens
      {"type": "done",      "tools_called": [...]} — signals end of stream
      {"type": "error",     "message": "<str>"}   — on failure
    """
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        req = ChatRequest(**data)
        messages = [m.model_dump() for m in req.messages]

        if not messages:
            await websocket.send_json({"type": "error", "message": "messages must not be empty"})
            return

        async for event in run_agent_stream(messages, system_prompt=req.system_prompt):
            await websocket.send_json(event)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
    finally:
        await websocket.close()
