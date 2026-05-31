import asyncio
import hashlib
import json
import os
import subprocess
import time
import urllib.request
from contextlib import asynccontextmanager

import ollama as _ollama

from fastapi import FastAPI, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from llm import OLLAMA_HOST
from models import (
    ChatRequest,
    JobSearchRequest,
    PatchNotesRequest,
    PatchStatusRequest,
    RankRequest,
)
from resume_llm import run_cover_letter_stream, run_resume_agent_stream
from resume_tools import RESUME_TOOL_DEFINITIONS
from tools.cv_versions import CVVersionTracker
from tools.job_cache import JobCache
from tools.job_scrapers import JobScraper
from tools.quality_gate import apply_quality_gate
from tools.ranker import rank_jobs

_cache = JobCache()
_scraper = JobScraper()


def _ensure_ollama_running() -> None:
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
    await _cache.init_db()
    yield


app = FastAPI(
    title="Local LLM Job Workbench",
    description="Qwen via Ollama — job intelligence, resume tailoring, PM assistant",
    version="2.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Jobs — REST endpoints
# ---------------------------------------------------------------------------

@app.post("/jobs/search", tags=["jobs"])
async def jobs_search(req: JobSearchRequest):
    """Scrape jobs, apply quality gate, cache results, return augmented list."""
    # Bug 4: check cache before scraping
    cached = await _cache.get_all_for_query(req.query, max_age_hours=6)
    if len(cached) >= 20:
        accepted = [j for j in cached if j.get("rejection_reason") is None
                    and (j.get("remote_friendly") or j.get("region_open"))]
        if req.sources:
            sources_lower = {s.lower() for s in req.sources}
            accepted = [j for j in accepted if (j.get("source") or "").lower() in sources_lower]
        return {"jobs": accepted[:30], "cache_hit": True}

    # Force remote/EMEA location if caller left it blank
    location = req.location or "Remote"

    loop = asyncio.get_event_loop()
    raw: list[dict] = await loop.run_in_executor(
        None, _scraper.scrape_all, req.query, location
    )

    if req.sources:
        sources_lower = {s.lower() for s in req.sources}
        raw = [j for j in raw if (j.get("source") or "").lower() in sources_lower]

    gated = apply_quality_gate(raw)

    # Bug 3: split accepted/rejected — cache both, return only accepted
    # Only surface remote-friendly or region-open jobs
    accepted = [j for j in gated if j.get("rejection_reason") is None
                and (j.get("remote_friendly") or j.get("region_open"))]
    rejected = [j for j in gated if j.get("rejection_reason") is not None]

    for job in gated:
        url = job.get("url") or ""
        job["url_hash"] = hashlib.sha256(url.encode()).hexdigest()
        try:
            await _cache.set(job)
        except Exception:
            pass

    return {"jobs": accepted[:30], "cache_hit": False}


@app.post("/jobs/rank", tags=["jobs"])
async def jobs_rank(req: RankRequest):
    """Rank jobs by keyword overlap + optional LLM scoring."""
    ranked = await rank_jobs(req.jobs, req.cv_keywords)
    # Bug 1: persist fit scores to DB
    for job in ranked:
        if job.get("fit_score") is not None:
            try:
                await _cache.update_fit(
                    job["url"],
                    job["fit_score"],
                    job.get("fit_reason", ""),
                    job.get("matched_keywords"),
                )
            except Exception:
                pass
    return ranked


@app.patch("/jobs/{url_hash}/status", tags=["jobs"])
async def patch_job_status(url_hash: str, req: PatchStatusRequest):
    await _cache.update_status_by_hash(url_hash, req.status)
    return {"ok": True}


@app.patch("/jobs/{url_hash}/notes", tags=["jobs"])
async def patch_job_notes(url_hash: str, req: PatchNotesRequest):
    await _cache.update_notes_by_hash(url_hash, req.notes)
    return {"ok": True}


@app.get("/jobs/recent", tags=["jobs"])
async def jobs_recent():
    """Return the 50 most recently fetched accepted jobs from SQLite."""
    return await _cache.get_recent()


@app.get("/jobs/pipeline", tags=["jobs"])
async def jobs_pipeline():
    """Return jobs grouped by pipeline status."""
    saved, applied, interview, offer = await asyncio.gather(
        _cache.get_by_status("saved"),
        _cache.get_by_status("applied"),
        _cache.get_by_status("interview"),
        _cache.get_by_status("offer"),
    )
    return {"saved": saved, "applied": applied, "interview": interview, "offer": offer}


# ---------------------------------------------------------------------------
# Resume — CV parsing & keyword extraction
# ---------------------------------------------------------------------------

@app.post("/resume/extract-keywords", tags=["resume"])
async def extract_keywords(file: UploadFile | None = None, text: str | None = None):
    """
    Accept a CV as a file upload or raw text, extract top skills/keywords via Ollama.
    Returns { keywords: list[str], summary: str }
    """
    import re as _re

    cv_text = ""
    if file is not None:
        raw_bytes = await file.read()
        # Try PDF extraction first, fall back to plain text
        try:
            import io
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw_bytes))
            cv_text = "\n".join(p.extract_text() or "" for p in reader.pages)
        except Exception:
            cv_text = raw_bytes.decode("utf-8", errors="ignore")
    elif text:
        cv_text = text

    if not cv_text.strip():
        return JSONResponse({"error": "No CV content provided."}, status_code=400)

    snippet = cv_text[:4000]
    prompt = (
        "Extract the top technical skills, tools, programming languages, frameworks, and "
        "domain expertise from this CV. Return ONLY a JSON object with two keys:\n"
        '  "keywords": an array of 15-30 concise skill strings (e.g. "Python", "FastAPI", "SQL")\n'
        '  "summary": one sentence describing the candidate\'s profile\n'
        "Do not include soft skills like 'communication' or 'teamwork'.\n\n"
        f"CV:\n{snippet}"
    )

    _model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    _host  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    client = _ollama.AsyncClient(host=_host)

    try:
        raw_chunks: list[str] = []
        async for chunk in await client.chat(
            model=_model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            think=False,
            options={"num_predict": 800},
        ):
            piece = (chunk.message.content or "") if chunk.message else ""
            if piece:
                raw_chunks.append(piece)

        raw = "".join(raw_chunks)
        # Strip <think> blocks in case the model still emits them
        raw = _re.sub(r"<think>.*?</think>", "", raw, flags=_re.DOTALL).strip()
        # Find the outermost JSON object
        m = _re.search(r"\{.*\}", raw, _re.DOTALL)
        if m:
            import json as _json
            data = _json.loads(m.group())
            return {
                "keywords": data.get("keywords", []),
                "summary": data.get("summary", ""),
            }
        return JSONResponse({"error": f"No JSON found in model output: {raw[:200]}"}, status_code=500)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


