"""Microsoft Agent Framework wiring (Python 3.10+, `pip install agent-framework`).

* `FoundryLLM`  - LLM backend: each prompt becomes an `agent_framework.Agent` on a
                  `FoundryChatClient` (Microsoft Foundry project + model deployment).
* `MafRunner`   - runs Explainer -> Narrator -> FactChecker as an Agent Framework
                  `Workflow` (Executors + edges). Offline it uses template fallbacks, so the
                  workflow itself is testable without credentials.

No `from __future__ import annotations` here: Agent Framework inspects handler type hints.
"""
import asyncio
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler
from typing_extensions import Never

from .agents import (ExplainerAgent, FactChecker, NarratorAgent, TacticalAnalystAgent, _fmt, _template_key,
                     _tmpl, tactical_facts)
from .models import Moment, Profile

log = logging.getLogger("itg.maf")
_loop: Optional[asyncio.AbstractEventLoop] = None
_lock = threading.Lock()


def _bg_loop() -> asyncio.AbstractEventLoop:
    """One long-lived event loop shared by all Foundry clients and workflow runs."""
    global _loop
    with _lock:
        if _loop is None:
            _loop = asyncio.new_event_loop()
            threading.Thread(target=_loop.run_forever, daemon=True, name="itg-maf-loop").start()
        return _loop


class FoundryLLM:
    name = "foundry"
    available = True

    def __init__(self, client: Any = None) -> None:
        if client is None:
            from agent_framework_foundry import FoundryChatClient
            from azure.identity import DefaultAzureCredential

            client = FoundryChatClient(
                project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
                model=os.environ["FOUNDRY_MODEL"],
                credential=DefaultAzureCredential(),
            )
        self.client = client
        self._agents: Dict[str, Any] = {}

    def complete(self, system: str, user: str, max_tokens: int = 250) -> Optional[str]:
        """Sync facade (callers run in worker threads); the model call runs on the shared loop."""
        from agent_framework import Agent

        try:
            agent = self._agents.get(system)
            if agent is None:
                agent = self._agents[system] = Agent(self.client, instructions=system,
                                                     name="itg-" + str(len(self._agents)))
            fut = asyncio.run_coroutine_threadsafe(agent.run(user), _bg_loop())
            return (fut.result(timeout=15).text or "").strip() or None
        except Exception as exc:  # noqa: BLE001 - degrade to templates, never break the stream
            log.warning("Foundry call failed, using template fallback: %s", exc)
            return None


@dataclass
class Job:
    moment: Moment
    profile: Profile
    why: str = ""
    headline: str = ""
    body: str = ""
    source: str = "template"
    verified: bool = False


class ExplainerExecutor(Executor):
    def __init__(self, agent: ExplainerAgent) -> None:
        super().__init__(id="explainer")
        self.agent = agent

    @handler
    async def run(self, job: Job, ctx: WorkflowContext[Job]) -> None:
        job.why, job.source = await asyncio.to_thread(self.agent.run, job.moment, job.profile.lang)
        await ctx.send_message(job)


class NarratorExecutor(Executor):
    def __init__(self, agent: NarratorAgent) -> None:
        super().__init__(id="narrator")
        self.agent = agent

    @handler
    async def run(self, job: Job, ctx: WorkflowContext[Job]) -> None:
        job.headline, job.body, src = await asyncio.to_thread(self.agent.run, job.moment, job.profile)
        if src == "llm":
            job.source = "llm"
        await ctx.send_message(job)


class FactCheckExecutor(Executor):
    """Final gate: anything not grounded in the moment's facts is replaced by the template."""

    def __init__(self) -> None:
        super().__init__(id="fact_checker")

    @handler
    async def run(self, job: Job, ctx: WorkflowContext[Never, Job]) -> None:
        text = f"{job.headline} {job.body} {job.why}"
        job.verified = FactChecker().run(text, job.moment.facts)
        if not job.verified:
            h, b, w = _tmpl(job.profile.lang, _template_key(job.moment))
            job.headline, job.body = _fmt(h, job.moment.facts), _fmt(b, job.moment.facts)
            job.why, job.source, job.verified = _fmt(w, job.moment.facts), "template", True
        await ctx.yield_output(job)


@dataclass
class TacticsJob:
    team: Dict[str, Any]
    opp: Dict[str, Any]
    lang: str
    mode: str
    summary: str = ""
    options: List[Dict[str, str]] = field(default_factory=list)
    source: str = "template"
    verified: bool = False


class TacticalAnalystExecutor(Executor):
    def __init__(self, agent: TacticalAnalystAgent) -> None:
        super().__init__(id="tactical_analyst")
        self.agent = agent

    @handler
    async def run(self, job: TacticsJob, ctx: WorkflowContext[TacticsJob]) -> None:
        job.summary, job.options, job.source = await asyncio.to_thread(
            self.agent.run, job.team, job.opp, job.lang, job.mode)
        await ctx.send_message(job)


class TacticsGuardExecutor(Executor):
    """Independent second check on the analyst's output; ungrounded text is replaced by the template."""

    def __init__(self, agent: TacticalAnalystAgent) -> None:
        super().__init__(id="tactics_guard")
        self.agent = agent

    @handler
    async def run(self, job: TacticsJob, ctx: WorkflowContext[Never, TacticsJob]) -> None:
        text = job.summary + " " + " ".join(o["title"] + " " + o["detail"] for o in job.options)
        job.verified = FactChecker().run(text, tactical_facts(job.team, job.opp))
        if not job.verified:
            job.summary, job.options, job.source = self.agent.fallback(job.team, job.lang)
            job.verified = True
        await ctx.yield_output(job)


class MafRunner:
    def __init__(self, llm: Any) -> None:
        self.explainer, self.narrator = ExplainerAgent(llm), NarratorAgent(llm)
        self.tactician = TacticalAnalystAgent(llm)

    def _workflow(self):
        # Fresh instance per run: a built Workflow holds run state, viewers run concurrently.
        ex, nar, chk = ExplainerExecutor(self.explainer), NarratorExecutor(self.narrator), FactCheckExecutor()
        return WorkflowBuilder(start_executor=ex).add_edge(ex, nar).add_edge(nar, chk).build()

    async def _run(self, job: Job) -> Job:
        return (await self._workflow().run(job)).get_outputs()[0]

    def run(self, moment: Moment, profile: Profile) -> Job:
        fut = asyncio.run_coroutine_threadsafe(self._run(Job(moment, profile)), _bg_loop())
        return fut.result(timeout=60)

    def _tactics_workflow(self):
        an, guard = TacticalAnalystExecutor(self.tactician), TacticsGuardExecutor(self.tactician)
        return WorkflowBuilder(start_executor=an).add_edge(an, guard).build()

    async def _run_tactics(self, job: TacticsJob) -> TacticsJob:
        return (await self._tactics_workflow().run(job)).get_outputs()[0]

    def run_tactics(self, team: Dict[str, Any], opp: Dict[str, Any], profile: Profile) -> TacticsJob:
        fut = asyncio.run_coroutine_threadsafe(
            self._run_tactics(TacticsJob(team, opp, profile.lang, profile.mode)), _bg_loop())
        return fut.result(timeout=60)
