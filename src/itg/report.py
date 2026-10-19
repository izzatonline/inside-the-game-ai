"""Full-time match report: territory heatmap, field tilt and possession-based style metrics.

Everything is derived from the event stream (no tracking frames needed), so it is cheap to build.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

COLS, ROWS = 24, 16
TOUCHES = {"pass", "carry", "shot", "tackle", "interception", "pressure"}


def _blur(grid: List[List[float]], passes: int = 3) -> List[List[float]]:
    for _ in range(passes):
        out = [[0.0] * COLS for _ in range(ROWS)]
        for j in range(ROWS):
            for i in range(COLS):
                tot, n = 0.0, 0
                for dj in (-1, 0, 1):
                    for di in (-1, 0, 1):
                        jj, ii = j + dj, i + di
                        if 0 <= jj < ROWS and 0 <= ii < COLS:
                            tot += grid[jj][ii]
                            n += 1
                out[j][i] = tot / n
        grid = out
    return grid


class MatchReportBuilder:
    def __init__(self, codes: List[str]) -> None:
        self.codes = codes
        self.grid = {c: [[0.0] * COLS for _ in range(ROWS)] for c in codes}
        self.ft = {c: 0 for c in codes}  # completed passes played from the final third
        self.adv = {c: {"starts": 0, "start_x": 0.0, "passes": 0, "builds": 0, "fast": 0, "press": 0,
                        "prog": 0, "ok": 0} for c in codes}
        self._poss: Optional[Dict[str, Any]] = None

    # ---- possession spells -------------------------------------------------
    def _end(self) -> None:
        p = self._poss
        if not p:
            return
        a = self.adv[p["team"]]
        a["starts"] += 1
        a["start_x"] += p["start_x"]
        a["passes"] += p["passes"]
        if p["passes"] >= 6 and p["max_x"] >= 67:
            a["builds"] += 1  # a patient move that reached the final third
        if p["start_x"] < 50 and p["t_reach"] is not None and p["t_reach"] - p["start_t"] <= 20:
            a["fast"] += 1  # won deep, in the final third within 20 seconds
        self._poss = None

    def _start(self, team: str, x: float, t: float) -> None:
        self._end()
        self._poss = {"team": team, "start_x": x, "start_t": t, "passes": 0, "max_x": x, "t_reach": None}

    @staticmethod
    def _reach(p: Dict[str, Any], x: float, t: float) -> None:
        if x > p["max_x"]:
            p["max_x"] = x
        if x >= 70 and p["t_reach"] is None:
            p["t_reach"] = t

    def observe(self, ev) -> None:
        if ev.type in ("kickoff", "possession_change"):
            self._start(ev.team, ev.x, ev.t)
        elif ev.type == "fulltime":
            self._end()
        p = self._poss
        if ev.type in TOUCHES:
            ax, ay = (ev.x, ev.y) if ev.team == self.codes[0] else (100 - ev.x, 100 - ev.y)
            self.grid[ev.team][min(ROWS - 1, int(ay / 100 * ROWS))][min(COLS - 1, int(ax / 100 * COLS))] += 1
            if ev.type in ("tackle", "interception", "pressure") and ev.x >= 60:
                self.adv[ev.team]["press"] += 1  # defensive action high up the pitch
        if ev.type == "pass" and ev.outcome == "complete":
            a = self.adv[ev.team]
            a["ok"] += 1
            if ev.x >= 66:
                self.ft[ev.team] += 1
            ex = ev.meta.get("ex")
            if ex is not None and ex - ev.x >= 10:
                a["prog"] += 1
            if p and p["team"] == ev.team:
                p["passes"] += 1
                self._reach(p, ex if ex is not None else ev.x, ev.t)
        elif ev.type in ("carry", "shot") and p and p["team"] == ev.team:
            self._reach(p, ev.x, ev.t)

    # ---- output ------------------------------------------------------------
    def build(self) -> Dict[str, Any]:
        self._end()
        h, a = self.codes
        gh, ga = _blur(self.grid[h]), _blur(self.grid[a])
        peak = max(max(max(r) for r in gh), max(max(r) for r in ga), 1e-9)
        v, w = [], []
        for j in range(ROWS):
            v.append([round((gh[j][i] - ga[j][i]) / (gh[j][i] + ga[j][i] + 1e-9), 3) for i in range(COLS)])
            w.append([round(min(1.0, ((gh[j][i] + ga[j][i]) / (2 * peak)) ** 0.5), 3) for i in range(COLS)])
        tot_ft = self.ft[h] + self.ft[a] or 1
        tilt_h = round(100 * self.ft[h] / tot_ft)

        def per(c: str) -> Dict[str, float]:
            d = self.adv[c]
            starts = max(d["starts"], 1)
            return {
                "start": round(d["start_x"] / starts * 1.05, 1),
                "prog": round(100 * d["prog"] / max(d["ok"], 1)),
                "circ": round(d["passes"] / starts, 2),
                "build": d["builds"], "fast": d["fast"], "press": d["press"],
            }

        m = {c: per(c) for c in self.codes}
        rows = [("start", "Start distance", " m"), ("prog", "Progression", "%"), ("circ", "Circulation", ""),
                ("build", "Build-ups", ""), ("fast", "Fast breaks", ""), ("press", "High press", "")]
        return {
            "heat": {"cols": COLS, "rows": ROWS, "v": v, "w": w},
            "tilt": {h: tilt_h, a: 100 - tilt_h},
            "metrics": [{"key": k, "label": lab, "unit": u, "home": m[h][k], "away": m[a][k]} for k, lab, u in rows],
        }
