from itg.agents import FactChecker, MatchPipeline
from itg.generator import TEAMS, generate_match
from itg.llm import OfflineLLM
from itg.models import Profile

NAMES = {c: v["name"] for c, v in TEAMS.items()}


def test_generator_is_deterministic():
    a, b = generate_match(7), generate_match(7)
    assert [e.to_dict() for e in a] == [e.to_dict() for e in b]
    assert a[-1].type == "fulltime"


def test_scoreline_matches_goal_moments():
    pipe = MatchPipeline(NAMES, OfflineLLM())
    goals = 0
    for e in generate_match(3):
        goals += sum(1 for m in pipe.state.ingest(e) if m.kind == "goal")
    assert goals == sum(pipe.state.snapshot()["teams"][c]["goals"] for c in NAMES)


def test_personalisation_changes_output():
    events = generate_match(3)
    out = {}
    for name, prof in {"casual": Profile(), "analyst": Profile(mode="analyst"),
                       "es": Profile(lang="es")}.items():
        pipe = MatchPipeline(NAMES, OfflineLLM())
        out[name] = [o for e in events for o in pipe.process(e, prof)]
    assert len(out["analyst"]) > len(out["casual"])
    assert any(o.chips for o in out["analyst"]) and not any(o.chips for o in out["casual"])
    assert any("GOL" in o.headline for o in out["es"])


def test_player_focus_only_shows_that_player_or_goals():
    pipe = MatchPipeline(NAMES, OfflineLLM())
    prof = Profile(player="Tungtung Sahur")
    for e in generate_match(3):
        for o in pipe.process(e, prof):
            assert o.kind == "goal" or "Tungtung Sahur" in (o.headline + o.body)


def test_fact_checker_blocks_invented_numbers():
    facts = {"xg": 0.31, "minute": 12}
    assert FactChecker().run("12' a 31% chance", facts)
    assert not FactChecker().run("12' a 64% chance", facts)


def test_recap_offline():
    pipe = MatchPipeline(NAMES, OfflineLLM())
    for e in generate_match(7):
        pipe.process(e, Profile())
    r = pipe.recap(Profile())
    assert r["headline"].startswith("Full time") and r["source"] == "template"
    assert "." in r["body"] and "Possession" not in r["body"] and r["goals"] is not None


def test_agent_framework_workflow_matches_plain_pipeline():
    maf = __import__("pytest").importorskip("agent_framework")  # noqa: F841
    from itg.maf import MafRunner

    events = generate_match(3)
    plain = MatchPipeline(NAMES, OfflineLLM())
    wf = MatchPipeline(NAMES, OfflineLLM(), runner=MafRunner(OfflineLLM()))
    prof = Profile(mode="analyst", lang="es")
    a = [(o.headline, o.body, o.why) for e in events for o in plain.process(e, prof)]
    b = [(o.headline, o.body, o.why) for e in events for o in wf.process(e, prof)]
    assert a and a == b


def test_broadcaster_fanout_and_late_join():
    import asyncio

    from itg.bus import Broadcaster, generator_source

    async def run():
        bc = Broadcaster(generator_source(3, speed=1e9))
        _, q1 = bc.subscribe()
        await bc.task
        hist, q2 = bc.subscribe()  # late joiner after the match ended
        got = []
        while (ev := await q1.get()) is not None:
            got.append(ev)
        return got, hist

    got, hist = asyncio.run(run())
    assert len(got) == len(hist) == len(generate_match(3))


def _analyze(seed):
    from itg.tactics import TacticsAnalyzer

    an = TacticsAnalyzer(list(TEAMS), NAMES, {c: [n for n, _ in v["players"]] for c, v in TEAMS.items()})
    for e in generate_match(seed):
        an.frame(e) if e.type == "tracking" else an.observe(e)
    return an.profiles


def test_tactics_infer_formation_from_positions_only():
    for seed in (1, 4, 7):
        p = _analyze(seed)
        assert p["NOR"]["formation"] == "4-3-3" and p["HAR"]["formation"] == "4-2-3-1"


def test_tactics_infer_style_and_roles():
    p = _analyze(7)
    assert p["NOR"]["line_height"] > p["HAR"]["line_height"] + 10  # high line vs low block
    ppda = [(_analyze(sd)["NOR"]["ppda"], _analyze(sd)["HAR"]["ppda"]) for sd in range(1, 7)]
    assert sum(a for a, _ in ppda) < sum(b for _, b in ppda)  # NOR press harder on average
    roles = {r["name"]: r["role"] for r in p["NOR"]["roles"]}
    assert roles["Callum Draper"] == "Inverted full-back"
    assert roles["Itadori Yuji"] == "Overlapping full-back"
    assert any(o["title"] for o in p["NOR"]["options"])


