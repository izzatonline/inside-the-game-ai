"""Interpret stage: fold raw events into football state and detect explainable moments."""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, Tuple

from .models import Event, Moment
from .report import MatchReportBuilder
from .tactics import TacticsAnalyzer

def minute_label(m: int) -> str:
    """Stoppage time reads 90+3', not 93'."""
    return str(m) if m <= 90 else f"90+{m - 90}"


WINDOW_S = 300.0  # rolling window for pressure / momentum
SPRINT_KMH = 33.0
HIGH_SPEED_KMH = 27.0
MAX_RUN_MS = 9.5  # faster than this between two frames is a jump in the data, not running
SWING_SHARE = 0.70  # pressure share needed to call a momentum swing
MIN_WINDOW_WEIGHT = 8.0


@dataclass
class TeamStats:
    name: str
    passes: int = 0
    passes_ok: int = 0
    actions: int = 0
    shots: int = 0
    on_target: int = 0
    goals: int = 0
    xg: float = 0.0
    tackles: int = 0
    interceptions: int = 0
    pressures: int = 0
    blocked: int = 0
    off_target: int = 0
    saves: int = 0
    corners: int = 0
    free_kicks: int = 0
    throw_ins: int = 0
    goal_kicks: int = 0
    fouls: int = 0
    yellow: int = 0
    offsides: int = 0
    crosses: int = 0


@dataclass
class PlayerStats:
    name: str
    team: str
    passes: int = 0
    passes_ok: int = 0
    shots: int = 0
    goals: int = 0
    xg: float = 0.0
    top_speed: float = 0.0
    diff_sum: float = 0.0  # difficulty of completed passes
    sprints: int = 0
    tackles: int = 0
    interceptions: int = 0
    pressures: int = 0
    on_target: int = 0
    assists: int = 0
    distance_m: float = 0.0  # from 1-second tracking
    fast: bool = False  # currently above HIGH_SPEED_KMH (a run is counted once, when it starts)


RESTART_CONFIRM_S = 10.0  # a restart event confirms frames of the same restart this many seconds after it


