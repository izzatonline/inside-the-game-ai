"""Multi-agent trace demo: handoffs between agents, and recovery from bad / failing models.

    PYTHONPATH=src python -m itg.demo --seed 3          # offline, or live Foundry if env is set
"""
import argparse
import asyncio

from .generator import TEAMS, generate_match
from .llm import get_llm
from .maf import Job, MafRunner
from .models import Profile
from .state import MatchState


class DownLLM:
    """Simulates a model outage."""
    name, available = "outage", True

    def complete(self, system, user, max_tokens=250):
        return None


class HallucinatingLLM:
    """Returns fluent text with invented numbers: the FactChecker must catch it."""
    name, available = "hallucinating", True

    def complete(self, system, user, max_tokens=250):
        out = ('{"headline": "Unreal strike", "body": "A 142 km/h rocket from a 97% chance!"}'
               if "JSON" in system else
               "This was the 9th goal of the season and the biggest comeback since 1987.")
        print(f"  [model said] {out}")
        return out


async def trace(runner: MafRunner, job: Job, label: str) -> None:
    print(f"\n=== {label} ===")
    result = await runner._workflow().run(job)
    for ev in result:
        if ev.type in ("executor_invoked", "executor_completed"):
            print(f"  {ev.type:<19} {ev.executor_id}")
    out = result.get_outputs()[0]
    print(f"  -> source={out.source} verified={out.verified}")
    print(f"  headline: {out.headline}\n  body:     {out.body}\n  why:      {out.why}")


async def main(seed: int) -> None:
    state = MatchState({c: v["name"] for c, v in TEAMS.items()})
    goal = next(m for e in generate_match(seed) for m in state.ingest(e) if m.kind == "goal")
    profile = Profile(mode="analyst")
    print(f"Moment: {goal.kind} {goal.id} at {goal.minute}' ({goal.facts['player']})")
    await trace(MafRunner(get_llm()), Job(goal, profile), "1. Normal run (configured backend)")
    await trace(MafRunner(DownLLM()), Job(goal, profile), "2. Model outage -> template fallback")
    await trace(MafRunner(HallucinatingLLM()), Job(goal, profile),
                "3. Hallucinated numbers -> rejected, grounded fallback")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=3)
    asyncio.run(main(ap.parse_args().seed))
