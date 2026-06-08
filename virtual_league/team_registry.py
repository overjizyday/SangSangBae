from __future__ import annotations

import json
from pathlib import Path

from .models import Team, to_jsonable

VALID_REGIONS = ["서울", "경기", "강원", "충청", "전라", "경상"]

DEFAULT_TEAM_SPECS = [
    ("T01", "서산", "충청", True),
    ("T02", "대구", "경상", True),
    ("T03", "부산", "경상", True),
    ("T04", "광주", "전라", True),
    ("T05", "경산", "경상", True),
    ("T06", "동대문", "서울", True),
]


def default_teams() -> list[Team]:
    return [
        Team(id=team_id, name=name, region=region, professional=professional)
        for team_id, name, region, professional in DEFAULT_TEAM_SPECS
    ]


def normalize_team(raw: dict[str, object]) -> Team:
    team_id = str(raw["id"]).strip()
    name = str(raw["name"]).strip()
    region = raw.get("region")
    professional = bool(raw.get("professional", True))

    if not team_id:
        raise ValueError("팀 id가 비어 있습니다.")
    if not name:
        raise ValueError(f"{team_id} 팀 이름이 비어 있습니다.")
    if region is not None:
        region = str(region).strip()
    if region not in VALID_REGIONS:
        raise ValueError(f"{team_id}의 region은 {VALID_REGIONS} 중 하나여야 합니다: {region}")

    return Team(id=team_id, name=name, region=region, professional=professional)


def validate_teams(teams: list[Team]) -> None:
    if len(teams) < 2:
        raise ValueError("팀은 최소 2개가 필요합니다.")

    ids = [team.id for team in teams]
    names = [team.name for team in teams]
    if len(ids) != len(set(ids)):
        raise ValueError("중복된 팀 id가 있습니다.")
    if len(names) != len(set(names)):
        raise ValueError("중복된 팀 이름이 있습니다.")


def load_teams(path: Path) -> list[Team]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path}는 팀 객체 배열이어야 합니다.")
    teams = [normalize_team(item) for item in raw]
    validate_teams(teams)
    return teams


def save_teams(path: Path, teams: list[Team]) -> None:
    validate_teams(teams)
    path.write_text(
        json.dumps(to_jsonable(teams), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def ensure_team_file(path: Path) -> list[Team]:
    if path.exists():
        return load_teams(path)
    teams = default_teams()
    save_teams(path, teams)
    return teams


def next_team_id(teams: list[Team]) -> str:
    numbers = []
    for team in teams:
        if team.id.startswith("T") and team.id[1:].isdigit():
            numbers.append(int(team.id[1:]))
    return f"T{(max(numbers) if numbers else 0) + 1:02d}"


def add_team(
    path: Path,
    name: str,
    region: str,
    professional: bool = True,
    team_id: str | None = None,
) -> Team:
    teams = ensure_team_file(path)
    new_team = Team(
        id=team_id or next_team_id(teams),
        name=name,
        region=region,
        professional=professional,
    )
    normalize_team(to_jsonable(new_team))
    teams.append(new_team)
    save_teams(path, teams)
    return new_team