# ---------------------------------------------------------------------------
# Resume tailoring agent
# ---------------------------------------------------------------------------

@app.get("/resume/tools", tags=["resume"])
def list_resume_tools():
    return {
        "tools": [
            {"name": t["function"]["name"], "description": t["function"]["description"]}
            for t in RESUME_TOOL_DEFINITIONS
        ]
    }


@app.get("/resume/config", tags=["resume"])
def resume_config():
    return {
        "cv_pdf_path": os.getenv("CV_PDF_PATH", "cv.pdf"),
        "overleaf_tex_path": os.getenv("OVERLEAF_TEX_PATH", "cv.tex"),
    }


@app.get("/resume/versions", tags=["resume"])
async def list_resume_versions():
    tracker = CVVersionTracker()
    versions = await tracker.list_versions()
    return {"versions": versions}


@app.websocket("/resume/chat")
async def resume_chat_ws(websocket: WebSocket):
    await websocket.accept()
    session_ctx: list[dict] = []
    try:
        while True:
            data = await websocket.receive_json()
            req = ChatRequest(**data)
            messages = [m.model_dump() for m in req.messages]

            if not messages:
                await websocket.send_json({"type": "error", "message": "messages must not be empty"})
                continue

            async for event in run_resume_agent_stream(
                messages,
                system_prompt=req.system_prompt,
                session_ctx=session_ctx,
            ):
                await websocket.send_json(event)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@app.websocket("/resume/cover-letter")
async def cover_letter_ws(websocket: WebSocket):
    await websocket.accept()
    session_ctx: list[dict] = []
    try:
        while True:
            data = await websocket.receive_json()
            job_context = data.get("job_context", "")
            req = ChatRequest(**{k: v for k, v in data.items() if k != "job_context"})
            messages = [m.model_dump() for m in req.messages]

            if not messages:
                await websocket.send_json({"type": "error", "message": "messages must not be empty"})
                continue

            async for event in run_cover_letter_stream(messages, job_context, session_ctx):
                await websocket.send_json(event)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# SPA static files — must come last so API routes take precedence
# ---------------------------------------------------------------------------

_DIST = os.path.join(os.path.dirname(__file__), "frontend", "dist")

if os.path.isdir(_DIST):
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="spa")
else:
    @app.get("/", include_in_schema=False)
    def serve_placeholder():
        return JSONResponse(
            {"message": "Frontend not built yet. Run: cd frontend && npm run build"},
            status_code=503,
        )
