"""FastAPI app: replays a synthetic match as SSE with per-viewer personalised overlays.

    uvicorn itg.server:app --reload --app-dir src
"""
from __future__ import annotations

import asyncio
import json
import pathlib
from typing import Dict, Optional, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .agents import MatchPipeline
from .bus import Broadcaster, make_source
from .generator import DEFAULT_MATCH, MATCHES, MatchSpec, generate_match
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
_live: Dict[Tuple[str, int], Broadcaster] = {}
_caches: Dict[Tuple[str, int], dict] = {}  # narration cache per (match, seed), shared by all viewers


def _spec(match: str) -> MatchSpec:
    if match not in MATCHES:
        raise HTTPException(404, f"unknown match '{match}'")
    return MATCHES[match]


def _pipeline(spec: MatchSpec, seed: int) -> MatchPipeline:
    return MatchPipeline({c: v["name"] for c, v in spec.teams.items()}, _llm, _caches.setdefault((spec.id, seed), {}), _runner,
                         rosters={c: [n for n, _ in v["players"]] for c, v in spec.teams.items()})


def _roster(spec: MatchSpec):
    return {c: {"name": v["name"], "players": [n for n, _ in v["players"]],
                "slots": [list(o) for o, _ in v["slots"]],
                "staff": {"coach": v["staff"]["coach"], "assistants": v["staff"]["assistants"],
                          "subs": [{"name": n, "pos": p, "number": k} for n, p, k in v["staff"]["subs"]]}}
            for c, v in spec.teams.items()}


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


@app.get("/api/matches")
def matches():
    return [{"id": m.id, "title": m.title, "subtitle": m.subtitle, "blurb": m.blurb,
             "duration_min": round(m.duration / 60), "scripted": m.scenario is not None,
             "teams": [{"code": c, "name": v["name"]} for c, v in m.teams.items()]} for m in MATCHES.values()]


@app.get("/api/config")
def config(match: str = DEFAULT_MATCH):
    return {
        "llm": _llm.name, "orchestration": "agent-framework" if _runner else "plain",
        "languages": LANGUAGES,
        "match": {"id": _spec(match).id, "title": _spec(match).title, "subtitle": _spec(match).subtitle},
        "teams": _roster(_spec(match)),
    }


@app.get("/api/match")
def match_events(seed: int = 7, match: str = DEFAULT_MATCH):
    """Raw synthetic events (the 'data innovation' output), machine-readable."""
    return [e.to_dict() for e in generate_match(seed, match=_spec(match).id)]


@app.get("/api/stream")
async def stream(seed: int = 7, speed: float = 60.0, lang: str = "en", mode: str = "casual",
                 team: Optional[str] = None, player: Optional[str] = None,
                 metric: Optional[str] = None, match: str = DEFAULT_MATCH):
    profile = Profile(mode=mode if mode in ("casual", "analyst") else "casual", lang=lang,
                      team=team or None, player=player or None, metric=metric or None)
    spec = _spec(match)
    events = generate_match(seed, match=spec.id)
    pipe = _pipeline(spec, seed)

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
               metric: Optional[str] = None, match: str = DEFAULT_MATCH):
    """Event-driven path: viewers subscribe to the shared ingest bus (in-memory or Event Hubs)."""
    profile = Profile(mode=mode if mode in ("casual", "analyst") else "casual", lang=lang,
                      team=team or None, player=player or None, metric=metric or None)
    spec = _spec(match)
    key = (spec.id, seed)
    if key not in _live or _live[key].task.done() and not _live[key].history:
        _live[key] = Broadcaster(make_source(seed, speed, spec.id))
    bc = _live[key]
    pipe = _pipeline(spec, seed)
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
