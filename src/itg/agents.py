"""Agent roles. Each is a small class with a single `run(...)` so it can be wrapped as a
Microsoft Agent Framework agent / workflow executor (see README) without changing logic.

Roles: Personalizer (relevance) -> Explainer (why it matters) -> Narrator (words)
       -> FactChecker (grounding guard) ; RecapAgent writes the full-time story.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from .llm import get_llm
from .models import Moment, Overlay, Profile
from .state import MatchState
from .tactics import FEATURED
from .templates import CHIPS, LANGUAGES, RECAP, T, TACTIC_SUMMARY

_NUM = re.compile(r"\d+(?:\.\d+)?")


def _numbers(obj: Any) -> List[float]:
    if isinstance(obj, bool) or obj is None:
        return []
    if isinstance(obj, (int, float)):
        return [float(obj)]
    if isinstance(obj, str):
        return [float(n) for n in _NUM.findall(obj)]
    if isinstance(obj, dict):
        return [n for v in obj.values() for n in _numbers(v)]
    if isinstance(obj, (list, tuple)):
        return [n for v in obj for n in _numbers(v)]
    return []


class FactChecker:
    """Rejects generated text containing numbers that are not in the source facts."""

    def run(self, text: str, facts: Dict[str, Any]) -> bool:
        allowed = _numbers(facts)
        for n in _NUM.findall(text):
            v = float(n)
            if not any(abs(v - a) <= 0.051 or abs(v / 100 - a) <= 0.0051 for a in allowed):
                return False
        return True


class PersonalizerAgent:
    """Decides whether a moment is worth showing *this* viewer, and which chips to attach."""

    METRIC_KINDS = {
        "speed": {"sprint", "goal", "big_chance"},
        "passing": {"difficult_pass", "milestone", "goal"},
        "xg": {"goal", "big_chance", "momentum_swing"},
    }

    def relevant(self, m: Moment, p: Profile) -> bool:
        if p.player:
            return m.player == p.player or m.kind == "goal"
        if p.metric in self.METRIC_KINDS:
            return m.kind in self.METRIC_KINDS[p.metric]
        threshold = 0.6 if p.mode == "casual" else 0.3
        if p.team and m.team != p.team:
            threshold = max(threshold, 0.95)  # only goals against your club
        return m.importance >= threshold

    def chips(self, m: Moment, p: Profile) -> List[Dict[str, str]]:
        if p.mode != "analyst":
            return []
        out = []
        for label, key, suffix in CHIPS.get(m.kind, []):
            if key in m.facts:
                out.append({"label": label, "value": f"{m.facts[key]}{suffix}"})
        return out


def _template_key(m: Moment) -> str:
    return "goal_against_run" if m.kind == "goal" and m.facts.get("against_run") else m.kind


def _fmt(s: str, facts: Dict[str, Any]) -> str:
    return s.format_map({k: ("" if v is None else v) for k, v in facts.items()})


def _tmpl(lang: str, key: str) -> Tuple[str, str, str]:
    return T.get(lang, T["en"])[key]


class ExplainerAgent:
    SYSTEM = ("You are a football analyst. In ONE sentence explain why this moment matters "
              "(momentum, control vs chaos, tactical pressure, rhythm). Use ONLY facts given; "
              "never invent numbers, names or events. Write in {language}. Plain text only.")

    def __init__(self, llm) -> None:
        self.llm = llm

    def run(self, m: Moment, lang: str) -> Tuple[str, str]:
        text = self.llm.complete(self.SYSTEM.format(language=LANGUAGES.get(lang, lang)),
                                 json.dumps({"kind": m.kind, "facts": m.facts}), 120)
        if text and FactChecker().run(text, m.facts):
            return text, "llm"
        return _fmt(_tmpl(lang, _template_key(m))[2], m.facts), "template"


class NarratorAgent:
    SYSTEM = ("You are a broadcast commentator writing a short on-screen caption. Return JSON "
              '{{"headline": "<=6 words", "body": "<=25 words"}}. Tone: {tone}. Language: {language}. '
              "Use ONLY the facts provided; never invent numbers, names or events.")

    def __init__(self, llm) -> None:
        self.llm = llm

    def run(self, m: Moment, p: Profile) -> Tuple[str, str, str]:
        tone = ("energetic, plain words for a casual fan" if p.mode == "casual"
                else "precise and tactical, for an analyst")
        raw = self.llm.complete(self.SYSTEM.format(tone=tone, language=LANGUAGES.get(p.lang, p.lang)),
                                json.dumps({"kind": m.kind, "facts": m.facts}), 160)
        if raw:
            try:
                data = json.loads(re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip())
                h, b = str(data["headline"]), str(data["body"])
                if FactChecker().run(h + " " + b, m.facts):
                    return h, b, "llm"
            except (ValueError, KeyError, TypeError):
                pass
        h, b, _ = _tmpl(p.lang, _template_key(m))
        return _fmt(h, m.facts), _fmt(b, m.facts), "template"


class RecapAgent:
    SYSTEM = ("You are a match reporter. Write a 3-sentence full-time recap using ONLY the facts "
              "given. Language: {language}. Plain text.")

    def __init__(self, llm) -> None:
        self.llm = llm

    def run(self, state: MatchState, top: List[Tuple[Moment, Overlay]], p: Profile) -> Dict[str, Any]:
        snap = state.snapshot()["teams"]
        h, a = state.codes
        facts = {
            "scoreline": f"{snap[h]['name']} {snap[h]['goals']}-{snap[a]['goals']} {snap[a]['name']}",
            "poss_home": snap[h]["possession_pct"], "poss_away": snap[a]["possession_pct"],
            "shots_home": snap[h]["shots"], "shots_away": snap[a]["shots"],
            "xg_home": snap[h]["xg"], "xg_away": snap[a]["xg"],
            "key_moments": [{"minute": m.minute, "kind": m.kind, "player": m.player,
                             "team": m.facts["team_name"]} for m, _ in top],
        }
        text = self.llm.complete(self.SYSTEM.format(language=LANGUAGES.get(p.lang, p.lang)),
                                 json.dumps(facts), 300)
        source = "llm"
        if not text or not FactChecker().run(text, facts):
            head, body = RECAP.get(p.lang, RECAP["en"])
            text = _fmt(body, facts) + " " + " ".join(o.body for _, o in top)
            source = "template"
        return {"headline": _fmt(RECAP.get(p.lang, RECAP["en"])[0], facts), "body": text,
                "source": source, "stats": snap}



def tactical_facts(team: Dict[str, Any], opp: Dict[str, Any]) -> Dict[str, Any]:
    """The only data the Tactical Analyst may use (and the FactChecker verifies against)."""
    def compact(p: Dict[str, Any]) -> Dict[str, Any]:
        d = {k: p[k] for k in ("name", "formation", "line_height", "width_m", "hull_area", "ppda",
                               "long_pct", "wide_pct", "primary", "tags")}
        d["featured_roles"] = [{"name": r["name"], "role": r["role"], "x_in": r["x_in"]}
                               for r in p["roles"] if r["role"] in FEATURED]
        return d
    return {"team": compact(team), "opponent": compact(opp), "baseline_options": team.get("options", [])}


class TacticalAnalystAgent:
    SYSTEM = ("You are a football tactical analyst for a broadcast. Given JSON facts about one team and its "
              'opponent, return JSON {{"summary": "<=40 words: what this team is doing and how the opponent can '
              'respond", "options": [{{"title": "<=6 words", "detail": "<=30 words"}}]}} with at most 3 options, '
              "grounded in baseline_options. Tone: {tone}. Language: {language}. Use ONLY the facts; never invent "
              "numbers, names or events.")

    def __init__(self, llm) -> None:
        self.llm = llm

    def fallback(self, team: Dict[str, Any], lang: str) -> Tuple[str, List[Dict[str, str]], str]:
        tmpl = TACTIC_SUMMARY.get(lang, TACTIC_SUMMARY["en"])
        return _fmt(tmpl, team), list(team.get("options", [])), "template"

    def run(self, team: Dict[str, Any], opp: Dict[str, Any], lang: str, mode: str):
        facts = tactical_facts(team, opp)
        tone = "plain words for a casual fan" if mode == "casual" else "precise and tactical, for an analyst"
        raw = self.llm.complete(self.SYSTEM.format(tone=tone, language=LANGUAGES.get(lang, lang)),
                                json.dumps(facts, ensure_ascii=False), 450)
        if raw:
            try:
                data = json.loads(re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip())
                summary = str(data["summary"])
                options = [{"title": str(o["title"]), "detail": str(o["detail"])} for o in data["options"]][:3]
                text = summary + " " + " ".join(o["title"] + " " + o["detail"] for o in options)
                if FactChecker().run(text, facts):
                    return summary, options, "llm"
            except (ValueError, KeyError, TypeError):
                pass
        return self.fallback(team, lang)


class MatchPipeline:
    """Orchestrates the agents for one viewer. Interpretation is shared logic in MatchState."""

    def __init__(self, team_names: Dict[str, str], llm=None, cache: Optional[dict] = None,
                 runner=None) -> None:
        self.llm = llm or get_llm()
        self.runner = runner  # optional itg.maf.MafRunner: Explainer->Narrator->FactChecker workflow
        self.state = MatchState(team_names)
        self.personalizer = PersonalizerAgent()
        self.explainer = ExplainerAgent(self.llm)
        self.narrator = NarratorAgent(self.llm)
        self.recapper = RecapAgent(self.llm)
        self.tactician = TacticalAnalystAgent(self.llm)
        self.cache = cache if cache is not None else {}  # shared across viewers of the same match
        self.shown: List[Tuple[Moment, Overlay]] = []

    def process(self, event, profile: Profile) -> List[Overlay]:
        overlays = []
        for m in self.state.ingest(event):
            if not self.personalizer.relevant(m, profile):
                continue
            key = (m.id, profile.lang, profile.mode)
            if key not in self.cache:
                if self.runner:
                    job = self.runner.run(m, profile)
                    self.cache[key] = (job.why, job.headline, job.body, job.source)
                else:
                    why, s1 = self.explainer.run(m, profile.lang)
                    headline, body, s2 = self.narrator.run(m, profile)
                    self.cache[key] = (why, headline, body, "llm" if "llm" in (s1, s2) else "template")
            why, headline, body, source = self.cache[key]
            ov = Overlay(
                moment_id=m.id, t=m.t, minute=m.minute, kind=m.kind, team=m.team,
                importance=m.importance, headline=headline, body=body,
                why=why if profile.mode == "analyst" or m.importance >= 0.9 else "",
                chips=self.personalizer.chips(m, profile), lang=profile.lang, mode=profile.mode,
                source=source, verified=True, duration_s=8.0 if m.importance >= 0.9 else 5.0)
            self.shown.append((m, ov))
            overlays.append(ov)
        return overlays

    def localize_tactics(self, update: Dict[str, Any], profile: Profile, t: float) -> Dict[str, Any]:
        """Adds a localised, fact-checked summary + options to each team's tactical profile.
        Cached per team / 5-minute window / language / mode and shared across viewers."""
        out: Dict[str, Any] = {}
        for c, p in update.items():
            opp = next((v for k, v in update.items() if k != c), None)
            key = ("tac", c, p["formation"], p["primary"], int(t // 300), profile.lang, profile.mode)
            if key not in self.cache:
                if opp is None:
                    self.cache[key] = self.tactician.fallback(p, profile.lang)
                elif self.runner:
                    job = self.runner.run_tactics(p, opp, profile)
                    self.cache[key] = (job.summary, job.options, job.source)
                else:
                    self.cache[key] = self.tactician.run(p, opp, profile.lang, profile.mode)
            summary, options, source = self.cache[key]
            out[c] = dict(p, summary=summary, options=options, summary_source=source)
        return out

    def recap(self, profile: Profile) -> Dict[str, Any]:
        top = sorted(self.shown, key=lambda mo: -mo[0].importance)[:4]
        top.sort(key=lambda mo: mo[0].t)
        return self.recapper.run(self.state, top, profile)
