"""Agent roles. Each is a small class with a single `run(...)` so it can be wrapped as a
Microsoft Agent Framework agent / workflow executor (see README) without changing logic.

Roles: Personalizer (relevance) -> Explainer (why it matters) -> Narrator (words)
       -> FactChecker (grounding guard, sends rejected drafts back for a rewrite) -> Editor (how it airs);
       RecapAgent writes the full-time story.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .llm import get_llm
from .models import Moment, Overlay, Profile
from .state import MatchState
from .tactics import FEATURED
from .templates import CHIPS, LANGUAGES, RECAP, RECAP_NARRATIVE, T, TACTIC_SUMMARY

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


# Meaning check for goal captions, per language: a goal must read as a goal, not a miss; "level" only when level;
# an own goal must say so and must not put the player in the team that benefits. Other languages: numbers only.
_GOAL = {"en": r"\b(goals?|scores?|scored|nets?|netted|converts?|converted|finish(es|ed)?|strikes?|header|winner|equali[sz]\w*|own goal)\b",
         "es": r"\b(gol\w*|marca\w*|anota\w*|convierte\w*|define\w*|autogol)\b",
         "ms": r"\b(gol|jaring\w*|menjaring\w*|skor\w*)\b",
         "fr": r"\b(but|buts|marque\w*|égalis\w*)\b", "pt": r"\b(gol\w*|marca\w*|golo\w*)\b"}
_MISS = {"en": r"\b(miss(es|ed)?|chances?|wide|saved|over the bar|shoots? high|fires? (wide|over))\b",
         "es": r"\b(fall\w*|ocasi[oó]n|dispara alto|desv[ií]\w*|parad\w*|al palo)\b",
         "ms": r"\b(terlepas|peluang|tersasar)\b", "fr": r"\b(manqu\w*|occasion|raté\w*)\b",
         "pt": r"\b(perd\w*|chance|desperdi\w*)\b"}
_LEVEL = {"en": r"\b(level(s|led|ler)?|equali[sz]\w*|all square)\b", "es": r"\b(empat\w*|igual\w*)\b",
          "ms": r"\b(menyamakan|seri)\b", "fr": r"\b(égalis\w*)\b", "pt": r"\b(empat\w*|igual\w*)\b"}
_SCORED = {"en": r"\b(scores?|scored|nets?|netted|converts?|converted|slots?|wins? it|goal stands|goal for)\b",
           "es": r"\b(marca|marcó|anota\w*|convierte|gol de)\b", "ms": r"\b(menjaring|jaringkan|gol untuk)\b",
           "fr": r"\b(marque|inscrit|but pour)\b", "pt": r"\b(marca|marcou|converte\w*|gol de)\b"}
_REVIEW = {"en": r"\b(var|check\w*|review\w*)\b", "es": r"\b(var|revisi[oó]n|revisa\w*)\b", "ms": r"\b(var|semakan|semak)\b",
           "fr": r"\b(var|vérif\w*|examen)\b", "pt": r"\b(var|revis\w*)\b"}
_LEADS = {"en": r"(ahead|lead(s|ing)?|in front)", "es": r"(ventaja|delante|lidera\w*|adelanta\w*)",
          "ms": r"(mendahului|di hadapan)", "fr": r"(devant|mène|en tête)", "pt": r"(frente|lidera\w*|vantagem)"}
_AWARDED = {"en": r"\b(award\w*|given|gives|reversed|penali[sz]\w*|punish\w*|sanction\w*|book\w*|yellow|corner)\b",
            "es": r"\b(conced\w*|otorg\w*|revert\w*|sancion\w*|castig\w*|amarilla|c[oó]rner)\b",
            "ms": r"\b(diberi|dihukum|kad|sepakan sudut)\b", "fr": r"\b(accord\w*|sanction\w*|jaune|corner)\b",
            "pt": r"\b(concedid\w*|puni\w*|amarelo|escanteio)\b"}
_OWN = {"en": r"own goal|own net", "es": r"autogol|en propia", "ms": r"gol sendiri", "fr": r"contre son camp", "pt": r"gol contra|autogolo"}


def meaning_problems(m: Moment, lang: str, headline: str, body: str) -> List[str]:
    """What a goal caption gets wrong in meaning (empty list = fine). Numbers are the FactChecker's job."""
    f = m.facts
    words = re.findall(r"\w+", headline.lower())
    if words and max(words.count(w) for w in words) >= 3:
        return ["the headline repeats the same word; write a real headline"]
    if lang in _GOAL and m.kind.startswith("restart_late_") and re.search(_AWARDED[lang], f"{headline} {body}", re.I):
        return ["it says the referee awarded or punished something, but this is only a timing report: nothing was awarded"]
    if lang not in _GOAL or m.kind not in ("goal", "var"):
        return []
    text, head, out = f"{headline} {body}", headline, []
    if m.kind == "var":  # a check is not a decision, and an awarded penalty has not been scored yet
        vk = f.get("var_kind")
        if vk in ("goal_check", "penalty_check", "penalty_awarded", "no_goal") and re.search(_SCORED[lang], text, re.I):
            out.append(f"it says someone scored, but {f.get('decision', 'this is a VAR review')}")
        if vk in ("goal_check", "penalty_check") and not re.search(_REVIEW[lang], text, re.I):
            out.append("it must say that VAR is checking")
        return out
    if re.search(_LEADS[lang], text, re.I):
        lead, trail = f.get("leader"), f.get("trailer")
        if not lead:
            out.append("it says a team leads, but the score is level")
        elif trail and re.search(rf"\b{re.escape(trail.split()[0])}\b\W+(?:\S+\W+){{0,3}}?{_LEADS[lang]}", text, re.I):
            out.append(f"{lead} lead, not {trail}")
    if not re.search(_GOAL[lang], text, re.I):
        out.append("it must say that a goal was scored")
    if re.search(_MISS[lang], head, re.I):
        out.append("the headline describes a miss or a chance, but this was a goal")
    if re.search(_LEVEL[lang], text, re.I) and f.get("score_home") != f.get("score_away"):
        out.append("it says the score is level, but it is not")
    if f.get("own_goal"):
        if not re.search(_OWN[lang], text, re.I):
            out.append("it must say this was an own goal")
        if f"{m.player} ({f.get('scoring_team')}" in text or f"{m.player} of {f.get('scoring_team')}" in text:
            out.append(f"{m.player} plays for {f.get('player_team')}, not {f.get('scoring_team')}")
    return out