class MatchState:
    def __init__(self, teams: Dict[str, str], rosters: Optional[Dict[str, List[str]]] = None):
        self.codes = list(teams)
        self.teams = {c: TeamStats(n) for c, n in teams.items()}
        self.players: Dict[str, PlayerStats] = {}
        self.t = 0.0
        # (t, team, weight, xg, is_shot)
        self.window: Deque[Tuple[float, str, float, float, bool]] = deque()
        self.turnovers: Deque[float] = deque()
        self.last_pass: Optional[Tuple[str, str, float]] = None
        self.dominant: Optional[str] = None
        self._cooldown: Dict[str, float] = {}
        self._n = 0
        self.report_builder = MatchReportBuilder(self.codes)
        self._last_frame: Optional[Tuple[float, List[List[float]], str]] = None
        self.restart_watch: Dict[str, Dict[str, Dict[str, float]]] = {}  # team -> kind -> n, over, total, longest
        self.last_restart: Optional[Tuple[float, str, str]] = None  # (t, team, kind) of the latest official restart
        self.goal_log: List[Dict[str, Any]] = []
        self.card_log: List[Dict[str, Any]] = []
        self.sub_log: List[Dict[str, Any]] = []
        # rosters give the analyzer names only, never roles
        self.tactics = TacticsAnalyzer(
            self.codes, teams,
            {c: list((rosters or {}).get(c) or [f"P{i + 1}" for i in range(11)]) for c in self.codes})

    # ---- helpers -------------------------------------------------------
    def _player(self, name: str, team: str) -> PlayerStats:
        return self.players.setdefault(name, PlayerStats(name, team))

    def _opp(self, team: str) -> str:
        return self.codes[1] if team == self.codes[0] else self.codes[0]

    def _window_weight(self) -> float:
        return sum(w for _, _, w, _, _ in self.window)

    def pressure_share(self, team: str) -> float:
        total = self._window_weight()
        if total < MIN_WINDOW_WEIGHT:
            return 0.5
        return sum(w for _, tm, w, _, _ in self.window if tm == team) / total

    def momentum(self) -> float:
        """-1..1, positive = home (first team) on top."""
        return round(2 * self.pressure_share(self.codes[0]) - 1, 2)

    def _window_shots(self, team: str) -> Tuple[int, float]:
        shots = [(xg) for _, tm, _, xg, s in self.window if tm == team and s]
        return len(shots), round(sum(shots), 2)

    def _ready(self, key: str, cooldown: float) -> bool:
        if self.t - self._cooldown.get(key, -1e9) < cooldown:
            return False
        self._cooldown[key] = self.t
        return True

    def _moment(self, ev: Event, kind: str, importance: float, player: Optional[str],
                team: str, **facts: Any) -> Moment:
        self._n += 1
        base = {
            "minute": minute_label(ev.minute), "team": team, "team_name": self.teams[team].name,
            "player": player, "window_min": int(WINDOW_S // 60),  # the rolling window "last N minutes" refers to
        }
        base.update(facts)
        return Moment(f"{kind}-{self._n}", kind, ev.t, ev.minute, team, player,
                      round(importance, 2), base)

    def phase_conf(self, ev: Event) -> float:
        """Confidence in a tracking frame's phase. The tracker alone may be unsure (was it a corner or a goal kick?),
        but once the official restart event for that team and kind has arrived, the restart is confirmed."""
        conf = ev.meta["phase_conf"]
        r = self.last_restart
        if r and r[1] == ev.meta["poss"] and r[2] == ev.meta["phase"] and 0 <= ev.t - r[0] <= RESTART_CONFIRM_S:
            return max(conf, 0.97)
        return conf

    def _restart_watch(self, ev: Event) -> List[Moment]:
        """Restart Watch: how long each throw-in, goal kick and keeper hold took, against the Premier League
        2026/27 handbook limits (throw-in and goal kick 5 s, keeper 8 s). Neutral: it reports, it does not judge."""
        kind, secs, limit = ev.meta["kind"], ev.meta["secs"], ev.meta["limit"]
        w = self.restart_watch.setdefault(ev.team, {}).setdefault(kind, {"n": 0, "over": 0, "total": 0.0, "longest": 0.0})
        w["n"] += 1
        w["total"] += secs
        w["longest"] = max(w["longest"], secs)
        if secs <= limit:
            return []
        w["over"] += 1
        if secs < limit + 1 or not self._ready("restart:" + ev.team, 600):  # clear cases only, one per 10 minutes
            return []
        return [self._moment(ev, "restart_late_" + kind, 0.35, None, ev.team, secs=secs, limit=int(limit),
                             over=w["over"])]

    def _physical(self, ev: Event) -> None:
        """Distance covered, top speed and fast runs, measured between consecutive 1-second tracking frames.
        Jumps faster than any player can run (9.5 m/s, 34 km/h) and the walk-back during long stoppages are skipped."""
        last, self._last_frame = self._last_frame, (ev.t, ev.meta["pos"], ev.meta["phase"])
        if not last or not self.tactics.rosters:
            return
        dt = ev.t - last[0]
        if not 0.5 <= dt <= 1.5 or "stoppage" in (last[2], ev.meta["phase"]):
            return
        for i, (p, q) in enumerate(zip(last[1], ev.meta["pos"])):
            v = math.hypot((q[0] - p[0]) * 1.05, (q[1] - p[1]) * 0.68) / dt
            if v > MAX_RUN_MS:
                continue
            team = self.codes[i // 11]
            ps = self._player(self.tactics.rosters[team][i % 11], team)
            ps.distance_m += v * dt
            kmh = v * 3.6
            ps.top_speed = max(ps.top_speed, kmh)
            if kmh >= HIGH_SPEED_KMH and not ps.fast:
                ps.sprints += 1  # high-speed runs (the radar's "Fast runs")
            ps.fast = kmh >= HIGH_SPEED_KMH

    # ---- main entry ----------------------------------------------------
    def ingest(self, ev: Event) -> List[Moment]:
        self.t = ev.t
        out: List[Moment] = []
        if ev.type == "tracking":
            self._physical(ev)
            self.tactics.frame(ev)
            return [self._moment(ev, d["kind"], d["importance"], d["player"], d["team"], **d["facts"])
                    for d in self.tactics.pop_moments()]
        self.tactics.observe(ev)
        self.report_builder.observe(ev)
        if ev.type == "warmup":
            return out
        if ev.type == "restart_taken":
            return self._restart_watch(ev)
        if ev.type in ("restart", "foul", "card", "offside"):
            ts0 = self.teams[ev.team]
            if ev.type == "restart":
                self.last_restart = (ev.t, ev.team, ev.meta["kind"])
                attr = {"corner": "corners", "free_kick": "free_kicks", "throw_in": "throw_ins", "goal_kick": "goal_kicks"}.get(ev.meta["kind"])
                if attr:
                    setattr(ts0, attr, getattr(ts0, attr) + 1)
            elif ev.type == "foul":
                ts0.fouls += 1
            elif ev.type == "offside":
                ts0.offsides += 1
            else:
                ts0.yellow += 1
                self.card_log.append({"minute": ev.minute, "team": ev.team, "player": ev.player, "card": "yellow"})
                return [self._moment(ev, "card", 0.6, ev.player, ev.team, card="yellow")]
            return out
        if ev.type == "own_goal":
            ts0 = self.teams[ev.team]
            ts0.goals += 1
            home, away = self.codes
            self.goal_log.append({"minute": ev.minute, "team": ev.team, "player": ev.player, "og": True,
                                  "score_home": self.teams[home].goals, "score_away": self.teams[away].goals})
            return [self._moment(
                ev, "goal", 1.0, ev.player, ev.team, own_goal=True, against_run=False,
                scoring_team=self.teams[ev.team].name, player_team=self.teams[self._opp(ev.team)].name,
                score_home=self.teams[home].goals, score_away=self.teams[away].goals,
                scoreline=f"{self.teams[home].name} {self.teams[home].goals}-{self.teams[away].goals} {self.teams[away].name}",
                pressure_pct=int(round(self.pressure_share(ev.team) * 100)))]
        if ev.type == "var":
            home, away = self.codes
            return [self._moment(ev, "var", 0.9 if ev.meta["kind"] in ("no_goal", "penalty_awarded") else 0.7,
                                 ev.player or None, ev.team, var_kind=ev.meta["kind"],
                                 score_home=self.teams[home].goals, score_away=self.teams[away].goals)]
        if ev.type == "substitution":
            self.tactics.rosters[ev.team][ev.meta["slot"]] = ev.player  # roles now belong to the new player
            self.sub_log.append({"minute": ev.minute, "team": ev.team, "slot": ev.meta["slot"], "player_in": ev.player,
                                 "player_out": ev.meta["player_out"], "number": ev.meta["number"]})
            return [self._moment(ev, "substitution", 0.6, ev.player, ev.team,
                                 player_in=ev.player, player_out=ev.meta["player_out"])]
        if ev.type in ("kickoff", "fulltime"):
            return out
        ts = self.teams[ev.team]
        ps = self._player(ev.player, ev.team)
        weight, xg, is_shot = 0.0, 0.0, False

        if ev.type == "pass":
            ts.passes += 1
            ts.actions += 1
            ps.passes += 1
            ok = ev.outcome == "complete"
            if ok:
                ts.passes_ok += 1
                ps.passes_ok += 1
                ps.diff_sum += ev.meta.get("difficulty", 0)
                self.last_pass = (ev.player, ev.team, ev.t)
            if ev.x >= 67:
                weight = 1.0
            ex, ey = ev.meta.get("ex", 0), ev.meta.get("ey", 50)
            if abs(ev.y - 50) >= 36 and ev.x >= 70 and ex >= 84.3 and 20.4 <= ey <= 79.6:
                ts.crosses += 1  # from a wide area into the penalty area
            diff = ev.meta.get("difficulty", 0)
            if ok and diff >= 0.8 and self._ready("hardpass:" + ev.player, 900):
                out.append(self._moment(
                    ev, "difficult_pass", 0.4, ev.player, ev.team,
                    distance=int(round(ev.meta["distance_m"])), difficulty=int(round(diff * 100))))
            if ps.passes in (50, 100) and ok:
                acc = int(round(100 * ps.passes_ok / ps.passes))
                out.append(self._moment(ev, "milestone", 0.3, ev.player, ev.team,
                                        count=ps.passes, acc=acc))
        elif ev.type == "carry":
            ts.actions += 1
            speed = ev.meta.get("speed_kmh", 0)  # measured from tracking by the generator
            if ev.x >= 67:
                weight = 1.0
            if speed >= SPRINT_KMH and self._ready("sprint:" + ev.player, 600):
                out.append(self._moment(ev, "sprint", 0.3, ev.player, ev.team, speed=int(speed)))
        elif ev.type == "shot":
            xg, is_shot = ev.meta["xg"], True
            ts.shots += 1
            ts.xg += xg
            ps.shots += 1
            ps.xg += xg
            if ev.outcome in ("goal", "saved"):
                ps.on_target += 1
            if ev.outcome in ("goal", "saved"):
                ts.on_target += 1
            if ev.outcome == "saved":
                self.teams[self._opp(ev.team)].saves += 1
            elif ev.outcome == "blocked":
                ts.blocked += 1
            elif ev.outcome in ("off_target", "disallowed"):
                ts.off_target += 1
            weight = 2 + 6 * xg
        elif ev.type in ("tackle", "interception"):
            if ev.type == "tackle":
                ts.tackles += 1
                ps.tackles += 1
            else:
                ts.interceptions += 1
                ps.interceptions += 1
            if ev.x >= 55:
                weight = 1.5
        elif ev.type == "pressure":
            ts.pressures += 1
            ps.pressures += 1
            weight = 0.5
        elif ev.type == "possession_change":
            self.turnovers.append(ev.t)

        if weight:
            self.window.append((ev.t, ev.team, weight, xg, is_shot))
        while self.window and ev.t - self.window[0][0] > WINDOW_S:
            self.window.popleft()
        while self.turnovers and ev.t - self.turnovers[0] > 180:
            self.turnovers.popleft()

        if is_shot:
            out.extend(self._shot_moments(ev, ts, ps))
        out.extend(self._regime_moments(ev))
        return out

    def _shot_moments(self, ev: Event, ts: TeamStats, ps: PlayerStats) -> List[Moment]:
        xg = ev.meta["xg"]
        opp = self.teams[self._opp(ev.team)]
        share = self.pressure_share(ev.team)
        if ev.outcome == "goal":
            ts.goals += 1
            ps.goals += 1
            assist = None
            if self.last_pass and self.last_pass[1] == ev.team and ev.t - self.last_pass[2] <= 12 \
                    and self.last_pass[0] != ev.player:
                assist = self.last_pass[0]
                self._player(assist, ev.team).assists += 1
            home, away = self.codes
            self.goal_log.append({"minute": ev.minute, "team": ev.team, "player": ev.player,
                                  "score_home": self.teams[home].goals, "score_away": self.teams[away].goals})
            return [self._moment(
                ev, "goal", 1.0, ev.player, ev.team,
                xg=xg, xg_pct=int(round(xg * 100)), shot_speed=int(ev.meta["speed_kmh"]),
                score_home=self.teams[home].goals, score_away=self.teams[away].goals,
                scoreline=f"{self.teams[home].name} {self.teams[home].goals}-"
                          f"{self.teams[away].goals} {self.teams[away].name}",
                assist=assist, player_goals=ps.goals, penalty=bool(ev.meta.get("penalty")),
                scoring_team=ts.name, player_team=ts.name,
                pressure_pct=int(round(share * 100)), against_run=share < 0.35,
            )]
        if xg >= 0.25 and ev.outcome != "disallowed":
            return [self._moment(
                ev, "big_chance", min(0.9, 0.45 + xg), ev.player, ev.team,
                xg=xg, xg_pct=int(round(xg * 100)), outcome=ev.outcome,
                team_xg=round(ts.xg, 2), opp_xg=round(opp.xg, 2))]
        return []

    def _regime_moments(self, ev: Event) -> List[Moment]:
        out: List[Moment] = []
        # Momentum swing: one side owns >=70% of recent pressure (with hysteresis).
        if self._window_weight() >= MIN_WINDOW_WEIGHT:
            leader = next((c for c in self.codes if self.pressure_share(c) >= SWING_SHARE), None)
            if leader is None and all(abs(self.pressure_share(c) - 0.5) < 0.1 for c in self.codes):
                self.dominant = None
            if leader and leader != self.dominant:
                self.dominant = leader
                if self._ready("swing", 420):
                    shots, xg5 = self._window_shots(leader)
                    out.append(self._moment(
                        ev, "momentum_swing", 0.55, None, leader,
                        pressure_pct=int(round(self.pressure_share(leader) * 100)),
                        shots_5=shots, xg_5=xg5))
        if len(self.turnovers) >= 15 and self._ready("chaos", 600):
            out.append(self._moment(ev, "chaos_spell", 0.45, None, ev.team,
                                    changes=len(self.turnovers)))
        return out

    # ---- read models ---------------------------------------------------
    def report(self):
        return self.report_builder.build()

    def snapshot(self) -> Dict[str, Any]:
        total_actions = sum(t.actions for t in self.teams.values()) or 1
        return {
            "t": self.t,
            "minute": int(self.t // 60) + 1,
            "momentum": self.momentum(),
            "restart_watch": {c: {k: {"n": int(w["n"]), "over": int(w["over"]), "avg": round(w["total"] / w["n"], 1),
                                      "longest": round(w["longest"], 1)} for k, w in kinds.items()}
                              for c, kinds in self.restart_watch.items()},
            "players": {n: {"team": p.team, "passes": p.passes, "passes_ok": p.passes_ok,
                            "pass_acc": int(round(100 * p.passes_ok / p.passes)) if p.passes else 0,
                            "pass_diff": int(round(100 * p.diff_sum / p.passes_ok)) if p.passes_ok else 0,
                            "shots": p.shots, "on_target": p.on_target, "goals": p.goals, "assists": p.assists,
                            "xg": round(p.xg, 2), "sprints": p.sprints, "top_speed": int(p.top_speed),
                            "distance_km": round(p.distance_m / 1000, 1),
                            "tackles": p.tackles, "interceptions": p.interceptions, "pressures": p.pressures}
                        for n, p in self.players.items()},
            "teams": {
                c: {
                    "name": s.name,
                    "goals": s.goals,
                    "possession_pct": int(round(100 * s.actions / total_actions)),
                    "shots": s.shots,
                    "on_target": s.on_target,
                    "xg": round(s.xg, 2),
                    "pass_acc_pct": int(round(100 * s.passes_ok / s.passes)) if s.passes else 0,
                    "passes": s.passes, "shots_off": s.off_target, "shots_blocked": s.blocked, "saves": s.saves,
                    "corners": s.corners, "free_kicks": s.free_kicks, "throw_ins": s.throw_ins, "goal_kicks": s.goal_kicks,
                    "fouls": s.fouls, "yellow": s.yellow, "offsides": s.offsides, "crosses": s.crosses,
                    "tackles": s.tackles, "interceptions": s.interceptions, "pressures": s.pressures,
                }
                for c, s in self.teams.items()
            },
        }
