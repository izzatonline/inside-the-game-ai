"""Evaluate the agent newsroom against a live model and write docs/evaluation.md (+ .json).

For each run (match, language, viewer mode) every moment goes through the real workflow
(Explainer -> Narrator -> FactChecker -> back for a rewrite if needed -> Editor) and we record:
first-pass approval, approval after a rewrite, template fallbacks, model failures, model calls,
time from moment to verified card, and an independent re-check that no aired number is ungrounded.

    set -a; . ./.env; set +a
    PYTHONPATH=src .venv311/bin/python scripts/eval_agents.py
"""
from __future__ import annotations

import json
import pathlib
import statistics
import sys
import time

from itg.agents import FactChecker, MatchPipeline, meaning_problems
from itg.generator import MATCHES, generate_match
from itg.llm import get_llm
from itg.models import Profile

RUNS = [("redcrest", "en", "analyst"), ("coastal", "en", "analyst"), ("riverside", "es", "analyst"), ("redcrest", "fr", "casual")]
SEED = 7


class Counting:
    """Wraps the model client to count calls, failures and time spent in the model."""

    def __init__(self, llm) -> None:
        self.llm, self.calls, self.failures, self.seconds = llm, 0, 0, 0.0
        self.name, self.available = llm.name, llm.available
        self.deployment = getattr(llm, "deployment", "")

    def complete(self, system: str, user: str, max_tokens: int = 250):
        t0 = time.perf_counter()
        out = self.llm.complete(system, user, max_tokens)
        self.seconds += time.perf_counter() - t0
        self.calls += 1
        self.failures += out is None
        return out


def main() -> None:
    base = get_llm()
    if not base.available:
        sys.exit("No model configured: load .env first (see the docstring).")
    try:
        from itg.maf import MafRunner
    except Exception:  # noqa: BLE001
        MafRunner = None  # noqa: N806
    rows, per_run = [], []
    for match, lang, mode in RUNS:
        llm = Counting(base)
        spec = MATCHES[match]
        pipe = MatchPipeline({c: v["name"] for c, v in spec.teams.items()}, llm, {},
                             MafRunner(llm) if MafRunner else None,
                             rosters={c: [n for n, _ in v["players"]] for c, v in spec.teams.items()})
        prof = Profile(mode=mode, lang=lang)
        n0 = len(rows)
        for e in generate_match(SEED, match=match):
            t0 = time.perf_counter()
            for ov in pipe.process(e, prof):
                c = ov.check
                trace = c["trace"]
                sent_back = sum(1 for s in trace if s["agent"] == "FactChecker" and "sent" in s["action"])
                grounded = ov.source != "llm" or FactChecker().run(f"{ov.headline} {ov.body} {ov.why}", ov.facts)
                moment = next(mm for mm, o in pipe.shown if o is ov)
                sense = meaning_problems(moment, lang, ov.headline, ov.body) if ov.source == "llm" else []
                rows.append({"match": match, "lang": lang, "mode": mode, "kind": ov.kind, "source": ov.source,
                             "sent_back": sent_back, "model_retry": any(s["note"] == "model retried once" for s in trace),
                             "model_down": any(s["note"].startswith("model unavailable") for s in trace),
                             "seconds": round(time.perf_counter() - t0, 2), "grounded": grounded,
                             "meaning_ok": not sense, "headline": ov.headline, "body": ov.body})
            print(f"\r{match}/{lang}/{mode}: {len(rows) - n0} cards", end="", flush=True)
        print()
        per_run.append({"run": f"{match} / {lang} / {mode}", "cards": len(rows) - n0, "calls": llm.calls,
                        "failures": llm.failures, "model_s": round(llm.seconds, 1)})

    ai = [r for r in rows if r["source"] == "llm"]
    lat = sorted(r["seconds"] for r in rows)
    summary = {
        "model": getattr(base, "deployment", "") or base.name, "orchestration": "agent-framework" if MafRunner else "plain",
        "seed": SEED, "cards": len(rows),
        "ai_written_pct": round(100 * len(ai) / len(rows), 1),
        "first_pass_pct": round(100 * sum(1 for r in rows if r["source"] == "llm" and not r["sent_back"]) / len(rows), 1),
        "fixed_after_rewrite_pct": round(100 * sum(1 for r in rows if r["source"] == "llm" and r["sent_back"]) / len(rows), 1),
        "template_fallback_pct": round(100 * (len(rows) - len(ai)) / len(rows), 1),
        "cards_with_a_rewrite": sum(1 for r in rows if r["sent_back"]),
        "model_retries": sum(1 for r in rows if r["model_retry"]),
        "ungrounded_numbers_aired": sum(1 for r in rows if not r["grounded"]),
        "goal_cards": sum(1 for r in rows if r["kind"] == "goal"),
        "goal_meaning_errors_aired": sum(1 for r in rows if not r["meaning_ok"]),
        "median_s": round(statistics.median(lat), 1), "p90_s": round(lat[int(len(lat) * 0.9)], 1),
        "runs": per_run,
    }
    out = pathlib.Path("docs")
    out.mkdir(exist_ok=True)
    (out / "evaluation.json").write_text(json.dumps({"summary": summary, "cards": rows}, indent=1, ensure_ascii=False))
    s = summary
    md = [
        "# Agent evaluation",
        "",
        f"Model `{s['model']}` on Microsoft Foundry, {s['orchestration']} workflow, synthetic matches (seed {s['seed']}). "
        f"Generated by `scripts/eval_agents.py`; raw results in `evaluation.json`.",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Cards produced | {s['cards']} |",
        f"| Written by the AI and approved first time | {s['first_pass_pct']}% |",
        f"| Written by the AI, approved after the FactChecker sent it back | {s['fixed_after_rewrite_pct']}% |",
        f"| Fell back to grounded template wording | {s['template_fallback_pct']}% |",
        f"| Model calls retried after a failed or unusable reply | {s['model_retries']} |",
        f"| Aired cards with a number not in the facts (independent re-check) | {s['ungrounded_numbers_aired']} |",
        f"| Aired goal cards that read as a miss, a wrong score state or a wrong own-goal team (of {s['goal_cards']}) | {s['goal_meaning_errors_aired']} |",
        f"| Moment to verified card, median / 90th percentile | {s['median_s']} s / {s['p90_s']} s |",
        "",
        "| Run (match / language / mode) | Cards | Model calls | Failed calls | Time in model |",
        "|---|---|---|---|---|",
        *[f"| {r['run']} | {r['cards']} | {r['calls']} | {r['failures']} | {r['model_s']} s |" for r in per_run],
        "",
        "The FactChecker verifies every number against the moment's facts, and for goals also checks the meaning "
        "(a goal reads as a goal, level only when level, own goals name the right team) in en/es/ms/fr/pt. "
        "It does not judge football opinions.",
    ]
    (out / "evaluation.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
