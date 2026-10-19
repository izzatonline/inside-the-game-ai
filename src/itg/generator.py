"""Seeded synthetic match generator (football-realistic, no real data).

    python -m itg.generator --seed 7 --out data/match_7.jsonl
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
from typing import Dict, List, Tuple

from .models import Event

# Slots are (out-of-possession xy, in-possession xy) in the team's own attacking frame:
# x 0 = own goal .. 100 = opponent goal, y 0..100 = left..right. Roles are NOT exported:
# the tactics analyzer must infer them from positions alone.
TEAMS: Dict[str, Dict] = {
    "NOR": {
        "name": "Northbridge FC",
        "tactic": {"line": 8.0, "width": 1.0, "press": 0.8, "long": 0.08},  # high line, press, short build-up
        "players": [
            ("Tomas Reyes", "GK"), ("Callum Draper", "DF"), ("Idris Okafor", "DF"),
            ("Mats Lindqvist", "DF"), ("Joao Barreto", "DF"), ("Felix Hartmann", "MF"),
            ("Kofi Mensah", "MF"), ("Luca Ferrante", "MF"), ("Yuto Arakawa", "FW"),
            ("Dario Vukovic", "FW"), ("Jamal Whitfield", "FW"),
        ],
        "slots": [  # 4-3-3: inverted RB, attacking LB, inside-forward RW
            ((5, 50), (14, 50)),
            ((28, 86), (48, 68)), ((22, 62), (30, 62)), ((22, 38), (30, 38)), ((30, 14), (64, 8)),
            ((40, 50), (46, 50)), ((52, 66), (56, 64)), ((52, 34), (66, 38)),
            ((72, 82), (82, 64)), ((82, 50), (88, 50)), ((72, 18), (86, 9)),
        ],
    },
    "HAR": {
        "name": "Harbor City",
        "tactic": {"line": -6.0, "width": 0.95, "press": 0.3, "long": 0.24},  # low block, direct counter
        "players": [
            ("Elias Brandt", "GK"), ("Rui Carvalho", "DF"), ("Owen Maddox", "DF"),
            ("Sami Haddad", "DF"), ("Pedro Salgado", "DF"), ("Niko Petrov", "MF"),
            ("Marcus Bell", "MF"), ("Arjun Nair", "MF"), ("Theo Lambert", "MF"),
            ("Diego Santoro", "MF"), ("Kwame Asante", "FW"),
        ],
        "slots": [  # 4-2-3-1: double pivot, #10, inverted left winger
            ((5, 50), (14, 50)),
            ((26, 86), (46, 84)), ((20, 60), (28, 60)), ((20, 40), (28, 40)), ((26, 14), (46, 16)),
            ((36, 60), (46, 60)), ((36, 40), (48, 40)),
            ((58, 84), (74, 86)), ((58, 50), (70, 50)), ((58, 16), (72, 30)),
            ((74, 50), (86, 50)),
        ],
    },
}

_ZONE_WEIGHTS = {
    "def": {"GK": 1.0, "DF": 6.0, "MF": 3.0, "FW": 0.5},
    "mid": {"GK": 0.1, "DF": 2.0, "MF": 6.0, "FW": 2.0},
    "att": {"GK": 0.0, "DF": 0.5, "MF": 3.0, "FW": 6.0},
}


def _pick(rng: random.Random, team: str, x: float) -> str:
    zone = "def" if x < 35 else "mid" if x < 68 else "att"
    players = TEAMS[team]["players"]
    weights = [_ZONE_WEIGHTS[zone][pos] for _, pos in players]
    return rng.choices([n for n, _ in players], weights=weights)[0]


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _frame_positions(codes, t, poss, bx_rel, by_rel):
    """22 player positions (absolute 0-100 pitch frame; first team attacks +x) around the ball."""
    out = []
    info = {"carrier": 1, "gap": 99.0, "opp_gap": 99.0}
    for c in codes:
        tac, slots = TEAMS[c]["tactic"], TEAMS[c]["slots"]
        has = c == poss
        bx, by = (bx_rel, by_rel) if has else (100 - bx_rel, 100 - by_rel)  # ball in c's frame
        pts = []
        for i, (o, n) in enumerate(slots):
            px, py = n if has else o
            if i == 0:
                px += max(0.0, bx - 50) * 0.1
            else:
                px += tac["line"] * (0.6 if has else 1.0) + (bx - 50) * 0.30
                py = 50 + (py - 50) * tac["width"] + (by - 50) * 0.22
            px += 1.2 * math.sin(t / 9 + i * 1.7)
            py += 1.2 * math.cos(t / 11 + i * 2.3)
            pts.append([px, py])
        def dm(i):
            return math.hypot((pts[i][0] - bx) * 1.05, (pts[i][1] - by) * 0.68)

        near = sorted(range(1, 11), key=dm)
        if has:
            cand = sorted(range(0 if bx < 10 else 1, 11), key=dm)  # the keeper can hold it deep
            info["carrier"], info["gap"] = cand[0], dm(cand[1])
            pts[cand[0]] = [bx, by]
        else:
            for i in near[:2]:  # the pressing pair close the ball down
                k = 0.55 * tac["press"]
                pts[i] = [pts[i][0] + (bx - pts[i][0]) * k, pts[i][1] + (by - pts[i][1]) * k]
            info["opp_gap"] = min(dm(i) for i in range(11))
        for p in pts:
            p[0], p[1] = _clamp(p[0], 1, 99), _clamp(p[1], 1, 99)
        if c != codes[0]:  # away team is shown in the opposite direction
            pts = [[100 - px, 100 - py] for px, py in pts]
        out.extend([round(px, 1), round(py, 1)] for px, py in pts)
    return out, info


def generate_match(seed: int = 7, duration: float = 5400.0, tracking: bool = True) -> List[Event]:
    rng = random.Random(seed)
    codes = list(TEAMS)
    other = {codes[0]: codes[1], codes[1]: codes[0]}
    strength = {c: rng.uniform(0.95, 1.1) for c in codes}
    # Spells where one side dominates: gives the explainer real momentum swings to find.
    phases: List[Tuple[float, float, str]] = []
    for _ in range(4):
        start = rng.uniform(300, duration - 700)
        phases.append((start, start + rng.uniform(360, 600), rng.choice(codes)))

    events: List[Event] = []
    ids = itertools.count(1)

    def emit(t, type_, team, player, x, y, outcome="", **meta):
        events.append(Event(next(ids), round(t, 1), type_, team, player,
                            round(x, 1), round(y, 1), outcome, meta))

    def track(t_, poss_, x_, y_, ph="open", phc=1.0, loose=False):
        """One tracking frame. holder/conf/phase say who has the ball and what kind of play it is;
        conf is lower when the ball is contested, plus a deterministic *simulated* tracker
        occlusion so consumers must handle uncertain frames."""
        if not tracking:
            return
        bx, by = (x_, y_) if poss_ == codes[0] else (100 - x_, 100 - y_)
        pos, info = _frame_positions(codes, t_, poss_, x_, y_)
        occluded = (math.sin(t_ * 12.9898) * 43758.5453) % 1.0 < 0.18
        if loose:
            holder, conf = None, 0.0
        else:
            conf = (_clamp(0.35 + info["opp_gap"] / 5.0, 0.3, 0.98) if ph == "open"
                    else _clamp(0.45 + info["gap"] / 6.0, 0.45, 0.97))
            if occluded:
                conf = min(conf, 0.6)
            holder = [poss_, info["carrier"]]
        emit(t_, "tracking", poss_, "", x_, y_, pos=pos, ball=[round(bx, 1), round(by, 1)], poss=poss_,
             holder=holder, conf=round(conf, 2), phase=ph, phase_conf=phc)

    t, poss, x, y, pressured = 0.0, codes[0], 50.0, 50.0, False
    score = {c: 0 for c in codes}
    emit(0, "kickoff", poss, _pick(rng, poss, 50), 50, 50)
    track(0.0, poss, x, y)

    while True:
        t += rng.uniform(3, 8)
        if t >= duration:
            break
        opp = other[poss]
        boost = {c: 0.45 if any(s <= t < e and tm == c for s, e, tm in phases) else 0.0
                 for c in codes}
        att, dfn = strength[poss] + boost[poss], strength[opp] + boost[opp]
        p_lose = _clamp(0.11 * dfn / att, 0.05, 0.3)
        r = rng.random()
        ph, phc, loose = "open", 1.0, False

        if x >= 72 and rng.random() < 0.09:
            shooter = _pick(rng, poss, x)
            dist = math.hypot((100 - x) * 1.05, (y - 50) * 0.68)
            xg = round(_clamp(0.65 * math.exp(-dist / 11.0) * (att / 1.0) ** 0.5, 0.02, 0.8), 2)
            u = rng.random()
            outcome = ("goal" if u < xg else "saved" if u < xg + 0.28
                       else "blocked" if u < xg + 0.48 else "off_target")
            speed = round(rng.uniform(70, 115), 0)
            if outcome == "goal":
                score[poss] += 1
            emit(t, "shot", poss, shooter, x, y, outcome, xg=xg, speed_kmh=speed,
                 distance_m=round(dist, 1), score=dict(score))
            shooter_team, poss, pressured = poss, opp, False
            if outcome == "goal":
                x = y = 50.0
                emit(t + 40, "kickoff", poss, _pick(rng, poss, 50), 50, 50)
                t += 40
                ph = "kickoff"
            elif outcome == "blocked" and len(events) % 2 == 0:
                # deflected behind: the attackers keep the ball for a corner (touch not certain)
                poss, x, y = shooter_team, 97.0, (4.0 if (len(events) // 2) % 2 else 96.0)
                emit(t, "restart", poss, "", x, y, kind="corner")
                ph, phc = "corner", 0.62
            else:
                x, y = 8.0, 50.0
                emit(t, "possession_change", poss, _pick(rng, poss, 8), x, y, cause="shot_" + outcome)
                if outcome == "off_target":
                    emit(t, "restart", poss, "", x, y, kind="goal_kick")
                    ph, phc = "goal_kick", 0.95
                elif outcome == "saved":
                    ph, phc = "keeper_hold", 0.95
        elif r < p_lose:
            tackler = _pick(rng, opp, 100 - x)
            kind = "tackle" if rng.random() < 0.6 else "interception"
            emit(t, kind, opp, tackler, 100 - x, 100 - y, "won")
            poss, x, y, pressured = opp, 100 - x, 100 - y, False
            emit(t, "possession_change", poss, tackler, x, y, cause=kind)
            loose = True  # the ball is up for grabs for a moment
        elif r < p_lose + 0.12 * (0.4 + TEAMS[opp]["tactic"]["press"]):
            emit(t, "pressure", opp, _pick(rng, opp, 100 - x), 100 - x, 100 - y,
                 intensity=round(rng.uniform(0.3, 1.0), 2))
            pressured = True
        elif rng.random() < 0.15:
            carrier = _pick(rng, poss, x)
            dx = _clamp(rng.gauss(6, 4), 0, 20)
            speed = round(_clamp(rng.gauss(24, 5), 12, 36), 1)
            emit(t, "carry", poss, carrier, x, y, "", speed_kmh=speed,
                 distance_m=round(dx * 1.05, 1))
            x = _clamp(x + dx, 2, 98)
        else:
            passer = _pick(rng, poss, x)
            dx = rng.gauss(26, 8) if rng.random() < TEAMS[poss]["tactic"]["long"] else rng.gauss(8, 9)
            nx, ny = _clamp(x + dx, 2, 98), _clamp(y + rng.gauss(0, 14), 4, 96)
            dist = math.hypot((nx - x) * 1.05, (ny - y) * 0.68)
            difficulty = _clamp(0.1 + dist / 60 + (0.25 if pressured else 0)
                                + (0.15 if nx > 70 else 0), 0, 1)
            p_ok = _clamp(1.0 - difficulty * 0.4 + (strength[poss] - 1) * 0.2, 0.2, 0.97)
            receiver = _pick(rng, poss, nx)
            ok = rng.random() < p_ok
            emit(t, "pass", poss, passer, x, y, "complete" if ok else "incomplete",
                 receiver=receiver, distance_m=round(dist, 1), difficulty=round(difficulty, 2),
                 speed_kmh=round(rng.uniform(35, 75) if dist > 20 else rng.uniform(20, 45), 0))
            if ok:
                x, y = nx, ny
            elif ny < 7 or ny > 93:  # ran out over the touchline: throw-in to the other side
                poss, x, y = opp, 100 - nx, (97.0 if ny < 50 else 3.0)
                emit(t, "possession_change", poss, "", x, y, cause="out_of_play")
                emit(t, "restart", poss, "", x, y, kind="throw_in")
                ph, phc = "throw_in", 0.92
            else:
                poss, x, y = opp, 100 - nx, 100 - ny
                emit(t, "possession_change", poss, _pick(rng, poss, x), x, y, cause="turnover")
            pressured = False
        track(t, poss, x, y, ph, phc, loose)

    emit(duration, "fulltime", poss, "", x, y, score=dict(score))
    return events


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a synthetic match as JSONL")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="-")
    a = ap.parse_args()
    lines = "\n".join(json.dumps(e.to_dict()) for e in generate_match(a.seed))
    if a.out == "-":
        print(lines)
    else:
        with open(a.out, "w") as f:
            f.write(lines + "\n")


if __name__ == "__main__":
    main()
