"""Seeded synthetic match generator (football-realistic, no real data).

    python -m itg.generator --seed 7 --out data/match_7.jsonl
"""
from __future__ import annotations

import argparse
import bisect
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
            ((28, 86), (52, 84)), ((24, 62), (34, 62)), ((24, 38), (34, 38)), ((28, 14), (52, 16)),
            ((42, 50), (48, 50)),
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


_XM, _YM = 1.05, 0.68  # metres per pitch unit along x (105 m) and y (68 m)
_BLOCK_SPAN = 40.0  # out of possession, back line to front line in pitch units (about 42 m)
_MIN_GAP_M = 4.5  # teammates further apart than this in open play (away from set pieces and walls)

# Set-piece spots as (distance from the goal line being attacked, y), written for a corner from the low-y side and
# mirrored for the other one. Pitch units: six-yard line about 5.2 from goal, posts at y 44.6 / 55.4,
# penalty area 15.7 deep and y 20.4-79.6.
_CORNER_DEF_BOX = [(1.5, 43.5),                                  # near post
                   (5.5, 42), (5.5, 47.5), (5.5, 53), (5.5, 58.5),  # zonal line along the six-yard box
                   (8.2, 49.2), (10.2, 56.0),                    # man-markers, goal-side of the two main targets
                   (15.5, 47)]                                   # edge of the box for knock-downs
_CORNER_DEF_HIGH = [(30, 38), (42, 58)]                          # left up for the counter
_CORNER_ATT_BOX = [(2.5, 52), (7.5, 40), (9.5, 49), (11.5, 57), (13.5, 64), (17.5, 45), (18.5, 30)]
_CORNER_ATT_BACK = [(46, 38), (46, 62)]
_PENALTY_EDGE = [(17, 22), (17.5, 27), (17, 32), (17.5, 37), (17, 63), (17.5, 68), (17, 73), (17.5, 78),
                 (22.5, 44), (22.5, 50), (22.5, 56), (25, 39), (25, 61), (28, 30), (28, 70), (30, 50)]


def _dist_m(a, b) -> float:
    return math.hypot((a[0] - b[0]) * _XM, (a[1] - b[1]) * _YM)


def _keep_out(out, idx, centre, r_m: float, goal: Optional[float] = None) -> None:
    """Push players in idx radially out of a circle of r_m metres (9.15 m at free kicks and penalties).
    With `goal` (the x of their own goal line) they retreat goal-side of the ball when the pitch leaves room."""
    for i in idx:
        dx, dy = (out[i][0] - centre[0]) * _XM, (out[i][1] - centre[1]) * _YM
        d = math.hypot(dx, dy)
        if d >= r_m:
            continue
        a0 = math.atan2(dy, dx) if d > 1e-6 else 0.0
        ring = []
        for turn in (0, 1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6, 7, -7, 8, -8, 9):  # nearest direction first
            a = a0 + turn * math.pi / 9
            p = [centre[0] + math.cos(a) * (r_m + 0.3) / _XM, centre[1] + math.sin(a) * (r_m + 0.3) / _YM]
            if 0.5 <= p[0] <= 99.5 and 0.5 <= p[1] <= 99.5:
                ring.append(p)
        side = [p for p in ring if goal is None or abs(p[0] - goal) <= abs(centre[0] - goal)]
        if side or ring:
            out[i] = (side or ring)[0]


def _spread(out, fixed, min_m: float = _MIN_GAP_M, rounds: int = 4) -> None:
    """Keep teammates at least min_m apart by sliding them sideways (y only, so line heights and the offside
    picture are untouched). Players in `fixed` (the ball carrier, a free-kick wall) do not move."""
    for _ in range(rounds):
        moved = False
        for t in (0, 1):
            for a in range(t * 11, t * 11 + 11):
                for b in range(a + 1, t * 11 + 11):
                    dx = (out[a][0] - out[b][0]) * _XM
                    dy = (out[a][1] - out[b][1]) * _YM
                    if dx * dx + dy * dy >= min_m * min_m or (a in fixed and b in fixed):
                        continue
                    push = (math.sqrt(max(min_m * min_m - dx * dx, 0.0)) - abs(dy)) / _YM + 0.05
                    sgn = 1.0 if (dy > 0 or (dy == 0 and out[a][1] >= 50)) else -1.0  # a goes away from b
                    ka, kb = (0.0, 1.0) if a in fixed else (1.0, 0.0) if b in fixed else (0.5, 0.5)
                    out[a][1] = _clamp(out[a][1] + sgn * push * ka, 1, 99)
                    out[b][1] = _clamp(out[b][1] - sgn * push * kb, 1, 99)
                    moved = True
        if not moved:
            return


