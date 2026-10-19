"""FastAPI app: replays a synthetic match as SSE with per-viewer personalised overlays.

    uvicorn itg.server:app --reload --app-dir src
"""
from __future__ import annotations

import asyncio
import json
import pathlib
from typing import Dict, Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .agents import MatchPipeline
from .bus import Broadcaster, make_source
from .generator import TEAMS, generate_match
from .llm import get_llm
from .models import Profile
from .templates import LANGUAGES

STATIC = pathlib.Path(__file__).parent / "static"  # built by `npm run build` in frontend/
app = FastAPI(title="Inside the Game")
_llm = get_llm()
try:  # Agent Framework workflow when installed (Python 3.10+); plain agents otherwise
    from .maf import MafRunner

    _runner = MafRunner(_llm)
except ImportError:
    _runner = None
_live: Dict[int, Broadcaster] = {}
_caches: Dict[int, dict] = {}  # narration cache per match seed, shared by all viewers


def _roster():
    return {c: {"name": v["name"], "players": [n for n, _ in v["players"]],
                "slots": [list(o) for o, _ in v["slots"]],
                "staff": {"coach": v["staff"]["coach"], "assistants": v["staff"]["assistants"],
                          "subs": [{"name": n, "pos": p, "number": k} for n, p, k in v["staff"]["subs"]]}}
            for c, v in TEAMS.items()}


async def _step(pipe, ev, profile, last_stats: float):
    """Process one event; return (sse chunks, new last_stats)."""
    out = []
    overlays = await asyncio.to_thread(pipe.process, ev, profile)
    if ev.type == "tracking":
        out.append(_sse("frame", {k: ev.meta[k] for k in ("pos", "ball", "poss", "holder", "conf", "phase", "phase_conf")}
                        | {"t": ev.t}))
    if ev.type in ("warmup", "substitution"):
        out.append(_sse("bench", ev.to_dict()))
    tac = pipe.state.tactics.take_update()
    if tac:
        tac = await asyncio.to_thread(pipe.localize_tactics, tac, profile, ev.t)
        out.append(_sse("tactics", tac))
    if ev.type != "tracking" and (ev.t - last_stats >= 10 or overlays or ev.type == "fulltime"):
        last_stats = ev.t
        out.append(_sse("stats", pipe.state.snapshot()))
    out.extend(_sse("overlay", ov.to_dict()) for ov in overlays)
    return out, last_stats


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


if (STATIC / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")


@app.get("/favicon.svg")
def favicon():
    return FileResponse(STATIC / "favicon.svg")


@app.get("/")
def index():
    page = STATIC / "index.html"
    if not page.exists():
        return HTMLResponse("<p>UI not built. Run: <code>cd frontend && npm install --legacy-peer-deps && npm run build</code></p>")
    return FileResponse(page)


@app.get("/api/config")
def config():
    return {
        "llm": _llm.name, "orchestration": "agent-framework" if _runner else "plain",
        "languages": LANGUAGES,
        "teams": _roster(),
    }


@app.get("/api/match")
def match(seed: int = 7):
    """Raw synthetic events (the 'data innovation' output), machine-readable."""
    return [e.to_dict() for e in generate_match(seed)]


@app.get("/api/stream")
async def stream(seed: int = 7, speed: float = 60.0, lang: str = "en", mode: str = "casual",
                 team: Optional[str] = None, player: Optional[str] = None,
                 metric: Optional[str] = None):
    profile = Profile(mode=mode if mode in ("casual", "analyst") else "casual", lang=lang,
                      team=team or None, player=player or None, metric=metric or None)
    events = generate_match(seed)
    pipe = MatchPipeline({c: v["name"] for c, v in TEAMS.items()}, _llm,
                         _caches.setdefault(seed, {}), _runner)

    async def gen():
        prev_t, last_stats = 0.0, -99.0
        for ev in events:
            await asyncio.sleep(max(0.0, min(ev.t - prev_t, 60)) / max(speed, 1))
            prev_t = ev.t
            chunks, last_stats = await _step(pipe, ev, profile, last_stats)
            for c in chunks:
                yield c
        yield _sse("recap", await asyncio.to_thread(pipe.recap, profile))

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@app.get("/api/live")
async def live(seed: int = 7, speed: float = 60.0, lang: str = "en", mode: str = "casual",
               team: Optional[str] = None, player: Optional[str] = None,
               metric: Optional[str] = None):
    """Event-driven path: viewers subscribe to the shared ingest bus (in-memory or Event Hubs)."""
    profile = Profile(mode=mode if mode in ("casual", "analyst") else "casual", lang=lang,
                      team=team or None, player=player or None, metric=metric or None)
    if seed not in _live or _live[seed].task.done() and not _live[seed].history:
        _live[seed] = Broadcaster(make_source(seed, speed))
    bc = _live[seed]
    pipe = MatchPipeline({c: v["name"] for c, v in TEAMS.items()}, _llm,
                         _caches.setdefault(seed, {}), _runner)
    history, q = bc.subscribe()
    catchup = []
    for ev in history:  # catch-up: rebuild state silently
        pipe.state.ingest(ev)
        if ev.type in ("warmup", "substitution"):
            catchup.append(_sse("bench", ev.to_dict()))

    async def gen():
        last_stats = -99.0
        try:
            for chunk in catchup:
                yield chunk
            if history:
                yield _sse("stats", pipe.state.snapshot())
                tac = pipe.state.tactics.take_update()
                if tac:
                    yield _sse("tactics", tac)
            while True:
                ev = await q.get()
                if ev is None:
                    break
                chunks, last_stats = await _step(pipe, ev, profile, last_stats)
                for c in chunks:
                    yield c
            yield _sse("recap", await asyncio.to_thread(pipe.recap, profile))
        finally:
            bc.unsubscribe(q)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})
