from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Team:
    id: str
    name: str
    region: str | None = None
    professional: bool = True


@dataclass
class Match:
    id: str
    competition: str
    stage: str
    round: int | str
    week: int
    home_team_id: str
    away_team_id: str
    match_no: int | None = None
    region: str | None = None
    group: str | None = None
    leg: int | None = None
    advantage_team_id: str | None = None
    day: str | None = None
    home_score: int | None = None
    away_score: int | None = None
    winner_team_id: str | None = None
    loser_team_id: str | None = None


@dataclass
class Standing:
    rank: int
    team_id: str
    team_name: str
    played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int


@dataclass
class SeasonMetadata:
    year: int
    competitions: list[str]
    todos: list[str]
    replay_started_at: str | None = None


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value