def _place(out, players, spots, gx, gy) -> None:
    """Put players on set-piece spots, matched by sideways order so nobody has to cross the box."""
    players = sorted(players, key=lambda i: out[i][1])
    for i, (g, y) in zip(players, sorted(spots, key=lambda s: gy(s[1]))):
        out[i] = [gx(g), gy(y)]


def _offside(out, bx: float, carrier) -> None:
    """Nobody beyond the second-last opponent (or the ball) in the opponents' half (IFAB Law 11); clamped attackers
    stay staggered, keeping their order, rather than forming a flat line."""
    xs1 = sorted((p[0] for p in out[11:]), reverse=True)
    xs0 = sorted(p[0] for p in out[:11])
    lim0 = max(50.0, bx, xs1[1])
    lim1 = min(50.0, bx, xs0[1])
    off0 = sorted((i for i in range(1, 11) if i != carrier and out[i][0] > lim0), key=lambda i: -out[i][0])
    for rank, i in enumerate(off0):
        out[i][0] = lim0 - 0.4 - 1.5 * rank
    off1 = sorted((i for i in range(12, 22) if i != carrier and out[i][0] < lim1), key=lambda i: out[i][0])
    for rank, i in enumerate(off1):
        out[i][0] = lim1 + 0.4 + 1.5 * rank


_DEAD = {"corner", "penalty", "free_kick", "throw_in", "goal_kick", "kickoff", "keeper_hold", "stoppage"}
_ACCEL = 4.0  # m/s per second
_WANDER_M = (5.5, 4.0)  # off-ball movement amplitude (x, y), metres
_PASS_MS = 16.0  # ball speed of a pass or clearance, m/s
RESTART_LIMITS = {"throw_in": 5.0, "goal_kick": 5.0, "keeper_hold": 8.0}  # PL 2026/27 handbook, seconds


