"""Seeded synthetic match generator (football-realistic, no real data).

    python -m itg.generator --seed 7 --out data/match_7.jsonl
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .models import Event

# Slots are (out-of-possession xy, in-possession xy) in the team's own attacking frame:
# x 0 = own goal .. 100 = opponent goal, y 0..100 = left..right. Roles are NOT exported:
# the tactics analyzer must infer them from positions alone.
_COASTAL_TEAMS: Dict[str, Dict] = {
    "NOR": {
        "name": "Northbridge FC", "color": "#38bdf8",
        "formation": "4-3-3",
        "tactic": {"line": 8.0, "width": 1.0, "press": 0.8, "long": 0.08},  # high line, press, short build-up
        "staff": {
            "coach": "Marco Villanueva", "assistants": ["Lena Voss", "Tariq Aziz"],
            "subs": [("Pieter Jansen", "GK", 31), ("Ravi Menon", "DF", 15), ("Oskar Berg", "DF", 24),
                     ("Hugo Marin", "MF", 16), ("Sione Tuilagi", "MF", 18), ("Amadou Keita", "MF", 21),
                     ("Nico Valente", "FW", 19), ("Bruno Teles", "FW", 99), ("Jonas Eklund", "FW", 20)],
        },
        "players": [
            ("Adrian Wong", "GK"), ("Callum Draper", "DF"), ("Idris Okafor", "DF"),
            ("Mats Lindqvist", "DF"), ("Itadori Yuji", "DF"), ("Afeef Rayan", "MF"),
            ("Kofi Mensah", "MF"), ("Izzat Jamal", "MF"), ("Umayr Ziyad", "FW"),
            ("Wafi Shaik", "FW"), ("Tungtung Sahur", "FW"),
        ],
        "numbers": [1, 2, 23, 4, 3, 6, 14, 8, 7, 9, 37],
        "slots": [  # 4-3-3: inverted RB, attacking LB, inside-forward RW
            ((5, 50), (14, 50)),
            ((28, 86), (48, 68)), ((22, 62), (30, 62)), ((22, 38), (30, 38)), ((30, 14), (64, 8)),
            ((40, 50), (46, 50)), ((52, 66), (56, 64)), ((52, 34), (66, 38)),
            ((72, 82), (82, 64)), ((82, 50), (88, 50)), ((72, 18), (86, 9)),
        ],
    },
    "HAR": {
        "name": "Harbor City", "color": "#f43f5e",
        "formation": "4-2-3-1",
        "tactic": {"line": -6.0, "width": 0.95, "press": 0.3, "long": 0.24},  # low block, direct counter
        "staff": {
            "coach": "Elena Rostova", "assistants": ["Gareth Pugh", "Imani Okoye"],
            "subs": [("Davi Moreira", "GK", 25), ("Kasper Lund", "DF", 13), ("Yusuf Demir", "DF", 15),
                     ("Felipe Rojas", "MF", 22), ("Anton Kovac", "MF", 16), ("Mateo Silva", "MF", 20),
                     ("Isaac Boateng", "FW", 18), ("Leo Fontaine", "FW", 29), ("Ciaran Doyle", "FW", 77)],
        },
        "players": [
            ("Elias Brandt", "GK"), ("Rui Carvalho", "DF"), ("Owen Maddox", "DF"),
            ("Sami Haddad", "DF"), ("Pedro Salgado", "DF"), ("Niko Petrov", "MF"),
            ("Marcus Bell", "MF"), ("Arjun Nair", "MF"), ("Theo Lambert", "MF"),
            ("Diego Santoro", "MF"), ("Kwame Asante", "FW"),
        ],
        "numbers": [1, 2, 4, 5, 3, 6, 8, 10, 7, 11, 19],
        "slots": [  # 4-2-3-1: double pivot, #10, inverted left winger
            ((5, 50), (14, 50)),
            ((26, 86), (46, 84)), ((20, 60), (28, 60)), ((20, 40), (28, 40)), ((26, 14), (46, 16)),
            ((36, 60), (46, 60)), ((36, 40), (48, 40)),
            ((58, 84), (74, 86)), ((58, 50), (70, 50)), ((58, 16), (72, 30)),
            ((74, 50), (86, 50)),
        ],
    },
}



@dataclass
class MatchSpec:
    """A simulated match: its two clubs plus (optionally) a scripted storyline."""

    id: str
    title: str
    subtitle: str
    blurb: str
    teams: Dict[str, Dict]
    duration: float = 5400.0
    scenario: Optional[Dict[str, Any]] = None
    stadium: str = ""  # home ground (the first-listed team is the home side)
    referee: Dict[str, Any] = field(default_factory=lambda: {"name": "Sam Whitlock", "assistants": ["Pia Norland", "Gus Ferreira"], "var": "Lena Okonkwo"})


MATCHES: Dict[str, MatchSpec] = {}
MATCHES["coastal"] = MatchSpec(
    "coastal", "Coastal Derby", "Seaview Park · 90 min", "Open game, shape battle: high press v low block",
    _COASTAL_TEAMS)
MATCHES["coastal"].stadium = "Seaview Park"
DEFAULT_MATCH = "coastal"
TEAMS = MATCHES[DEFAULT_MATCH].teams  # default match, kept for existing callers


_RIVERSIDE_TEAMS: Dict[str, Dict] = {
    "MER": {
        "name": "Meridian FC", "color": "#a78bfa",
        "formation": "4-1-4-1",
        "tactic": {"line": 10.0, "width": 1.05, "press": 0.9, "long": 0.05},  # dominant, high line, short passing
        "staff": {
            "coach": "Conrad Whitlock", "assistants": ["Bruno Esteves", "Yelena Marsh"],
            "subs": [("Ben Hargrove", "GK", 31), ("Luis Mancera", "DF", 12), ("Niklas Aalto", "DF", 15),
                     ("Oren Sasson", "MF", 18), ("Ruben Calvet", "MF", 16), ("Anil Prakash", "MF", 21),
                     ("Theo Marquand", "FW", 11), ("Felix Lorenz", "FW", 19), ("Dmitri Kasim", "FW", 99)],
        },
        "players": [
            ("Idris Calloway", "GK"), ("Tomas Varga", "DF"), ("Emeka Obi", "DF"), ("Rafael Quintero", "DF"),
            ("Soren Lindahl", "DF"), ("Kofi Danso", "MF"), ("Mattias Holm", "MF"), ("Dario Ferrucci", "MF"),
            ("Yusuf Karaca", "MF"), ("Jamie Rutherford", "MF"), ("Casper Wolfe", "FW"),
        ],
        "numbers": [1, 2, 4, 5, 3, 6, 8, 10, 14, 7, 9],
        "slots": [  # 4-1-4-1
            ((5, 50), (16, 50)),
            ((30, 86), (52, 84)), ((24, 62), (34, 62)), ((24, 38), (34, 38)), ((30, 14), (52, 16)),
            ((40, 50), (48, 50)),
            ((62, 86), (78, 88)), ((56, 62), (66, 60)), ((56, 38), (66, 40)), ((62, 14), (78, 12)),
            ((78, 50), (88, 50)),
        ],
    },
    "TID": {
        "name": "Tidewater Town", "color": "#fbbf24",
        "formation": "5-4-1",
        "tactic": {"line": -12.0, "width": 1.0, "press": 0.25, "long": 0.32},  # deep five-man block, long counters
        "staff": {
            "coach": "Hamish Dunleavy", "assistants": ["Rory Quill", "Ines Barros"],
            "subs": [("Oscar Fenwick", "GK", 1), ("Piers Garrow", "DF", 12), ("Linus Halloran", "DF", 16),
                     ("Azim Rahal", "MF", 17), ("Abel Okoro", "MF", 14), ("Cormac Reyes", "MF", 21),
                     ("Gideon Pryce", "FW", 22), ("Leo Marchetti", "FW", 11), ("Jory Bates", "FW", 27)],
        },
        "players": [
            ("Walter Penhale", "GK"), ("Callum Ashby", "DF"), ("Isaac Thorne", "DF"), ("Marcus Bellweather", "DF"),
            ("Declan Rudd", "DF"), ("Ellis Cartmel", "DF"), ("Tobias Wren", "MF"), ("Nolan Pike", "MF"),
            ("Dominic Hale", "MF"), ("Harlan Voss", "MF"), ("Rory Blackwood", "FW"),
        ],
        "numbers": [13, 2, 4, 5, 3, 15, 6, 8, 20, 10, 9],
        "slots": [  # 5-4-1
            ((5, 50), (12, 50)),
            ((26, 90), (46, 88)), ((20, 68), (26, 66)), ((18, 50), (24, 50)), ((20, 32), (26, 34)), ((26, 10), (46, 12)),
            ((40, 78), (52, 76)), ((38, 58), (46, 56)), ((38, 42), (46, 44)), ((40, 22), (52, 24)),
            ((58, 50), (66, 50)),
        ],
    },
}

# Inspired by a real-world storyline (a dominant side, an early equaliser, a disallowed goal and a late penalty)
# but with invented clubs, players and venue, and shifted minutes. Everything here is synthetic.
_M = 60.0
MATCHES["riverside"] = MatchSpec(
    "riverside", "Riverside Cup Tie", "Riverside Arena · 90+9", "Total control, a VAR drama and a late penalty",
    _RIVERSIDE_TEAMS, duration=99 * _M,
    referee={"name": "Marta Quill", "assistants": ["Owen Harlan", "Dev Rao"], "var": "Jon Ashby"},
    scenario={
        "strength": {"MER": 1.5, "TID": 0.78},
        "shot_rate": 0.03,
        "script": [
            {"t": 17 * _M + 20, "do": "goal", "team": "MER", "scorer": "Jamie Rutherford", "assist": "Mattias Holm", "xg": 0.34},
            {"t": 24 * _M + 10, "do": "goal", "team": "TID", "scorer": "Tobias Wren", "assist": "Callum Ashby", "xg": 0.22},
            {"t": 36 * _M + 40, "do": "goal", "team": "MER", "scorer": "Casper Wolfe", "assist": "Dario Ferrucci", "xg": 0.41},
            {"t": 66 * _M + 30, "do": "goal", "team": "MER", "scorer": "Casper Wolfe", "assist": "Jamie Rutherford", "xg": 0.52},
            {"t": 72 * _M, "do": "card", "team": "TID", "player": "Callum Ashby"},
            {"t": 84 * _M + 50, "do": "disallowed", "team": "MER", "scorer": "Casper Wolfe", "assist": "Dario Ferrucci", "xg": 0.45, "reason": "offside"},
            {"t": 87 * _M + 30, "do": "penalty", "team": "TID", "taker": "Gideon Pryce", "fouler": "Rafael Quintero"},
            {"t": 93 * _M, "do": "card", "team": "MER", "player": "Rafael Quintero"},
            {"t": 97 * _M + 30, "do": "card", "team": "TID", "player": "Isaac Thorne"},
        ],
        "subs": [
            (50, "MER", "Yusuf Karaca", "Oren Sasson"), (61, "MER", "Soren Lindahl", "Niklas Aalto"),
            (77, "MER", "Mattias Holm", "Theo Marquand"), (77, "MER", "Jamie Rutherford", "Felix Lorenz"),
            (77, "MER", "Tomas Varga", "Luis Mancera"),
            (70, "TID", "Harlan Voss", "Abel Okoro"), (70, "TID", "Nolan Pike", "Azim Rahal"),
            (77, "TID", "Rory Blackwood", "Gideon Pryce"), (77, "TID", "Tobias Wren", "Leo Marchetti"),
            (91, "TID", "Marcus Bellweather", "Piers Garrow"),
        ],
    })


_REDCREST_TEAMS: Dict[str, Dict] = {
    "RED": {
        "name": "Redcrest United", "color": "#ef4444",
        "formation": "3-4-2-1",
        "tactic": {"line": 4.0, "width": 1.0, "press": 0.6, "long": 0.12},  # wing-backs, possession with width
        "staff": {
            "coach": "Ansel Whitcombe", "assistants": ["Ruta Kalnins", "Desmond Pryor"],
            "subs": [("Tobias Lund", "GK", 22), ("Idan Barak", "DF", 3), ("Corin Ashdown", "DF", 12),
                     ("Mateo Ibanez", "MF", 15), ("Kwesi Tetteh", "MF", 16), ("Rune Halvorsen", "MF", 18),
                     ("Zane Okafor", "FW", 11), ("Felipe Marsh", "FW", 19), ("Hollis Crane", "FW", 99)],
        },
        "players": [
            ("Hugo Mertens", "GK"), ("Callan Brooks", "DF"), ("Anselm Dreyer", "DF"), ("Rafe Holloway", "DF"),
            ("Mateus Duarte", "MF"), ("Kelvin Osei", "MF"), ("Joaquin Vidal", "MF"), ("Pascal Roux", "MF"),
            ("Teodor Falk", "MF"), ("Rhys Penmark", "MF"), ("Emil Sandoval", "FW"),
        ],
        "numbers": [1, 2, 4, 5, 6, 8, 10, 14, 7, 17, 9],
        "slots": [  # 3-4-2-1
            ((5, 50), (14, 50)),
            ((22, 70), (30, 70)), ((20, 50), (28, 50)), ((22, 30), (30, 30)),
            ((42, 92), (64, 92)), ((42, 8), (64, 8)), ((38, 58), (48, 58)), ((38, 42), (48, 42)),
            ((60, 66), (74, 66)), ((60, 34), (74, 34)),
            ((78, 50), (88, 50)),
        ],
    },
    "KES": {
        "name": "Kestrel Town", "color": "#2dd4bf",
        "formation": "4-4-2",
        "tactic": {"line": -6.0, "width": 1.0, "press": 0.35, "long": 0.22},  # compact 4-4-2, quick breaks
        "staff": {
            "coach": "Gavin Harrowgate", "assistants": ["Pia Santoro", "Neil Tranter"],
            "subs": [("Cass Dunmore", "GK", 1), ("Elliott Rae", "DF", 12), ("Marek Zielinski", "DF", 14),
                     ("Dev Anand", "MF", 15), ("Louis Perrault", "MF", 16), ("Gabe Sinclair", "MF", 21),
                     ("Wes Calloway", "FW", 17), ("Ike Nwosu", "FW", 19), ("Bram Voorhees", "FW", 88)],
        },
        "players": [
            ("Ivor Teasdale", "GK"), ("Cormac Leighton", "DF"), ("Lucan Marsh", "DF"), ("Dorian Ashcroft", "DF"),
            ("Evan Hartley", "DF"), ("Nasir Bello", "MF"), ("Tomasz Wrobel", "MF"), ("Jarek Lindgren", "MF"),
            ("Pablo Ibarra", "MF"), ("Corbin Vale", "FW"), ("Emerson Lyle", "FW"),
        ],
        "numbers": [30, 2, 3, 4, 5, 6, 8, 10, 7, 9, 11],
        "slots": [  # 4-4-2
            ((5, 50), (12, 50)),
            ((28, 86), (44, 84)), ((20, 62), (26, 62)), ((20, 38), (26, 38)), ((28, 14), (44, 16)),
            ((42, 82), (54, 80)), ((38, 60), (46, 58)), ((38, 40), (46, 42)), ((42, 18), (54, 20)),
            ((62, 58), (70, 58)), ((60, 42), (68, 42)),
        ],
    },
}

# Inspired by a second real-world storyline the user supplied (an early shock, an equaliser, an own goal,
# a penalty and a late consolation) with invented clubs, players and venue, and shifted minutes.
MATCHES["redcrest"] = MatchSpec(
    "redcrest", "Redcrest Rain Night", "Redcrest Park · 90+9", "An early shock, a fightback and a goal flurry",
    _REDCREST_TEAMS, duration=99 * _M,
    referee={"name": "Tobias Renner", "assistants": ["Yara Lindgren", "Cal Brennan"], "var": "Ines Duarte"},
    scenario={
        "strength": {"RED": 1.22, "KES": 0.92},
        "shot_rate": 0.05,
        "script": [
            {"t": 28 * _M + 40, "do": "goal", "team": "KES", "scorer": "Evan Hartley", "assist": "Nasir Bello", "xg": 0.18},
            {"t": 33 * _M, "do": "card", "team": "KES", "player": "Tomasz Wrobel"},
            {"t": 37 * _M + 10, "do": "card", "team": "KES", "player": "Nasir Bello"},
            {"t": 41 * _M + 10, "do": "goal", "team": "RED", "scorer": "Pascal Roux", "assist": "Rhys Penmark", "xg": 0.27},
            {"t": 55 * _M + 30, "do": "own_goal", "team": "RED", "culprit": "Lucan Marsh", "var": True},
            {"t": 58 * _M + 50, "do": "penalty", "team": "RED", "taker": "Pascal Roux", "fouler": "Dorian Ashcroft", "var": False},
            {"t": 60 * _M + 20, "do": "card", "team": "KES", "player": "Dorian Ashcroft"},
            {"t": 67 * _M + 30, "do": "goal", "team": "RED", "scorer": "Pascal Roux", "xg": 0.62},
            {"t": 81 * _M + 40, "do": "goal", "team": "RED", "scorer": "Teodor Falk", "assist": "Pascal Roux", "xg": 0.30},
            {"t": 90 * _M + 50, "do": "goal", "team": "KES", "scorer": "Wes Calloway", "assist": "Pablo Ibarra", "xg": 0.58},
            {"t": 93 * _M, "do": "card", "team": "RED", "player": "Teodor Falk"},
        ],
        "subs": [
            (46, "KES", "Emerson Lyle", "Wes Calloway"), (62, "KES", "Jarek Lindgren", "Dev Anand"),
            (73, "KES", "Tomasz Wrobel", "Louis Perrault"), (73, "KES", "Pablo Ibarra", "Gabe Sinclair"),
            (83, "KES", "Nasir Bello", "Ike Nwosu"),
            (73, "RED", "Callan Brooks", "Corin Ashdown"), (74, "RED", "Kelvin Osei", "Idan Barak"),
            (80, "RED", "Rhys Penmark", "Zane Okafor"), (80, "RED", "Teodor Falk", "Mateo Ibanez"),
            (80, "RED", "Joaquin Vidal", "Kwesi Tetteh"),
        ],
    })


_ZONE_WEIGHTS = {
    "def": {"GK": 1.0, "DF": 6.0, "MF": 3.0, "FW": 0.5},
    "mid": {"GK": 0.1, "DF": 2.0, "MF": 6.0, "FW": 2.0},
    "att": {"GK": 0.0, "DF": 0.5, "MF": 3.0, "FW": 6.0},
}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _kickoff_shape(pos, kicker_team: int, carrier: int):
    """Kick-off: every player in their own half (team 0 on the left, team 1 on the right), only the taker at the
    centre spot and the opponents outside the centre circle. Each team keeps its own relative line order and width,
    stretched over its half (keeper deep, outfield between 14 and 40)."""
    out = [None] * 22
    for t in (0, 1):
        idx = range(t * 11, t * 11 + 11)
        rel = {i: (pos[i][0] if t == 0 else 100 - pos[i][0]) for i in idx}  # distance from own goal line
        lo, hi = min(rel[i] for i in idx if i % 11), max(rel[i] for i in idx if i % 11)
        for i in idx:
            d = 4.5 if i % 11 == 0 else 14 + (rel[i] - lo) / max(hi - lo, 1e-6) * 26
            out[i] = [round(d if t == 0 else 100 - d, 1), pos[i][1]]
    out[kicker_team * 11 + carrier] = [49.8 if kicker_team == 0 else 50.2, 50.0]
    return out


def _frame_positions(codes, t, poss, bx_rel, by_rel, teams, forced_carrier=None):
    """22 player positions (absolute 0-100 pitch frame; first team attacks +x) around the ball."""
    out = []
    info = {"carrier": 1, "gap": 99.0, "opp_gap": 99.0}
    for c in codes:
        tac, slots = teams[c]["tactic"], teams[c]["slots"]
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
            carrier = cand[0] if forced_carrier is None else forced_carrier  # scripted takers are known
            info["carrier"], info["gap"] = carrier, dm(next(i for i in cand if i != carrier))
            pts[carrier] = [bx, by]
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


def generate_match(seed: int = 7, duration: Optional[float] = None, tracking: bool = True,
                   match: str = DEFAULT_MATCH) -> List[Event]:
    spec = MATCHES[match]
    teams, scen = spec.teams, spec.scenario
    duration = duration or spec.duration
    rng = random.Random(seed)
    codes = list(teams)
    other = {codes[0]: codes[1], codes[1]: codes[0]}
    strength = {c: rng.uniform(0.95, 1.1) for c in codes}
    if scen:
        strength.update(scen.get("strength", {}))
    # Spells where one side dominates: gives the explainer real momentum swings to find.
    phases: List[Tuple[float, float, str]] = []
    for _ in range(4):
        start = rng.uniform(300, duration - 700)
        phases.append((start, start + rng.uniform(360, 600), rng.choice(codes)))

    events: List[Event] = []
    ids = itertools.count(1)
    roster = {c: list(teams[c]["players"]) for c in codes}  # changes when substitutions happen

    def pick(team: str, x: float) -> str:
        zone = "def" if x < 35 else "mid" if x < 68 else "att"
        players = roster[team]
        weights = [_ZONE_WEIGHTS[zone][pos] for _, pos in players]
        return rng.choices([n for n, _ in players], weights=weights)[0]

    # Bench plan from a separate RNG so the match itself is unchanged: 3 subs per team, warm-up 2.5 min before.
    plan = []
    brng = random.Random(seed * 7919 + 13)
    if scen and scen.get("subs"):
        for minute, c, out_name, in_name in scen["subs"]:
            slot = next(i for i, (n, _) in enumerate(teams[c]["players"]) if n == out_name)
            idx = next(i for i, sb in enumerate(teams[c]["staff"]["subs"]) if sb[0] == in_name)
            plan.append((minute * 60.0 - 150, "warmup", c, slot, idx))
            plan.append((minute * 60.0, "substitution", c, slot, idx))
    for c in ([] if scen and scen.get("subs") else codes):
        subs = teams[c]["staff"]["subs"]
        free = list(range(len(subs)))
        for slot, minute in zip(brng.sample(range(1, 11), 3), sorted(brng.sample(range(58, 84), 3))):
            pos = teams[c]["players"][slot][1]
            idx = next((i for i in free if subs[i][1] == pos), next(i for i in free if subs[i][1] != "GK"))
            free.remove(idx)
            when = minute * 60.0 + brng.uniform(0, 50)
            plan.append((when - 150, "warmup", c, slot, idx))
            plan.append((when, "substitution", c, slot, idx))
    plan.sort()

    def emit(t, type_, team, player, x, y, outcome="", **meta):
        events.append(Event(next(ids), round(t, 1), type_, team, player,
                            round(x, 1), round(y, 1), outcome, meta))

    def slot_of(team: str, name: str) -> Optional[int]:
        return next((i for i, (n, _) in enumerate(roster[team]) if n == name), None)

    def track(t_, poss_, x_, y_, ph="open", phc=1.0, loose=False, taker=None):
        """One tracking frame. holder/conf/phase say who has the ball and what kind of play it is;
        conf is lower when the ball is contested, plus a deterministic *simulated* tracker
        occlusion so consumers must handle uncertain frames."""
        if not tracking:
            return
        bx, by = (x_, y_) if poss_ == codes[0] else (100 - x_, 100 - y_)
        pos, info = _frame_positions(codes, t_, poss_, x_, y_, teams,
                                     slot_of(poss_, taker) if taker else None)
        if ph == "kickoff" or t_ == 0.0:  # restarts from the centre: teams start in their own halves
            pos = _kickoff_shape(pos, codes.index(poss_), info["carrier"])
        elif ph in ("throw_in", "corner"):  # the taker stands just outside the line, the ball sits on it
            k = codes.index(poss_) * 11 + info["carrier"]
            pos[k] = ([bx, -2.0 if by < 50 else 102.0] if ph == "throw_in"
                      else [bx + (1.6 if bx > 50 else -1.6), by + (-2.0 if by < 50 else 2.0)])
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
    emit(0, "kickoff", poss, pick(poss, 50), 50, 50)
    track(0.0, poss, x, y)

    script = sorted(scen["script"], key=lambda d: d["t"]) if scen else []

    def run_script(item):
        """Scripted storyline beats (goals, VAR, penalty, cards). Random play never scores in these matches."""
        nonlocal t, poss, x, y, pressured
        kind, att, tt = item["do"], item["team"], item["t"]
        if kind == "own_goal":  # att is the side that benefits; the culprit plays for the other side
            score[att] += 1
            emit(tt, "own_goal", att, item["culprit"], 90, 50, score=dict(score), against=other[att])
            track(tt, att, 90, 50)
            if item.get("var"):
                emit(tt + 2, "var", att, item["culprit"], 90, 50, kind="goal_check")
                emit(tt + 40, "var", att, item["culprit"], 90, 50, kind="goal_stands")
                tt += 40
            poss, x, y = other[att], 50.0, 50.0
            emit(tt + 40, "kickoff", poss, pick(poss, 50), 50, 50)
            t = tt + 40
            track(t, poss, x, y, "kickoff")
        elif kind in ("goal", "disallowed"):
            if item.get("assist"):
                emit(tt - 3, "pass", att, item["assist"], 72, 52, "complete", receiver=item["scorer"],
                     distance_m=24.0, difficulty=0.55, speed_kmh=55)
            if kind == "goal":
                score[att] += 1
            emit(tt, "shot", att, item["scorer"], 88, 50, "goal" if kind == "goal" else "disallowed", xg=item["xg"],
                 speed_kmh=item.get("speed", 90), distance_m=11.0, score=dict(score))
            track(tt, att, 88, 50, taker=item["scorer"])
            if kind == "goal":
                poss, x, y = other[att], 50.0, 50.0
                emit(tt + 40, "kickoff", poss, pick(poss, 50), 50, 50)
                t = tt + 40
                track(t, poss, x, y, "kickoff")
            else:  # VAR rules it out: free kick to the defenders
                emit(tt + 2, "var", att, item["scorer"], 88, 50, kind="goal_check")
                emit(tt + 42, "var", att, item["scorer"], 88, 50, kind="no_goal", reason=item.get("reason", "offside"))
                poss, x, y = other[att], 20.0, 50.0
                emit(tt + 60, "restart", poss, "", x, y, kind="free_kick")
                t = tt + 60
                track(t, poss, x, y)
        elif kind == "penalty":
            emit(tt, "foul", other[att], item["fouler"], 15, 50, against=att, penalty=True)
            if item.get("var", True):
                emit(tt + 4, "var", att, item["taker"], 88, 50, kind="penalty_check")
                emit(tt + 60, "var", att, item["taker"], 88, 50, kind="penalty_awarded")
            emit(tt + 80, "restart", att, "", 88, 50, kind="penalty")
            for k in range(3):
                track(tt + 85 + k * 3, att, 88, 50, "penalty", 0.97, taker=item["taker"])
            score[att] += 1
            emit(tt + 95, "shot", att, item["taker"], 88, 50, "goal", xg=0.76, speed_kmh=96, distance_m=11.0,
                 penalty=True, score=dict(score))
            track(tt + 96, att, 88, 50, taker=item["taker"])
            poss, x, y = other[att], 50.0, 50.0
            emit(tt + 135, "kickoff", poss, pick(poss, 50), 50, 50)
            t = tt + 135
            track(t, poss, x, y, "kickoff")
        elif kind == "card":
            emit(tt, "card", att, item["player"], 40, 50, card="yellow")
        pressured = False

    while True:
        t += rng.uniform(3, 8)
        if t >= duration:
            break
        while plan and plan[0][0] <= t:
            when, kind, c, slot, idx = plan.pop(0)
            sub_name, sub_pos, number = teams[c]["staff"]["subs"][idx]
            if kind == "warmup":
                emit(when, "warmup", c, sub_name, 50, 50, sub_idx=idx, slot=slot, number=number)
            else:
                out_name = roster[c][slot][0]
                roster[c][slot] = (sub_name, sub_pos)
                emit(when, "substitution", c, sub_name, 50, 50, sub_idx=idx, slot=slot, number=number, player_out=out_name)
        while script and script[0]["t"] <= t:
            run_script(script.pop(0))
        opp = other[poss]
        boost = {c: 0.45 if any(s <= t < e and tm == c for s, e, tm in phases) else 0.0
                 for c in codes}
        att, dfn = strength[poss] + boost[poss], strength[opp] + boost[opp]
        p_lose = _clamp(0.11 * dfn / att, 0.05, 0.3)
        r = rng.random()
        ph, phc, loose = "open", 1.0, False

        if x >= 72 and rng.random() < (scen.get("shot_rate", 0.09) if scen else 0.09):
            shooter = pick(poss, x)
            dist = math.hypot((100 - x) * 1.05, (y - 50) * 0.68)
            xg = round(_clamp(0.65 * math.exp(-dist / 11.0) * ((min(att, 1.1) if scen else att) / 1.0) ** 0.5, 0.02, 0.8), 2)
            u = rng.random()
            outcome = ("goal" if (u < xg and not scen) else "saved" if u < xg + 0.28
                       else "blocked" if u < xg + 0.48 else "off_target")
            speed = round(rng.uniform(70, 115), 0)
            if outcome == "goal":
                score[poss] += 1
            emit(t, "shot", poss, shooter, x, y, outcome, xg=xg, speed_kmh=speed,
                 distance_m=round(dist, 1), score=dict(score))
            shooter_team, poss, pressured = poss, opp, False
            if outcome == "goal":
                x = y = 50.0
                emit(t + 40, "kickoff", poss, pick(poss, 50), 50, 50)
                t += 40
                ph = "kickoff"
            elif outcome == "blocked" and len(events) % 2 == 0:
                # deflected behind: the attackers keep the ball for a corner (touch not certain)
                poss, x, y = shooter_team, 100.0, (0.0 if (len(events) // 2) % 2 else 100.0)  # in the corner
                emit(t, "restart", poss, "", x, y, kind="corner")
                ph, phc = "corner", 0.62
            else:
                x, y = 8.0, 50.0
                emit(t, "possession_change", poss, pick(poss, 8), x, y, cause="shot_" + outcome)
                if outcome == "off_target":
                    emit(t, "restart", poss, "", x, y, kind="goal_kick")
                    ph, phc = "goal_kick", 0.95
                elif outcome == "saved":
                    ph, phc = "keeper_hold", 0.95
        elif r < p_lose:
            tackler = pick(opp, 100 - x)
            kind = "tackle" if rng.random() < 0.6 else "interception"
            emit(t, kind, opp, tackler, 100 - x, 100 - y, "won")
            poss, x, y, pressured = opp, 100 - x, 100 - y, False
            emit(t, "possession_change", poss, tackler, x, y, cause=kind)
            loose = True  # the ball is up for grabs for a moment
        elif r < p_lose + 0.12 * (0.4 + teams[opp]["tactic"]["press"]):
            emit(t, "pressure", opp, pick(opp, 100 - x), 100 - x, 100 - y,
                 intensity=round(rng.uniform(0.3, 1.0), 2))
            pressured = True
        elif rng.random() < 0.15:
            carrier = pick(poss, x)
            dx = _clamp(rng.gauss(6, 4), 0, 20)
            speed = round(_clamp(rng.gauss(24, 5), 12, 36), 1)
            emit(t, "carry", poss, carrier, x, y, "", speed_kmh=speed,
                 distance_m=round(dx * 1.05, 1))
            x = _clamp(x + dx, 2, 98)
        else:
            passer = pick(poss, x)
            dx = rng.gauss(26, 8) if rng.random() < teams[poss]["tactic"]["long"] else rng.gauss(8, 9)
            nx, ny = _clamp(x + dx, 2, 98), _clamp(y + rng.gauss(0, 14), 4, 96)
            dist = math.hypot((nx - x) * 1.05, (ny - y) * 0.68)
            difficulty = _clamp(0.1 + dist / 60 + (0.25 if pressured else 0)
                                + (0.15 if nx > 70 else 0), 0, 1)
            p_ok = _clamp(1.0 - difficulty * 0.4 + (strength[poss] - 1) * 0.2, 0.2, 0.97)
            receiver = pick(poss, nx)
            ok = rng.random() < p_ok
            emit(t, "pass", poss, passer, x, y, "complete" if ok else "incomplete",
                 receiver=receiver, distance_m=round(dist, 1), difficulty=round(difficulty, 2), ex=round(nx, 1), ey=round(ny, 1),
                 speed_kmh=round(rng.uniform(35, 75) if dist > 20 else rng.uniform(20, 45), 0))
            if ok:
                x, y = nx, ny
            elif ny < 7 or ny > 93:  # ran out over the touchline: throw-in to the other side
                poss, x, y = opp, 100 - nx, (100.0 if ny < 50 else 0.0)  # on the touchline
                emit(t, "possession_change", poss, "", x, y, cause="out_of_play")
                emit(t, "restart", poss, "", x, y, kind="throw_in")
                ph, phc = "throw_in", 0.92
            else:
                poss, x, y = opp, 100 - nx, 100 - ny
                emit(t, "possession_change", poss, pick(poss, x), x, y, cause="turnover")
            pressured = False
        track(t, poss, x, y, ph, phc, loose)

    # Discipline layer from its own RNG so the match flow above is untouched: some pressure events are
    # fouls (free kick to the other side, occasionally a yellow card) and some failed final-third passes offside.
    frng = random.Random(seed * 104729 + 7)
    yellows = {c: 0 for c in codes}
    for e in list(events):
        if e.type == "pressure" and frng.random() < 0.22:
            emit(e.t, "foul", e.team, e.player, e.x, e.y, against=other[e.team])
            emit(e.t + 0.1, "restart", other[e.team], "", 100 - e.x, 100 - e.y, kind="free_kick")
            if frng.random() < 0.13 and yellows[e.team] < 4 and not scen:
                yellows[e.team] += 1
                emit(e.t + 0.2, "card", e.team, e.player, e.x, e.y, card="yellow")
        elif e.type == "pass" and e.outcome == "incomplete" and e.x >= 62 and frng.random() < 0.09:
            emit(e.t, "offside", e.team, e.meta.get("receiver", ""), e.x, e.y)

    emit(duration, "fulltime", poss, "", x, y, score=dict(score))
    events.sort(key=lambda ev: (ev.t, ev.id))
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

MATCHES["riverside"].stadium = "Riverside Arena"
MATCHES["redcrest"].stadium = "Redcrest Park"
