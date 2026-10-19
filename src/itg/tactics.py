"""Tactics analyzer: infers shape, style and player roles from tracking positions + events.

It never sees the generator's slot labels. Everything here is derived from where players
actually are (in / out of possession) and what the team does on the ball.
All coordinates are team-relative: x 0 = own goal .. 100 = opponent goal, y 0..100.
"""
from __future__ import annotations

import math
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

from .models import Event

WINDOW_S = 420.0
UPDATE_S = 60.0
FIRST_UPDATE_S = 240.0
MIN_FRAMES = 6

HIGH_LINE, LOW_LINE = 31.0, 22.0
PRESS_PPDA, PASSIVE_PPDA = 3.0, 6.0  # PPDA-like: opponent passes per defensive action (synthetic scale)

ROLE_SHORT = {
    "Goalkeeper": "GK", "Centre-back": "CB", "Full-back": "FB", "Inverted full-back": "IFB",
    "Overlapping full-back": "OFB", "Holding midfielder": "DM", "Double pivot": "DM",
    "Box-to-box midfielder": "B2B", "Advanced 8": "AM8", "Number 10": "#10", "Winger": "W",
    "Inverted winger": "IW", "Inside forward": "IF", "Striker": "ST",
}
FEATURED = {"Inverted full-back", "Overlapping full-back", "Inside forward", "Inverted winger"}


def _partition(xs: List[float], k: int) -> Tuple[float, List[int]]:
    """Optimal split of sorted values into k contiguous groups (min within-group SSE)."""
    n = len(xs)
    pre, pre2 = [0.0], [0.0]
    for v in xs:
        pre.append(pre[-1] + v)
        pre2.append(pre2[-1] + v * v)

    def sse(i: int, j: int) -> float:  # [i, j)
        m = j - i
        return (pre2[j] - pre2[i]) - (pre[j] - pre[i]) ** 2 / m

    best: Dict[Tuple[int, int], Tuple[float, List[int]]] = {}

    def solve(i: int, g: int) -> Tuple[float, List[int]]:
        if g == 1:
            return sse(i, n), [n]
        if (i, g) in best:
            return best[(i, g)]
        res = (float("inf"), [])
        for j in range(i + 1, n - g + 2):
            tail, cuts = solve(j, g - 1)
            cand = sse(i, j) + tail
            if cand < res[0]:
                res = (cand, [j] + cuts)
        best[(i, g)] = res
        return res

    return solve(0, k)