def _motion(keys, vmax, first: str, seed: int):
    """Turn the step-by-step snapshots (one every 3-8 s) into 1-second movement.

    Between two snapshots each player runs towards the next snapshot's spot with their own top speed and a
    limited acceleration, plus a little off-ball movement, so nobody glides 20 m in a second or stands frozen.
    The ball moves with its holder and then travels at pass speed to the receiver; attackers aim to stay on the
    last defender's shoulder; on a dead ball everyone waits until it is played. Open-play snapshots are rewritten
    with the simulated positions; dead-ball ones (set pieces, kick-offs) keep their exact shapes because the
    stoppage gives players time to get there.

    Returns (frames, restarts): new (t, meta) frames, and (t_out, team, kind, seconds) for each timed restart."""
    xy = lambda p: [p[0] * _XM, p[1] * _YM]  # noqa: E731
    pu = lambda m: [round(m[0] / _XM, 1), round(m[1] / _YM, 1)]  # noqa: E731
    lerp = lambda p, q, a: [p[0] + (q[0] - p[0]) * a, p[1] + (q[1] - p[1]) * a]  # noqa: E731
    wr = random.Random(seed * 7 + 3)
    wander = [(wr.uniform(14, 26), wr.uniform(17, 31), wr.uniform(0, 6.3), wr.uniform(0, 6.3)) for _ in range(22)]

    def drift(i, t):  # checking runs and small adjustments off the ball, zero on average (metres)
        px, py, ax, ay = wander[i]
        k = 0.3 if i % 11 == 0 else 1.0
        return (k * _WANDER_M[0] * math.sin(2 * math.pi * t / px + ax), k * _WANDER_M[1] * math.sin(2 * math.pi * t / py + ay))

    def slot(m):
        h = m["holder"]
        return None if not h else (0 if h[0] == first else 11) + h[1]

    S = [xy(p) for p in keys[0].meta["pos"]]
    V = [[0.0, 0.0] for _ in range(22)]
    frames, restarts, dead_since = [], [], None
    for k0, k1 in zip(keys, keys[1:]):
        m0, m1, t0, t1 = k0.meta, k1.meta, k0.t, k1.t
        h0, h1 = slot(m0), slot(m1)
        same_stop = m1["phase"] == m0["phase"] and m1["poss"] == m0["poss"] and t1 - t0 < 3  # one stoppage, two frames
        dead0, into_dead = m0["phase"] in _DEAD, m1["phase"] in _DEAD and not same_stop
        b0, b1 = xy(m0["ball"]), xy(m1["ball"])
        carry = h0 is not None and h0 == h1
        flight = 0.0 if carry else _clamp(math.dist(b0, b1) / _PASS_MS, 0.5, 2.0)
        release = max(t0, t1 - flight)
        if dead0 and dead_since is None:
            dead_since = (t0, m0["poss"], m0["phase"])
        if dead0 and not same_stop:  # this restart is taken at `release`
            st, team, kind = dead_since
            if kind in RESTART_LIMITS:
                restarts.append((st, team, kind, round(release - st, 1)))
            dead_since = None
        start, ball, rel_pt = [p[:] for p in S], b0, None
        ts = t0 + 1.0
        while ts < t1 - 0.3:
            h = None
            if into_dead:  # the ball goes dead: players walk or jog to the set-piece spots meanwhile
                a = (ts - t0) / (t1 - t0)
                S = [lerp(p, xy(q), a) for p, q in zip(start, m1["pos"])]
                ph = "stoppage" if t1 - t0 > 30 else "open"  # a long stoppage (goal, VAR) is not open play
                ball, hold, poss, conf = lerp(b0, b1, a), None, m0["poss"], 0.0
            elif dead0 and ts < release:  # everyone waits for the restart
                ball, ph, hold, poss, conf, h = b0, m0["phase"], m0["holder"], m0["poss"], m0["conf"], h0
            else:
                in_air = not carry and ts >= release
                h = h1 if in_air else h0
                bx_u = (ball[0]) / _XM
                xs0 = sorted(S[i][0] / _XM for i in range(11))
                xs1 = sorted((S[i][0] / _XM for i in range(11, 22)), reverse=True)
                line0, line1 = max(50.0, bx_u, xs1[1]), min(50.0, bx_u, xs0[1])
                left = max(t1 - ts + 1.0, 1.0)
                sep = [[0.0, 0.0] for _ in range(22)]  # teammates closer than _MIN_GAP_M ease apart
                for tm in (0, 11):
                    for a in range(tm, tm + 11):
                        for b in range(a + 1, tm + 11):
                            dx, dy = S[a][0] - S[b][0], S[a][1] - S[b][1]
                            d = math.hypot(dx, dy)
                            if d < _MIN_GAP_M:
                                ux, uy = (dx / d, dy / d) if d > 1e-6 else (0.0, 1.0)
                                push = (_MIN_GAP_M - d) * 0.6
                                sep[a][0] += ux * push; sep[a][1] += uy * push
                                sep[b][0] -= ux * push; sep[b][1] -= uy * push
                for i in range(22):
                    if i == h0 and not in_air:
                        tx, ty = (b1 if carry else b0)  # the holder dribbles on, or stays on the ball before passing
                    elif i == h1 and in_air:
                        tx, ty = b1  # the receiver goes to meet the ball
                    else:
                        dx, dy = drift(i, ts)
                        tx, ty = xy(m1["pos"][i])
                        tx, ty = tx + dx + sep[i][0] * left, ty + dy + sep[i][1] * left
                        if i % 11:  # attackers aim for the last defender's shoulder, never beyond it
                            tx = min(tx, (line0 - 0.5) * _XM) if i < 11 else max(tx, (line1 + 0.5) * _XM)
                    dvx, dvy = (tx - S[i][0]) / left, (ty - S[i][1]) / left
                    offside_now = i % 11 and (S[i][0] / _XM > line0 if i < 11 else S[i][0] / _XM < line1)
                    if i in (h0, h1) or offside_now:  # ball players and attackers caught offside hurry
                        dvx, dvy = tx - S[i][0], ty - S[i][1]  # ball players go straight there, as fast as they can
                    sp = math.hypot(dvx, dvy)
                    if sp > vmax[i]:
                        dvx, dvy = dvx * vmax[i] / sp, dvy * vmax[i] / sp
                    ax, ay = dvx - V[i][0], dvy - V[i][1]
                    acc = math.hypot(ax, ay)
                    if acc > _ACCEL:
                        ax, ay = ax * _ACCEL / acc, ay * _ACCEL / acc
                    V[i] = [V[i][0] + ax, V[i][1] + ay]
                    S[i] = [_clamp(S[i][0] + V[i][0], -3, 108), _clamp(S[i][1] + V[i][1], -3, 71)]
                if not in_air:
                    ball = S[h0][:] if h0 is not None else lerp(b0, b1, (ts - t0) / (t1 - t0))
                else:
                    rel_pt = rel_pt or ball
                    ball = lerp(rel_pt, b1, min((ts - release) / flight, 1.0))
                ph = "open" if in_air or not dead0 else m0["phase"]
                hold = m1["holder"] if in_air else m0["holder"]
                poss = m1["poss"] if in_air else m0["poss"]
                conf = min(m1["conf"], 0.6) if in_air else m0["conf"]
            frames.append((round(ts, 1), {"phase_conf": m0["phase_conf"] if ph == m0["phase"] else 1.0,
                                          "pos": [pu(p) for p in S], "ball": pu(ball), "poss": poss,
                                          "holder": hold, "conf": round(conf, 2), "phase": ph}))
            ts += 1.0
        if m1["phase"] in _DEAD or t1 - t0 > 30:  # set pieces and kick-offs keep their exact shape
            S, V = [xy(p) for p in m1["pos"]], [[0.0, 0.0] for _ in range(22)]
        else:  # open play: the snapshot shows where the simulated players really are
            if h1 is not None:
                S[h1] = b1[:]
            m1["pos"] = [pu(p) for p in S]
    return frames, restarts