class FactChecker:
    """Rejects generated text containing numbers that are not in the source facts."""

    def audit(self, text: str, facts: Dict[str, Any]) -> Dict[str, Any]:
        """Every number in the text, and whether it appears in the facts (exactly, or as a percentage of one)."""
        allowed = _numbers(facts)
        found, missing = [], []
        for n in _NUM.findall(text):
            v = float(n)
            ok = any(abs(v - a) <= 0.051 or abs(v / 100 - a) <= 0.0051 for a in allowed)
            (found if ok else missing).append(n)
        return {"numbers": found + missing, "matched": found, "unmatched": missing}

    def run(self, text: str, facts: Dict[str, Any]) -> bool:
        return not self.audit(text, facts)["unmatched"]


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
    if m.kind == "goal" and m.facts.get("own_goal"):
        return "goal_own"
    if m.kind == "goal" and m.facts.get("penalty"):
        return "goal_penalty"
    if m.kind == "var":
        return "var_" + m.facts["var_kind"]
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

    def draft(self, m: Moment, lang: str, feedback: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """One model draft, unchecked. `feedback` carries a rejected draft and why it was rejected."""
        payload: Dict[str, Any] = {"kind": m.kind, "facts": m.facts}
        if feedback:
            payload["rejected_draft"] = feedback
        return self.llm.complete(self.SYSTEM.format(language=LANGUAGES.get(lang, lang)), json.dumps(payload), 120)

    def run(self, m: Moment, lang: str) -> Tuple[str, str]:
        text = self.draft(m, lang)
        if text and FactChecker().run(text, m.facts):
            return text, "llm"
        return _fmt(_tmpl(lang, _template_key(m))[2], m.facts), "template"


class NarratorAgent:
    SYSTEM = ("You are a broadcast commentator writing a short on-screen caption. Return JSON "
              '{{"headline": "<=6 words", "body": "<=25 words"}}. Tone: {tone}. Language: {language}. '
              "Use ONLY the facts provided; never invent numbers, names or events. "
              "For a goal: the headline says a goal was scored (never a chance, shot or miss); say level or equaliser "
              "only when score_home equals score_away; if own_goal is true, the player (of player_team) put the ball "
              "into their own net and scoring_team benefits.")

    def __init__(self, llm) -> None:
        self.llm = llm

    def draft(self, m: Moment, p: Profile, feedback: Optional[Dict[str, Any]] = None) -> Optional[Tuple[str, str]]:
        """One model draft (headline, body), unchecked; None if the model failed or returned bad JSON."""
        tone = ("energetic, plain words for a casual fan" if p.mode == "casual"
                else "precise and tactical, for an analyst")
        payload: Dict[str, Any] = {"kind": m.kind, "facts": m.facts}
        if feedback:
            payload["rejected_draft"] = feedback
        raw = self.llm.complete(self.SYSTEM.format(tone=tone, language=LANGUAGES.get(p.lang, p.lang)),
                                json.dumps(payload), 160)
        if raw:
            try:
                data = json.loads(re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip())
                return str(data["headline"]), str(data["body"])
            except (ValueError, KeyError, TypeError):
                pass
        return None

    def run(self, m: Moment, p: Profile) -> Tuple[str, str, str]:
        d = self.draft(m, p)
        if d and FactChecker().run(d[0] + " " + d[1], m.facts):
            return d[0], d[1], "llm"
        h, b, _ = _tmpl(p.lang, _template_key(m))
        return _fmt(h, m.facts), _fmt(b, m.facts), "template"


MAX_REWRITES = 2  # after the first draft, how many times the FactChecker may send a part back


@dataclass
class Job:
    """One moment moving through the newsroom: Explainer -> Narrator -> FactChecker (-> back for a rewrite) -> Editor."""
    moment: Moment
    profile: Profile
    why: str = ""
    headline: str = ""
    body: str = ""
    why_ai: bool = False
    cap_ai: bool = False
    redo: Set[str] = field(default_factory=lambda: {"why", "caption"})
    feedback: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    attempts: Dict[str, int] = field(default_factory=lambda: {"Explainer": 0, "Narrator": 0})
    trace: List[Dict[str, Any]] = field(default_factory=list)
    route: str = ""
    source: str = "template"
    slot: str = ""
    priority: int = 0
    duration_s: float = 5.0
    verified: bool = False

    def log(self, agent: str, action: str, ok: bool = True, note: str = "") -> None:
        self.trace.append({"agent": agent, "action": action, "ok": ok, "note": note})


def _with_retry(call):
    """Recovery: one immediate retry when a model call fails or returns nothing usable."""
    out = call()
    return (out, 1) if out else (call(), 2)


class Newsroom:
    """The steps of the review loop, shared by the plain-Python path and the Agent Framework workflow
    (each step is one executor there), so both produce the same result."""

    def __init__(self, explainer: "ExplainerAgent", narrator: "NarratorAgent") -> None:
        self.explainer, self.narrator = explainer, narrator

    def explain(self, job: Job) -> None:
        if "why" not in job.redo:
            return
        job.redo.discard("why")
        job.attempts["Explainer"] += 1
        fb = job.feedback.pop("why", None)
        text, calls = _with_retry(lambda: self.explainer.draft(job.moment, job.profile.lang, fb))
        if text:
            job.why, job.why_ai = text, True
            job.log("Explainer", "rewrote why it matters" if fb else "wrote why it matters", True,
                    "model retried once" if calls > 1 else "")
        else:
            job.why, job.why_ai = _fmt(_tmpl(job.profile.lang, _template_key(job.moment))[2], job.moment.facts), False
            job.log("Explainer", "used the template", False, "model unavailable after a retry")

    def narrate(self, job: Job) -> None:
        if "caption" not in job.redo:
            return
        job.redo.discard("caption")
        job.attempts["Narrator"] += 1
        fb = job.feedback.pop("caption", None)
        d, calls = _with_retry(lambda: self.narrator.draft(job.moment, job.profile, fb))
        if d:
            job.headline, job.body, job.cap_ai = d[0], d[1], True
            job.log("Narrator", "rewrote the caption" if fb else "wrote the caption", True,
                    "model retried once" if calls > 1 else "")
        else:
            h, b, _ = _tmpl(job.profile.lang, _template_key(job.moment))
            job.headline, job.body, job.cap_ai = _fmt(h, job.moment.facts), _fmt(b, job.moment.facts), False
            job.log("Narrator", "used the template", False, "model unavailable after a retry")

    def check(self, job: Job) -> None:
        """Approve, or send each failing part back to its writer with the numbers that broke the rule.
        After MAX_REWRITES the part falls back to the grounded template."""
        facts, fc = job.moment.facts, FactChecker()
        parts = [("why", "Explainer", job.why_ai, job.why), ("caption", "Narrator", job.cap_ai, f"{job.headline} {job.body}")]
        for part, writer, ai, text in parts:
            if not ai:
                continue
            bad = fc.audit(text, facts)["unmatched"]
            sense = meaning_problems(job.moment, job.profile.lang, job.headline, job.body) if part == "caption" else []
            if not bad and not sense:
                continue
            why_not = "; ".join((["numbers not in the facts: " + ", ".join(bad)] if bad else []) + sense)
            if job.attempts[writer] <= MAX_REWRITES:
                job.redo.add(part)
                job.feedback[part] = {"draft": text, "numbers_not_in_facts": bad, "meaning_problems": sense,
                                      "instruction": "Rewrite it. Use only numbers that appear in facts, and fix the meaning problems."}
                job.log("FactChecker", f"sent the {'why' if part == 'why' else 'caption'} back to the {writer}", False, why_not)
            else:
                h, b, w = _tmpl(job.profile.lang, _template_key(job.moment))
                if part == "why":
                    job.why, job.why_ai = _fmt(w, facts), False
                else:
                    job.headline, job.body, job.cap_ai = _fmt(h, facts), _fmt(b, facts), False
                job.log("FactChecker", f"rejected the {writer}'s last draft, template used", False, why_not)
        job.route = "rewrite" if job.redo else "edit"
        if job.route == "edit":
            job.verified = True
            if job.why_ai or job.cap_ai:
                job.log("FactChecker", "approved every number" + (" and the meaning" if job.moment.kind == "goal" else ""), True)

    def edit(self, job: Job) -> None:
        """Editor: decides how the verified card airs (screen slot, priority, time on screen)."""
        m = job.moment
        job.source = "llm" if (job.why_ai or job.cap_ai) else "template"
        big = m.kind in ("goal", "var") or m.importance >= 0.9
        job.slot = "full_width" if big else "lower_third" if m.importance >= 0.6 else "ticker"
        job.priority = 3 if big else 2 if m.importance >= 0.6 else 1
        words = len(f"{job.headline} {job.body}".split())
        job.duration_s = (8.0 if big else 5.0) + (2.0 if words > 22 else 0.0)
        job.log("Editor", f"aired it: {job.slot.replace('_', ' ')}, {job.duration_s:g} s", True)

    def run(self, moment: Moment, profile: Profile) -> Job:
        """The same loop without Agent Framework."""
        job = Job(moment, profile)
        while True:
            self.explain(job)
            self.narrate(job)
            self.check(job)
            if job.route == "edit":
                break
        self.edit(job)
        return job


class RecapAgent:
    SYSTEM = ("You are a match reporter. Write exactly 2 short sentences summarising the match for a general fan: "
              "the result and how it unfolded. Use ONLY the facts given; never invent numbers or names. "
              "Language: {language}. Plain text.")

    def __init__(self, llm) -> None:
        self.llm = llm

    @staticmethod
    def _narrative(facts: Dict[str, Any], lang: str) -> str:
        t = RECAP_NARRATIVE.get(lang, RECAP_NARRATIVE["en"])
        hs, as_ = facts["score_home"], facts["score_away"]
        if hs == as_:
            text = _fmt(t["draw"], {"home": facts["home"], "away": facts["away"], "hs": hs, "as": as_})
        else:
            win_home = hs > as_
            text = _fmt(t["win"], {"winner": facts["home"] if win_home else facts["away"],
                                   "loser": facts["away"] if win_home else facts["home"],
                                   "ws": max(hs, as_), "ls": min(hs, as_)})
            if facts["comeback"]:
                text += t["comeback"]
        xg_h, xg_a = facts["xg_home"], facts["xg_away"]
        poss_team = facts["home"] if facts["poss_home"] >= facts["poss_away"] else facts["away"]
        xg_team = facts["home"] if xg_h >= xg_a else facts["away"]
        text += _fmt(t["detail_same" if poss_team == xg_team else "detail"], {
            "poss_team": poss_team, "poss_pct": max(facts["poss_home"], facts["poss_away"]),
            "xg_team": xg_team, "xg_h": xg_h, "xg_a": xg_a})
        return text

    def run(self, state: MatchState, top: List[Tuple[Moment, Overlay]], p: Profile) -> Dict[str, Any]:
        snap = state.snapshot()["teams"]
        h, a = state.codes
        goals = state.goal_log
        winner_home = snap[h]["goals"] > snap[a]["goals"]
        trailed = any((g["score_home"] < g["score_away"]) if winner_home else (g["score_away"] < g["score_home"]) for g in goals)
        facts = {
            "home": snap[h]["name"], "away": snap[a]["name"], "score_home": snap[h]["goals"], "score_away": snap[a]["goals"],
            "scoreline": f"{snap[h]['name']} {snap[h]['goals']}-{snap[a]['goals']} {snap[a]['name']}",
            "poss_home": snap[h]["possession_pct"], "poss_away": snap[a]["possession_pct"],
            "shots_home": snap[h]["shots"], "shots_away": snap[a]["shots"],
            "xg_home": snap[h]["xg"], "xg_away": snap[a]["xg"],
            "comeback": bool(goals) and snap[h]["goals"] != snap[a]["goals"] and trailed,
            "goals": [{"minute": g["minute"], "scorer": g["player"], "team": snap[g["team"]]["name"]} for g in goals],
        }
        text = self.llm.complete(self.SYSTEM.format(language=LANGUAGES.get(p.lang, p.lang)), json.dumps(facts), 220) if p.ai else None
        source = "llm"
        if not text or not FactChecker().run(text, facts):
            text, source = self._narrative(facts, p.lang), "template"
        return {
            "headline": _fmt(RECAP.get(p.lang, RECAP["en"])[0], facts), "body": text, "source": source,
            "stats": snap, "home": h, "away": a, "goals": goals, "report": state.report(), "cards": state.card_log, "subs": state.sub_log,
            "key_moments": [{"minute": m.minute, "kind": m.kind, "headline": o.headline, "team": m.team} for m, o in top],
        }


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
                 runner=None, rosters: Optional[Dict[str, List[str]]] = None) -> None:
        self.llm = llm or get_llm()
        self.runner = runner  # optional itg.maf.MafRunner: Explainer->Narrator->FactChecker workflow
        self.state = MatchState(team_names, rosters)
        self.personalizer = PersonalizerAgent()
        self.explainer = ExplainerAgent(self.llm)
        self.narrator = NarratorAgent(self.llm)
        self.recapper = RecapAgent(self.llm)
        self.tactician = TacticalAnalystAgent(self.llm)
        self.newsroom = Newsroom(self.explainer, self.narrator)
        self.cache = cache if cache is not None else {}  # shared across viewers of the same match
        self.shown: List[Tuple[Moment, Overlay]] = []

    def process(self, event, profile: Profile) -> List[Overlay]:
        overlays = []
        for m in self.state.ingest(event):
            if not self.personalizer.relevant(m, profile):
                continue
            key = (m.id, profile.lang, profile.mode, profile.ai)
            if key not in self.cache:
                if not profile.ai:  # viewer switched AI off: grounded templates only
                    job = Job(m, profile, redo=set())
                    h, b, w = _tmpl(profile.lang, _template_key(m))
                    job.why, job.headline, job.body = _fmt(w, m.facts), _fmt(h, m.facts), _fmt(b, m.facts)
                    job.log("Narrator", "used the template", True, "AI switched off by the viewer")
                    self.newsroom.edit(job)
                else:
                    job = self.runner.run(m, profile) if self.runner else self.newsroom.run(m, profile)
                self.cache[key] = job
            job = self.cache[key]
            why, headline, body, source = job.why, job.headline, job.body, job.source
            audit = (FactChecker().audit(f"{headline} {body} {why}", m.facts) if source == "llm"
                     else {"numbers": [], "matched": [], "unmatched": []})  # templates are fixed wording, nothing to audit
            how = ("ai" if source == "llm" else "ai_off" if not profile.ai
                   else "fallback" if getattr(self.llm, "available", False) else "rules")
            ov = Overlay(
                moment_id=m.id, t=m.t, minute=m.minute, kind=m.kind, team=m.team,
                importance=m.importance, headline=headline, body=body,
                why=why if profile.mode == "analyst" or m.importance >= 0.9 else "",
                chips=self.personalizer.chips(m, profile), lang=profile.lang, mode=profile.mode,
                source=source, verified=True, duration_s=job.duration_s, player=m.player,
                facts=m.facts, model=(getattr(self.llm, "deployment", "") or self.llm.name) if source == "llm" else "",
                check={"how": how, "numbers": len(audit["numbers"]), "matched": len(audit["matched"]),
                       "unmatched": audit["unmatched"], "agents": ["Explainer", "Narrator", "FactChecker", "Editor"],
                       "trace": job.trace, "rewrites": sum(1 for s in job.trace if s["agent"] == "FactChecker" and not s["ok"]),
                       "slot": job.slot, "priority": job.priority})
            self.shown.append((m, ov))
            overlays.append(ov)
        return overlays

    def localize_tactics(self, update: Dict[str, Any], profile: Profile, t: float) -> Dict[str, Any]:
        """Adds a localised, fact-checked summary + options to each team's tactical profile.
        Cached per team / 5-minute window / language / mode and shared across viewers."""
        out: Dict[str, Any] = {}
        for c, p in update.items():
            opp = next((v for k, v in update.items() if k != c), None)
            key = ("tac", c, p["formation"], p["primary"], int(t // 300), profile.lang, profile.mode, profile.ai)
            if key not in self.cache:
                if opp is None or not profile.ai:
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