def _hull(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lo: List[Tuple[float, float]] = []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    up: List[Tuple[float, float]] = []
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def hull_area_m2(points: List[Tuple[float, float]]) -> float:
    h = [(x * 1.05, y * 0.68) for x, y in _hull(points)]
    return abs(sum(h[i][0] * h[(i + 1) % len(h)][1] - h[(i + 1) % len(h)][0] * h[i][1]
                   for i in range(len(h)))) / 2 if len(h) >= 3 else 0.0


class TacticsAnalyzer:
    def __init__(self, codes: List[str], names: Dict[str, str], rosters: Dict[str, List[str]]):
        self.codes, self.names, self.rosters = codes, names, rosters
        self.frames: Dict[str, Deque[Tuple[float, bool, List[List[float]]]]] = {c: deque() for c in codes}
        self.passes: Dict[str, Deque[Tuple[float, float, bool, bool]]] = {c: deque() for c in codes}
        self.defacts: Dict[str, Deque[Tuple[float, float]]] = {c: deque() for c in codes}
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self._last_update = -1e9
        self._reported: set = set()
        self._seen_roles: set = set()
        self._tag_pending: Dict[str, Tuple[str, int]] = {}
        self._ppda: Dict[str, float] = {}
        self._last_shift: Dict[str, float] = {}
        self._primary: Dict[str, str] = {}
        self._moments: List[Dict[str, Any]] = []
        self._dirty = False

    # ---- ingest --------------------------------------------------------
    def observe(self, ev: Event) -> None:
        if ev.type == "pass":
            self.passes[ev.team].append((ev.t, ev.x, ev.meta.get("distance_m", 0) >= 25,
                                         abs(ev.y - 50) >= 27))
        elif ev.type in ("tackle", "interception", "pressure"):
            self.defacts[ev.team].append((ev.t, ev.x))

    def frame(self, ev: Event) -> None:
        pos, poss = ev.meta["pos"], ev.meta["poss"]
        for ci, c in enumerate(self.codes):
            seg = pos[ci * 11:(ci + 1) * 11]
            rel = seg if ci == 0 else [[100 - x, 100 - y] for x, y in seg]
            self.frames[c].append((ev.t, c == poss, rel))
        for dq in (*self.frames.values(), *self.passes.values(), *self.defacts.values()):
            while dq and ev.t - dq[0][0] > WINDOW_S:
                dq.popleft()
        if ev.t >= FIRST_UPDATE_S and ev.t - self._last_update >= UPDATE_S:
            self._last_update = ev.t
            self._update(ev)

    # ---- analysis ------------------------------------------------------
    def _profile(self, c: str) -> Optional[Dict[str, Any]]:
        fr = self.frames[c]
        fin = [f for f in fr if f[1]]
        fout = [f for f in fr if not f[1]]
        if len(fin) < MIN_FRAMES or len(fout) < MIN_FRAMES:
            return None

        def avg(frames):
            return [[sum(f[2][i][a] for f in frames) / len(frames) for a in (0, 1)] for i in range(11)]

        a_out, a_in = avg(fout), avg(fin)
        gk = min(range(11), key=lambda i: a_out[i][0])
        field = sorted((i for i in range(11) if i != gk), key=lambda i: a_out[i][0])
        xs = [a_out[i][0] for i in field]
        sse3, cuts3 = _partition(xs, 3)
        sse4, cuts4 = _partition(xs, 4)
        cuts = cuts4 if sse3 > 0 and sse4 < 0.3 * sse3 else cuts3
        groups, start = [], 0
        for cut in cuts:
            groups.append(field[start:cut])
            start = cut
        formation = "-".join(str(len(g)) for g in groups)

        roles = {gk: "Goalkeeper"}
        mids = groups[1:-1]
        for gi, g in enumerate(groups):
            for i in g:
                ox, oy = a_out[i]
                ix, iy = a_in[i]
                wide = abs(oy - 50) >= 25
                tucks = abs(oy - 50) - abs(iy - 50) >= 12
                if gi == 0:
                    if not wide:
                        roles[i] = "Centre-back"
                    elif ix >= 55 and abs(iy - 50) >= 30:
                        roles[i] = "Overlapping full-back"
                    elif abs(iy - 50) <= 24 and ix >= 40:
                        roles[i] = "Inverted full-back"
                    else:
                        roles[i] = "Full-back"
                elif gi == len(groups) - 1:
                    if abs(oy - 50) >= 28:
                        roles[i] = "Inside forward" if tucks else "Winger"
                    else:
                        roles[i] = "Striker"
                else:
                    if abs(oy - 50) >= 28:
                        roles[i] = "Inverted winger" if tucks else "Winger"
                    elif mids.index(g) == 0:
                        deepest = min((j for j in g if abs(a_out[j][1] - 50) < 28), key=lambda j: a_out[j][0])
                        if len(g) == 2:
                            roles[i] = "Double pivot"
                        elif i == deepest:
                            roles[i] = "Holding midfielder"
                        else:
                            roles[i] = "Advanced 8" if ix >= 63 else "Box-to-box midfielder"
                    else:
                        roles[i] = "Number 10"

        # shape metrics from out-of-possession frames (outfield only)
        areas, spreads = [], []
        for _, _, rel in fout:
            pts = [(rel[i][0], rel[i][1]) for i in range(11) if i != gk]
            areas.append(hull_area_m2(pts))
            ys = [p[1] for p in pts]
            spreads.append((max(ys) - min(ys)) * 0.68)
        line_height = sum(a_out[i][0] for i in groups[0]) / len(groups[0])

        opp = self.codes[1] if c == self.codes[0] else self.codes[0]
        opp_passes = sum(1 for _, px, _, _ in self.passes[opp] if px <= 60)
        high_acts = sum(1 for _, ax in self.defacts[c] if ax >= 40)
        ppda = opp_passes / max(high_acts, 1)
        own = self.passes[c]
        long_pct = round(100 * sum(1 for p in own if p[2]) / len(own)) if own else 0
        wide_pct = round(100 * sum(1 for p in own if p[3]) / len(own)) if own else 0

        return {
            "formation": formation, "line_height": round(line_height), "width_m": round(sum(spreads) / len(spreads)),
            "hull_area": round(sum(areas) / len(areas)), "ppda": round(ppda, 1), "long_pct": long_pct,
            "wide_pct": wide_pct, "tags": [], "primary": "",
            "roles": [{
                "idx": i, "name": self.rosters[c][i], "role": roles[i], "short": ROLE_SHORT[roles[i]],
                "x_in": round(a_in[i][0]), "y_in": round(a_in[i][1]),
            } for i in range(11)],
        }

    @staticmethod
    def _retag(prof: Dict[str, Any]) -> None:
        line, ppda = prof["line_height"], prof["ppda"]
        tags = ["high line" if line >= HIGH_LINE else "low block" if line <= LOW_LINE else "mid block"]
        if ppda <= PRESS_PPDA:
            tags.append("aggressive press")
        elif ppda >= PASSIVE_PPDA:
            tags.append("passive press")
        if prof["long_pct"] >= 20:
            tags.append("direct play")
        elif prof["long_pct"] <= 12:
            tags.append("short build-up")
        if prof["wide_pct"] >= 50:
            tags.append("wing play")
        prof["tags"] = tags
        prof["primary"] = ("high press" if line >= HIGH_LINE and ppda <= PRESS_PPDA
                           else tags[0])

    def _options(self, c: str) -> List[Dict[str, str]]:
        opp = self.codes[1] if c == self.codes[0] else self.codes[0]
        me, them = self.profiles.get(c), self.profiles.get(opp)
        if not me or not them:
            return []
        on, out = self.names[opp], []
        if them["line_height"] >= HIGH_LINE:
            out.append({"title": "Play in behind",
                        "detail": f"{on} defend at line {them['line_height']}: long diagonals to the wide forwards "
                                  f"can attack the space behind their full-backs."})
        elif them["line_height"] <= LOW_LINE:
            out.append({"title": "Be patient, attack the half-spaces",
                        "detail": f"{on} sit deep (line {them['line_height']}). Overload the channels between "
                                  f"centre-back and full-back, and shoot from range."})
        if them["ppda"] <= PRESS_PPDA:
            out.append({"title": "Bypass the press",
                        "detail": f"{on} press hard (PPDA {them['ppda']}). Use a long ball over the first line "
                                  f"or a short triangle to escape it."})
        elif them["ppda"] >= PASSIVE_PPDA:
            out.append({"title": "Press their first pass",
                        "detail": f"{on} allow passes freely (PPDA {them['ppda']}). Stepping up to disrupt "
                                  f"build-up can win the ball high."})
        if them["width_m"] <= 38:
            out.append({"title": "Switch the play",
                        "detail": f"{on} are narrow ({them['width_m']} m wide). Quick switches isolate wide players."})
        elif them["width_m"] >= 50:
            out.append({"title": "Attack the centre",
                        "detail": f"{on} stretch to {them['width_m']} m wide, leaving the central lane open."})
        feat = [r for r in me["roles"] if r["role"] in FEATURED]
        if feat:
            r = feat[0]
            out.append({"title": f"Use the {r['role'].lower()}",
                        "detail": f"{r['name']} averages {r['x_in']} up the pitch in possession: "
                                  f"keep feeding that overload."})
        return out[:3]

    def _update(self, ev: Event) -> None:
        for c in self.codes:
            prof = self._profile(c)
            if prof:
                self.profiles[c] = prof
        for c in self.codes:
            prof = self.profiles.get(c)
            if not prof:
                continue
            raw = prof["ppda"]  # smooth PPDA across updates so tags do not flicker
            ema = raw if c not in self._ppda else 0.5 * self._ppda[c] + 0.5 * raw
            self._ppda[c] = ema
            prof["ppda"] = round(ema, 1)
            self._retag(prof)
            if c not in self._reported:
                self._reported.add(c)
                self._primary[c] = prof["primary"]
                self._last_shift[c] = ev.t
                self._moments.append({"kind": "tactic_report", "team": c, "player": None, "importance": 0.6,
                                      "facts": {"formation": prof["formation"], "line_height": prof["line_height"],
                                                "ppda": prof["ppda"], "tag": prof["primary"]}})
            elif prof["primary"] != self._primary[c]:
                cand, n = self._tag_pending.get(c, (prof["primary"], 0))
                n = n + 1 if cand == prof["primary"] else 1
                self._tag_pending[c] = (prof["primary"], n)
                if n >= 3 and ev.t - self._last_shift[c] >= 900:
                    self._moments.append({"kind": "tactic_shift", "team": c, "player": None, "importance": 0.6,
                                          "facts": {"prev_tag": self._primary[c], "tag": prof["primary"],
                                                    "line_height": prof["line_height"], "ppda": prof["ppda"]}})
                    self._primary[c] = prof["primary"]
                    self._last_shift[c] = ev.t
                    self._tag_pending.pop(c, None)
            else:
                self._tag_pending.pop(c, None)
            for r in prof["roles"]:
                key = (c, r["name"], r["role"])
                if r["role"] in FEATURED and key not in self._seen_roles:
                    self._seen_roles.add(key)
                    self._moments.append({"kind": "role_reveal", "team": c, "player": r["name"],
                                          "importance": 0.4, "facts": {"role": r["role"].lower(), "x_in": r["x_in"],
                                                                      "y_in": r["y_in"]}})
        for c in self.codes:
            if c in self.profiles:
                self.profiles[c]["options"] = self._options(c)
        self._dirty = True

    # ---- outputs -------------------------------------------------------
    def pop_moments(self) -> List[Dict[str, Any]]:
        out, self._moments = self._moments, []
        return out

    def take_update(self) -> Optional[Dict[str, Any]]:
        if not self._dirty:
            return None
        self._dirty = False
        return {c: dict(p, name=self.names[c]) for c, p in self.profiles.items()}