def test_tactic_moments_are_narrated_and_grounded():
    pipe = MatchPipeline(NAMES, OfflineLLM())
    kinds = {o.kind: o for e in generate_match(7) for o in pipe.process(e, Profile(mode="analyst"))}
    assert {"tactic_report", "role_reveal"} <= set(kinds)
    assert "4-3-3" in kinds["tactic_report"].headline or "4-2-3-1" in kinds["tactic_report"].headline


class _StubLLM:
    name, available = "stub", True

    def __init__(self, reply):
        self.reply = reply

    def complete(self, system, user, max_tokens=250):
        return self.reply(user) if callable(self.reply) else self.reply


def _pair():
    p = _analyze(7)
    for c in p:
        p[c]["name"] = NAMES[c]
        p[c]["options"] = [{"title": "Play in behind", "detail": f"Line {p[c]['line_height']}."}]
    return p["NOR"], p["HAR"]


def test_tactical_analyst_accepts_grounded_and_rejects_invented_numbers():
    import json

    from itg.agents import TacticalAnalystAgent

    nor, har = _pair()
    good = json.dumps({"summary": f"Los locales defienden en línea {nor['line_height']}.",
                       "options": [{"title": "Juego en largo", "detail": f"La línea rival está en {har['line_height']}."}]})
    s, opts, src = TacticalAnalystAgent(_StubLLM(good)).run(nor, har, "es", "analyst")
    assert src == "llm" and opts[0]["title"] == "Juego en largo"

    bad = json.dumps({"summary": "They press at 97% intensity.", "options": [{"title": "x", "detail": "y"}]})
    s, opts, src = TacticalAnalystAgent(_StubLLM(bad)).run(nor, har, "es", "analyst")
    assert src == "template" and "4-3-3" in s and opts == nor["options"]


def test_tactics_workflow_localises_and_guards():
    pytest = __import__("pytest")
    pytest.importorskip("agent_framework")
    from itg.maf import MafRunner

    nor, har = _pair()
    job = MafRunner(OfflineLLM()).run_tactics(nor, har, Profile(lang="ms"))
    assert job.verified and "beraksi" in job.summary
    liar = _StubLLM('{"summary": "A 142 m high line.", "options": []}')
    job = MafRunner(liar).run_tactics(nor, har, Profile(lang="en"))
    assert job.verified and job.source == "template"


def test_localize_tactics_is_cached_across_viewers():
    cache, calls = {}, []
    llm = _StubLLM(lambda user: calls.append(1) or None)
    nor, har = _pair()
    for _ in range(2):
        pipe = MatchPipeline(NAMES, llm, cache)
        out = pipe.localize_tactics({"NOR": nor, "HAR": har}, Profile(lang="es"), 300.0)
    assert len(calls) == 2 and out["NOR"]["summary"].startswith("Northbridge")


def test_tracking_reports_holder_phase_and_uncertainty():
    frames = [e for e in generate_match(7) if e.type == "tracking"]
    phases = {e.meta["phase"] for e in frames}
    assert {"open", "throw_in", "goal_kick", "corner", "keeper_hold"} <= phases
    assert all(0.0 <= e.meta["conf"] <= 1.0 for e in frames)
    confs = [e.meta["conf"] for e in frames]
    assert any(c >= 0.8 for c in confs) and any(0.5 <= c < 0.8 for c in confs) and any(c < 0.5 for c in confs)
    for e in frames:
        if e.meta["holder"] is None:
            assert e.meta["conf"] < 0.5  # never a named holder without confidence data
        else:
            assert e.meta["holder"][0] == e.meta["poss"] and 0 <= e.meta["holder"][1] < 11
    assert any(e.meta["phase_conf"] < 0.8 for e in frames if e.meta["phase"] == "corner")


def test_substitutions_warmups_and_roster_names():
    ev = generate_match(7)
    assert all(a.t <= b.t for a, b in zip(ev, ev[1:]))  # still time-ordered
    subs = [e for e in ev if e.type == "substitution"]
    warm = [e for e in ev if e.type == "warmup"]
    assert len(subs) == 6 and len(warm) == 6
    for s_ in subs:  # each sub warmed up first, and the replaced player never acts afterwards
        assert any(w.team == s_.team and w.meta["sub_idx"] == s_.meta["sub_idx"] and w.t < s_.t for w in warm)
        assert not any(e.player == s_.meta["player_out"] and e.t > s_.t for e in ev if e.type in ("pass", "shot"))


def test_substitution_moment_and_tactics_roster_update():
    pipe = MatchPipeline(NAMES, OfflineLLM())
    out = [o for e in generate_match(7) for o in pipe.process(e, Profile(mode="analyst"))]
    assert sum(o.kind == "substitution" for o in out) == 6
    sub = next(o for o in out if o.kind == "substitution")
    assert "replace" in sub.body