def _realism(pos, poss_idx: int, ball, ph: str, carrier: int):
    """Make the 22 positions obey football logic. All values are 0-100 pitch units, team 0 attacks +x.

    * Out of possession a team drops behind the ball as a block: the whole shape moves back together (lines keep
      their spacing) and only squeezes if the back line would end up in its own goal.
    * Nobody camps in an offside position: attackers sit on the shoulder of the opponents' second-last defender
      (a player is only offside if nearer the goal line than both the ball and the second-last opponent, in the
      opponents' half; IFAB Law 11).
    * Set pieces: corners (zonal line on the six-yard box, two man-markers, near post, edge, two left high),
      penalties (everyone outside the area and the arc) and free kicks (a wall at 9.15 m near goal, opponents
      9.15 m from the ball).
    * Teammates keep a few metres apart in open play instead of stacking on the same spot.
    """
    bx, by = ball
    out = [[p[0], p[1]] for p in pos]
    u = lambda t, x: x if t == 0 else 100 - x  # distance from a team's own goal line  # noqa: E731
    back = lambda t, v: v if t == 0 else 100 - v  # noqa: E731
    att, dfn = poss_idx, 1 - poss_idx
    end = 100.0 if att == 0 else 0.0  # the goal line being attacked
    gx = lambda g: end - g if end else g  # noqa: E731  (g = distance from that goal line)
    att_out = [att * 11 + k for k in range(1, 11) if att * 11 + k != carrier]
    dfn_out = [dfn * 11 + k for k in range(1, 11)]

    if ph == "corner":
        end = 100.0 if bx > 50 else 0.0
        gy = (lambda y: y) if by < 50 else (lambda y: 100 - y)  # noqa: E731
        d_idx = sorted(dfn_out, key=lambda i: abs(out[i][0] - end))
        _place(out, d_idx[:8], _CORNER_DEF_BOX, gx, gy)
        _place(out, d_idx[8:], _CORNER_DEF_HIGH, gx, gy)
        out[dfn * 11] = [gx(1.2), gy(51)]  # the keeper on his line, a step towards the far post
        a_idx = sorted(att_out, key=lambda i: abs(out[i][0] - end))
        _place(out, a_idx[:7], _CORNER_ATT_BOX, gx, gy)
        _place(out, a_idx[7:], _CORNER_ATT_BACK, gx, gy)
        out[att * 11] = [gx(78), 50]
        return out

    if ph == "penalty":
        gy = lambda y: y  # noqa: E731
        edge = sorted(_PENALTY_EDGE, key=lambda s: s[1])
        d_spots, a_spots = edge[0::2] + edge[1::2][:1], edge[1::2][1:]  # 9 defenders and 7 attackers share the edge
        d_idx = sorted(dfn_out, key=lambda i: abs(out[i][0] - end))
        a_idx = sorted(att_out, key=lambda i: abs(out[i][0] - end))
        _place(out, d_idx[:9], d_spots, gx, gy)
        _place(out, d_idx[9:], [(40, 50)], gx, gy)
        _place(out, a_idx[:7], a_spots, gx, gy)
        _place(out, a_idx[7:], [(52, 35), (52, 65)], gx, gy)
        out[dfn * 11] = [gx(0.4), 50]  # keeper on the line
        out[att * 11] = [gx(80), 50]
        _keep_out(out, d_idx + a_idx, (bx, by), 9.15)  # outside the arc
        return out

    for t in (0, 1):  # the team without the ball drops back as a block
        if t == poss_idx:
            continue
        idx = [t * 11 + k for k in range(1, 11)]
        bu = u(t, bx)
        us = {i: u(t, out[i][0]) for i in idx}
        lim = {i: max(bu + (44 if rank < 2 else 30), 18) for rank, i in enumerate(sorted(idx, key=lambda i: -us[i]))}
        need = max(us[i] - lim[i] for i in idx)
        if need > 0:
            d0 = min(us.values())
            shift = min(need, max(0.0, d0 - 6))  # the back line stops 6 units from its own goal line
            d0 -= shift
            over = [(lim[i] - d0) / (us[i] - shift - d0) for i in idx if us[i] - shift > lim[i]]
            k = min(over) if over else 1.0  # then squeeze proportionally, so lines keep their order and ratios
            for i in idx:
                out[i][0] = back(t, d0 + (us[i] - shift - d0) * k)
        us = [u(t, out[i][0]) for i in idx]  # a defending block is compact: back line to front line at most ~42 m
        d0, span = min(us), max(us) - min(us)
        if span > _BLOCK_SPAN:
            for i, cu in zip(idx, us):
                out[i][0] = back(t, d0 + (cu - d0) * _BLOCK_SPAN / span)

    for t in (0, 1):  # outfield players defend from the six-yard line, not on the goal line: squeeze 0-8 into 5-8
        for i in range(t * 11 + 1, t * 11 + 11):
            cu = u(t, out[i][0])
            if cu < 8 and i != carrier:
                out[i][0] = back(t, 5 + cu * 3 / 8)

    bu = u(att, bx)
    if bu >= 65 and ph == "open":  # final third: the front three join the attack and narrow towards the box
        for rank, i in enumerate(sorted(att_out, key=lambda i: -u(att, out[i][0]))[:3]):
            cu = u(att, out[i][0])
            out[i] = [back(att, max(cu, min(bu - 4 - 4 * rank, 90))), 50 + (out[i][1] - 50) * 0.75]

    for t in (0, 1):  # keepers: on the line between ball and goal centre, higher (sweeping) when their team has it
        k = t * 11
        if k == carrier:
            continue
        bu = u(t, bx)
        if t == poss_idx:
            g, ky = _clamp(4 + 0.18 * bu, 4, 22), 50 + (by - 50) * 0.1
        else:
            g, ky = _clamp(1.5 + 0.1 * bu, 1.5, 9), 50 + (by - 50) * (0.2 if bu < 40 else 0.08)
        out[k] = [back(t, g), ky]

    if ph == "goal_kick":  # centre-backs split to the corners of the box, opponents wait outside the area
        kt = poss_idx
        own = 0.0 if kt == 0 else 100.0
        go = lambda g: own + g if kt == 0 else own - g  # noqa: E731
        cbs = sorted((i for i in range(kt * 11 + 1, kt * 11 + 11) if i != carrier), key=lambda i: u(kt, out[i][0]))[:2]
        _place(out, cbs, [(13, 24), (13, 76)], go, lambda y: y)
        for i in dfn_out:
            if u(kt, out[i][0]) < 17.5 and 18 < out[i][1] < 82:
                out[i][0] = go(17.5 + (i % 3) * 1.5)
    elif ph == "throw_in":  # two short options: one down the line, one infield
        inside = 1.0 if by < 50 else -1.0
        fwd = 1.0 if att == 0 else -1.0
        mates = sorted(att_out, key=lambda i: _dist_m(out[i], (bx, by)))[:2]
        spots = [(bx + fwd * 8, by + inside * 6), (bx - fwd * 3, by + inside * 18)]
        for i, (sx, sy) in zip(mates, spots):
            out[i] = [_clamp(sx, 2, 98), _clamp(sy, 2, 98)]

    fixed = {carrier}
    if ph == "free_kick":
        gb = abs(end - bx)
        side = by - 50
        if gb <= 35 and abs(side) < 35:  # within shooting range: a wall 9.15 m from the ball
            n = 4 if gb < 25 and abs(side) < 18 else 3 if abs(side) < 28 else 2
            aim = (end, 50 + (2.7 if side > 0 else -2.7))  # the wall covers the near-post half of the goal
            vx, vy = (aim[0] - bx) * _XM, (aim[1] - by) * _YM
            norm = math.hypot(vx, vy) or 1.0
            vx, vy = vx / norm, vy / norm
            cx, cy = bx * _XM + vx * 9.15, by * _YM + vy * 9.15
            wall = sorted(dfn_out, key=lambda i: math.hypot(out[i][0] * _XM - cx, out[i][1] * _YM - cy))[:n]
            for k, i in enumerate(sorted(wall, key=lambda i: out[i][1])):
                off = (k - (n - 1) / 2) * 0.7  # shoulder to shoulder, across the line of the kick
                out[i] = [(cx - vy * off) / _XM, (cy + vx * off) / _YM]
            fixed.update(wall)
            out[dfn * 11] = [gx(1.0), 50 - (2.0 if side > 0 else -2.0)]  # keeper covers the far side
            # everyone else holds a line level with the wall (one stays up for the counter), the attackers
            # stand on its shoulder in the gaps
            line_g = _clamp(abs(end - cx / _XM) - 0.5, 6.0, 16.0)  # never higher than the edge of the box
            wall_y = cy / _YM
            rest = sorted((i for i in dfn_out if i not in wall), key=lambda i: abs(out[i][0] - end))[:-1]
            ys = [y for y in (28 + 44 * k / 9 for k in range(10)) if abs(y - wall_y) > 6][:len(rest)]
            _place(out, rest, [(line_g, y) for y in ys], gx, lambda y: y)
            runners = sorted(att_out, key=lambda i: abs(out[i][0] - end))[:4]
            gaps = [(a + b) / 2 for a, b in zip(ys, ys[1:])]
            gaps = sorted(gaps, key=lambda y: abs(y - 50))[:len(runners)]
            _place(out, runners, [(line_g + 0.8, y) for y in gaps], gx, lambda y: y)
        _spread(out, fixed, min_m=2.5)
        _keep_out(out, [i for i in dfn_out if i not in fixed], (bx, by), 9.15, goal=end)

    _offside(out, bx, carrier)
    if ph != "free_kick":
        _spread(out, fixed)  # sideways only, so it cannot undo the offside picture
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

    def frame_at(t_, poss_, x_, y_, ph="open", taker=None):
        """All 22 positions at a moment (absolute frame) plus who is on the ball."""
        bx, by = (x_, y_) if poss_ == codes[0] else (100 - x_, 100 - y_)
        pos, info = _frame_positions(codes, t_, poss_, x_, y_, teams,
                                     slot_of(poss_, taker) if taker else None)
        if ph == "kickoff" or t_ == 0.0:  # restarts from the centre: teams start in their own halves
            pos = _kickoff_shape(pos, codes.index(poss_), info["carrier"])
        else:
            pos = [[round(px, 1), round(py, 1)] for px, py in
                   _realism(pos, codes.index(poss_), (bx, by), ph, codes.index(poss_) * 11 + info["carrier"])]
        return pos, info, (bx, by)

    def at_ball(t_, poss_, x_, y_, exclude=None):
        """Names follow the geometry: (player on the ball, nearest opponent) at that moment. `exclude` skips one
        slot of the team on the ball (a pass is never received by the passer)."""
        pos, info, b = frame_at(t_, poss_, x_, y_)
        pi = codes.index(poss_)
        mine = sorted(range(11), key=lambda k: _dist_m(pos[pi * 11 + k], b))
        k = info["carrier"] if info["carrier"] != exclude else next(k for k in mine if k != exclude)
        near = min(range(11), key=lambda k: _dist_m(pos[(1 - pi) * 11 + k], b))
        return roster[poss_][k][0], roster[other[poss_]][near][0], k

    def track(t_, poss_, x_, y_, ph="open", phc=1.0, loose=False, taker=None, runner=None, run_k=0.0):
        """One tracking frame. holder/conf/phase say who has the ball and what kind of play it is;
        conf is lower when the ball is contested, plus a deterministic *simulated* tracker
        occlusion so consumers must handle uncertain frames."""
        if not tracking:
            return
        pos, info, (bx, by) = frame_at(t_, poss_, x_, y_, ph, taker)
        r = slot_of(poss_, runner) if runner and runner != taker else None
        if r is not None:  # a scripted scorer making a run towards the penalty spot
            k = codes.index(poss_) * 11 + r
            gx_ = 86.0 if poss_ == codes[0] else 14.0
            pos[k] = [round(pos[k][0] + (gx_ - pos[k][0]) * run_k, 1), round(pos[k][1] + (46 - pos[k][1]) * run_k, 1)]
        if ph in ("throw_in", "corner"):  # the taker stands just outside the line, the ball sits on it
            k = codes.index(poss_) * 11 + info["carrier"]
            pos[k] = ([round(bx, 1), -2.0 if by < 50 else 102.0] if ph == "throw_in"
                      else [round(bx + (1.6 if bx > 50 else -1.6), 1), by + (-2.0 if by < 50 else 2.0)])
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
    carries: List[Tuple[Event, int]] = []  # (carry event, player index in the frame) to time from tracking
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
            for dt, bx_, k in ((9, 58, 0.35), (6, 65, 0.7), (3, 72, 0.95)):  # build-up: the scorer runs into the box
                track(tt - dt, att, bx_, 52, taker=item.get("assist") or item["scorer"], runner=item["scorer"], run_k=k)
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
        while script and script[0]["t"] - 12 <= t:  # 12 s early, so scripted goals get their build-up frames
            run_script(script.pop(0))
        opp = other[poss]
        boost = {c: 0.45 if any(s <= t < e and tm == c for s, e, tm in phases) else 0.0
                 for c in codes}
        att, dfn = strength[poss] + boost[poss], strength[opp] + boost[opp]
        p_lose = _clamp(0.11 * dfn / att, 0.05, 0.3)
        r = rng.random()
        ph, phc, loose = "open", 1.0, False
        hold = None  # who the next frame shows on the ball, when an event names them

        # Names come from the positions of that moment (pick() still runs so the random stream, and with it the
        # match, stays the same as before).
        if x >= 72 and rng.random() < (scen.get("shot_rate", 0.09) if scen else 0.09):
            pick(poss, x)
            shooter = at_ball(t, poss, x, y)[0]
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
                pick(poss, 8)
                emit(t, "possession_change", poss, at_ball(t, poss, x, y)[0], x, y, cause="shot_" + outcome)
                if outcome == "off_target":
                    emit(t, "restart", poss, "", x, y, kind="goal_kick")
                    ph, phc = "goal_kick", 0.95
                elif outcome == "saved":
                    ph, phc = "keeper_hold", 0.95
        elif r < p_lose:
            pick(opp, 100 - x)
            tackler = at_ball(t, poss, x, y)[1]
            kind = "tackle" if rng.random() < 0.6 else "interception"
            emit(t, kind, opp, tackler, 100 - x, 100 - y, "won")
            poss, x, y, pressured = opp, 100 - x, 100 - y, False
            emit(t, "possession_change", poss, tackler, x, y, cause=kind)
            hold = tackler
            loose = True  # the ball is up for grabs for a moment
        elif r < p_lose + 0.12 * (0.4 + teams[opp]["tactic"]["press"]):
            pick(opp, 100 - x)
            emit(t, "pressure", opp, at_ball(t, poss, x, y)[1], 100 - x, 100 - y,
                 intensity=round(rng.uniform(0.3, 1.0), 2))
            pressured = True
        elif rng.random() < 0.15:
            pick(poss, x)
            carrier, _, cslot = at_ball(t, poss, x, y)
            dx = _clamp(rng.gauss(6, 4), 0, 20)
            speed = round(_clamp(rng.gauss(24, 5), 12, 36), 1)  # replaced by the measured speed when tracking
            emit(t, "carry", poss, carrier, x, y, "", speed_kmh=speed,
                 distance_m=round(dx * 1.05, 1))
            carries.append((events[-1], codes.index(poss) * 11 + cslot))
            x, hold = _clamp(x + dx, 2, 98), carrier
        else:
            pick(poss, x)
            passer, _, passer_slot = at_ball(t, poss, x, y)
            dx = rng.gauss(26, 8) if rng.random() < teams[poss]["tactic"]["long"] else rng.gauss(8, 9)
            nx, ny = _clamp(x + dx, 2, 98), _clamp(y + rng.gauss(0, 14), 4, 96)
            dist = math.hypot((nx - x) * 1.05, (ny - y) * 0.68)
            difficulty = _clamp(0.1 + dist / 60 + (0.25 if pressured else 0)
                                + (0.15 if nx > 70 else 0), 0, 1)
            p_ok = _clamp(1.0 - difficulty * 0.4 + (strength[poss] - 1) * 0.2, 0.2, 0.97)
            pick(poss, nx)
            receiver = at_ball(t, poss, nx, ny, exclude=passer_slot)[0]
            ok = rng.random() < p_ok
            emit(t, "pass", poss, passer, x, y, "complete" if ok else "incomplete",
                 receiver=receiver, distance_m=round(dist, 1), difficulty=round(difficulty, 2), ex=round(nx, 1), ey=round(ny, 1),
                 speed_kmh=round(rng.uniform(35, 75) if dist > 20 else rng.uniform(20, 45), 0))
            if ok:
                x, y, hold = nx, ny, receiver
            elif ny < 7 or ny > 93:  # ran out over the touchline: throw-in to the other side
                poss, x, y = opp, 100 - nx, (100.0 if ny < 50 else 0.0)  # on the touchline
                emit(t, "possession_change", poss, "", x, y, cause="out_of_play")
                emit(t, "restart", poss, "", x, y, kind="throw_in")
                ph, phc = "throw_in", 0.92
            else:
                poss, x, y = opp, 100 - nx, 100 - ny
                pick(poss, x)
                emit(t, "possession_change", poss, at_ball(t, poss, x, y)[0], x, y, cause="turnover")
            pressured = False
        track(t, poss, x, y, ph, phc, loose, taker=hold)

    # Discipline layer from its own RNG so the match flow above is untouched: some pressure events are
    # fouls (free kick to the other side, occasionally a yellow card) and some failed final-third passes offside.
    frng = random.Random(seed * 104729 + 7)
    yellows = {c: 0 for c in codes}
    for e in list(events):
        in_box = 100 - e.x > 84.3 and 20.4 < e.y < 79.6  # a foul there would be a penalty: random play never gives one
        if e.type == "pressure" and frng.random() < 0.22 and not in_box:
            emit(e.t, "foul", e.team, e.player, e.x, e.y, against=other[e.team])
            emit(e.t + 0.1, "restart", other[e.team], "", 100 - e.x, 100 - e.y, kind="free_kick")
            if e.t + 2.5 < duration:  # set-up frame (wall, 9.15 m) before play resumes; the next step is 3+ s later
                track(e.t + 2.5, other[e.team], 100 - e.x, 100 - e.y, "free_kick", 0.9)
            if frng.random() < 0.13 and yellows[e.team] < 4 and not scen:
                yellows[e.team] += 1
                emit(e.t + 0.2, "card", e.team, e.player, e.x, e.y, card="yellow")
        elif e.type == "pass" and e.outcome == "incomplete" and e.x >= 62 and frng.random() < 0.3:
            # offside only when the geometry allows it: the intended receiver was on the last defender's shoulder
            pos, _, (bx, by) = frame_at(e.t, e.team, e.x, e.y)
            ti = codes.index(e.team)
            k = slot_of(e.team, e.meta.get("receiver", ""))
            them = sorted((p[0] for p in pos[(1 - ti) * 11:(1 - ti) * 11 + 11]), reverse=ti == 0)
            line = max(50.0, bx, them[1]) if ti == 0 else min(50.0, bx, them[1])
            if k is not None and abs(pos[ti * 11 + k][0] - line) <= 3.0:
                emit(e.t, "offside", e.team, e.meta["receiver"], e.x, e.y, line_x=round(line, 1))

    if tracking:  # 1-second movement between the snapshots, plus how long each timed restart took
        keys = sorted((e for e in events if e.type == "tracking"), key=lambda ev: (ev.t, ev.id))
        vrng = random.Random(seed * 31 + 5)
        vmax = [6.0 if i % 11 == 0 else vrng.uniform(7.4, 9.2) for i in range(22)]  # top speed, m/s
        frames, restarts = _motion(keys, vmax, codes[0], seed)
        for t_, m in frames:
            bx_, by_ = m["ball"] if m["poss"] == codes[0] else (100 - m["ball"][0], 100 - m["ball"][1])
            emit(t_, "tracking", m["poss"], "", bx_, by_, **m)
        allf = sorted(((e.t, e.meta) for e in events if e.type == "tracking"), key=lambda f: f[0])
        times = [f[0] for f in allf]
        for ce, k in carries:  # a carry's speed is what the tracking shows for that run, not a guess
            lo, hi = bisect.bisect_left(times, ce.t - 9), bisect.bisect_right(times, ce.t + 0.1)
            seg = allf[lo:hi]
            sp = [math.hypot((b["pos"][k][0] - a["pos"][k][0]) * _XM, (b["pos"][k][1] - a["pos"][k][1]) * _YM) / (tb - ta)
                  for (ta, a), (tb, b) in zip(seg, seg[1:]) if 0.5 <= tb - ta <= 1.5]
            sp = [v for v in sp if v <= 9.5]  # faster is a jump in the data, not running
            if sp:
                ce.meta["speed_kmh"] = round(max(sp) * 3.6, 1)
        for st, team, kind, secs in restarts:
            emit(st + secs, "restart_taken", team, "", 50, 50, kind=kind, secs=secs, limit=RESTART_LIMITS[kind])

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
