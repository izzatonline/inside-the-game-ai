from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Event:
    """One synthetic match event.

    x/y are 0-100 pitch coordinates from the *acting team's* attacking
    perspective: x=0 is their own goal line, x=100 the opponent's.
    """

    id: int
    t: float  # match seconds
    type: str  # kickoff|pass|carry|shot|tackle|interception|pressure|possession_change|fulltime
    team: str
    player: str
    x: float
    y: float
    outcome: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def minute(self) -> int:
        return int(self.t // 60) + 1

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["minute"] = self.minute
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Event":
        return cls(d["id"], d["t"], d["type"], d["team"], d["player"], d["x"], d["y"],
                   d.get("outcome", ""), d.get("meta", {}))


@dataclass
class Moment:
    """A detected, explainable moment. `facts` is the only data narration may use."""

    id: str
    kind: str
    t: float
    minute: int
    team: str
    player: Optional[str]
    importance: float  # 0-1
    facts: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Profile:
    """Viewer preferences that make the same match feel different per fan."""

    mode: str = "casual"  # casual | analyst
    lang: str = "en"
    team: Optional[str] = None  # favourite club code
    player: Optional[str] = None  # player-focus mode
    metric: Optional[str] = None  # xg | speed | passing


@dataclass
class Overlay:
    moment_id: str
    t: float
    minute: int
    kind: str
    team: str
    importance: float
    headline: str
    body: str
    why: str
    chips: List[Dict[str, str]]
    lang: str
    mode: str
    source: str  # llm | template
    verified: bool
    duration_s: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