def test_riverside_scripted_storyline():
    ev = generate_match(7, match="riverside")
    assert ev[-1].meta["score"] == {"MER": 3, "TID": 2}
    goals = [(e.minute, e.team, e.player) for e in ev if e.type == "shot" and e.outcome == "goal"]
    assert [g[:2] for g in goals] == [(18, "MER"), (25, "TID"), (37, "MER"), (67, "MER"), (90, "TID")]
    assert any(e.type == "shot" and e.outcome == "disallowed" for e in ev)
    assert [e.meta["kind"] for e in ev if e.type == "var"] == ["goal_check", "no_goal", "penalty_check", "penalty_awarded"]
    assert any(e.type == "tracking" and e.meta["phase"] == "penalty" for e in ev)
    assert sum(e.type == "substitution" for e in ev) == 10 and sum(e.type == "card" for e in ev) == 3
    assert all(a.t <= b.t for a, b in zip(ev, ev[1:]))


def test_riverside_story_in_the_pipeline_and_dominance():
    from itg.generator import MATCHES

    spec = MATCHES["riverside"]
    names = {c: v["name"] for c, v in spec.teams.items()}
    rosters = {c: [n for n, _ in v["players"]] for c, v in spec.teams.items()}
    pipe = MatchPipeline(names, OfflineLLM(), rosters=rosters)
    out = [o for e in generate_match(7, match="riverside") for o in pipe.process(e, Profile(mode="analyst"))]
    kinds = [o.kind for o in out]
    assert kinds.count("goal") == 5 and kinds.count("var") == 4 and kinds.count("card") == 3
    assert any(o.kind == "goal" and "penalty spot" in o.body for o in out)
    assert any(o.kind == "var" and "offside" in o.body and "86'" in o.body for o in out)
    snap = pipe.state.snapshot()["teams"]
    assert snap["MER"]["possession_pct"] >= 62  # the dominant side keeps the ball
    r = pipe.recap(Profile())
    assert r["headline"].startswith("Full time: Meridian FC 3-2 Tidewater Town")


def test_redcrest_storyline_own_goal_var_and_penalty():
    from itg.generator import MATCHES

    spec = MATCHES["redcrest"]
    names = {c: v["name"] for c, v in spec.teams.items()}
    rosters = {c: [n for n, _ in v["players"]] for c, v in spec.teams.items()}
    ev = generate_match(7, match="redcrest")
    assert ev[-1].meta["score"] == {"RED": 5, "KES": 2}
    pipe = MatchPipeline(names, OfflineLLM(), rosters=rosters)
    out = [o for e in ev for o in pipe.process(e, Profile(mode="analyst"))]
    goals = [o for o in out if o.kind == "goal"]
    assert len(goals) == 7
    assert any("OWN GOAL" in o.headline for o in goals) and any("penalty spot" in o.body for o in goals)
    assert [o.headline for o in out if o.kind == "var"] == ["VAR check: possible goal", "VAR: goal stands"]
    r = pipe.recap(Profile())
    assert r["headline"].startswith("Full time: Redcrest United 5-2 Kestrel Town")
    assert any(g.get("og") for g in r["goals"])
    assert 52 <= r["stats"]["RED"]["possession_pct"] <= 75


def test_stream_start_minute_catches_up_and_ends_the_same():
    from fastapi.testclient import TestClient

    from itg.server import app

    c = TestClient(app)
    base = "/api/stream?match=riverside&speed=1000000&lang=en&mode=analyst"
    full = c.get(base).text
    part = c.get(base + "&start=70").text
    assert "event: live" in part and "event: live" not in full
    history = part.split("event: live")[0]
    assert '"kind": "goal"' in history and "event: bench" in history  # early goals and subs come in the burst
    assert part.count("event: frame") < 0.5 * full.count("event: frame")  # frames before the jump are skipped
    assert part.split("event: recap")[1] == full.split("event: recap")[1]  # same final result either way


def test_match_report_is_built_from_events():
    from itg.generator import MATCHES

    for mid, home_dominant in (("riverside", True), ("coastal", None)):
        spec = MATCHES[mid]
        names = {c: v["name"] for c, v in spec.teams.items()}
        rosters = {c: [n for n, _ in v["players"]] for c, v in spec.teams.items()}
        pipe = MatchPipeline(names, OfflineLLM(), rosters=rosters)
        for e in generate_match(3, match=mid):
            pipe.process(e, Profile())
        rep = pipe.recap(Profile())["report"]
        heat = rep["heat"]
        assert len(heat["v"]) == heat["rows"] and len(heat["v"][0]) == heat["cols"]
        assert all(-1 <= x <= 1 for row in heat["v"] for x in row) and all(0 <= x <= 1 for row in heat["w"] for x in row)
        assert sum(rep["tilt"].values()) == 100
        assert [m["key"] for m in rep["metrics"]] == ["start", "prog", "circ", "build", "fast", "press"]
        if home_dominant:  # the dominant side owns the final third and builds patiently
            first = list(rep["tilt"])[0]
            assert rep["tilt"][first] > 70
            build = next(m for m in rep["metrics"] if m["key"] == "build")
            assert build["home"] > build["away"]
