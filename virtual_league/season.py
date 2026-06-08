from __future__ import annotations

import json
import secrets
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from .acl import generate_acl
from .acl_view import write_acl_participants_html
from .calendar import assign_season_days
from .calendar_view import write_calendar_html
from .championship import generate_championship
from .fa_cup import generate_fa_cup
from .future_competitions import todo_messages
from .league import generate_league_final_round, generate_league_schedule
from .local_cup import generate_local_cup
from .models import Match, SeasonMetadata, Team, to_jsonable
from .results import simulate_match_outcomes, simulate_match_outcomes_with_traces, write_results_csv
from .simulation import simulate_results
from .standings import calculate_standings
from .standings_view import build_competition_tables, write_standings_csv, write_standings_html
from .super_cup import generate_super_cup
from .team_registry import default_teams, ensure_team_file
from .tournament_resolution import (
    resolve_acl,
    resolve_linear_bracket,
    resolve_local_cup,
    resolve_super_cup,
)


def discover_next_year(seasons_dir: Path) -> int:
    if not seasons_dir.exists():
        return 1970

    years = []
    for child in seasons_dir.iterdir():
        if child.is_dir() and child.name.isdigit():
            years.append(int(child.name))
    latest_year = max(years) if years else 1969
    latest_dir = seasons_dir / str(latest_year)
    season_file = latest_dir / "season.json"
    if latest_year > 1970 and season_file.exists() and _season_needs_repair(latest_dir):
        return latest_year
    return latest_year + 1 if years else 1970


def _season_needs_repair(season_dir: Path) -> bool:
    if not season_dir.exists():
        return False
    required = [
        "season.json",
        "teams.json",
        "schedule.json",
        "standings.json",
        "results.csv",
        "standings.csv",
        "standings.html",
        "calendar.html",
    ]
    for filename in required:
        path = season_dir / filename
        if not path.exists():
            return True
        if filename.endswith(".json"):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return True
    season_file = season_dir / "season.json"
    if season_file.exists():
        try:
            data = json.loads(season_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return True
        if not data.get("competitions"):
            return True
    return False


def _latest_completed_season_standings(seasons_dir: Path, year: int) -> list[dict[str, object]]:
    for prior_year in range(year - 1, 1969, -1):
        previous_standings = seasons_dir / str(prior_year) / "standings.json"
        if not previous_standings.exists():
            continue
        data = json.loads(previous_standings.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            return data
    return []


def find_previous_league_winner_id(seasons_dir: Path, year: int) -> str | None:
    standings = _latest_completed_season_standings(seasons_dir, year)
    if not standings:
        return None
    return str(standings[0]["team_id"])


def load_previous_standings(seasons_dir: Path, year: int) -> list[dict[str, object]]:
    return _latest_completed_season_standings(seasons_dir, year)


def load_previous_cup_results(seasons_dir: Path, year: int) -> dict[str, dict[str, str | None]]:
    results: dict[str, dict[str, str | None]] = {}
    for prior_year in range(year - 1, 1969, -1):
        season_dir = seasons_dir / str(prior_year)
        if not season_dir.exists():
            continue
        for competition in ["local_cup", "championship", "fa_cup"]:
            if competition in results:
                continue
            path = season_dir / f"{competition}.json"
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            standings = data.get("standings")
            winner_id: str | None = None
            runner_up_id: str | None = None
            if isinstance(standings, list):
                if len(standings) >= 1 and isinstance(standings[0], dict):
                    winner_id = str(standings[0].get("team_id") or "") or None
                if len(standings) >= 2 and isinstance(standings[1], dict):
                    runner_up_id = str(standings[1].get("team_id") or "") or None
            champions = data.get("champions")
            if winner_id is None and isinstance(champions, dict):
                champion = champions.get(competition)
                winner_id = str(champion or "") or None
            if winner_id or runner_up_id:
                results[competition] = {"winner_id": winner_id, "runner_up_id": runner_up_id}
        if results:
            return results
    return results


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(to_jsonable(value), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _resolve_seed(seed: int | None) -> int:
    return seed if seed is not None else secrets.randbelow(2**31)


def _strip_placeholder_metadata(payload: dict[str, object]) -> None:
    for key in ["advancers", "po_candidates", "regional_advancers", "slot_advancers"]:
        if key in payload:
            payload.pop(key, None)
    champions = payload.get("champions")
    if isinstance(champions, dict):
        for key, value in list(champions.items()):
            if isinstance(value, str) and any(token in value for token in ["_승자", "_예선통과_", "_PO후보"]):
                champions.pop(key, None)


def _normalize_matches(payload: dict[str, object]) -> None:
    matches = payload.get("matches")
    if not isinstance(matches, list):
        return
    normalized: list[Match] = []
    for item in matches:
        if isinstance(item, Match):
            normalized.append(item)
            continue
        if isinstance(item, dict):
            normalized.append(
                Match(
                    id=str(item.get("id", "")),
                    competition=str(item.get("competition", payload.get("competition", ""))),
                    stage=str(item.get("stage", "")),
                    round=item.get("round", ""),
                    week=int(item.get("week", 0)),
                    home_team_id=str(item.get("home_team_id", "")),
                    away_team_id=str(item.get("away_team_id", "")),
                    match_no=item.get("match_no"),
                    region=item.get("region"),
                    group=item.get("group"),
                    leg=item.get("leg"),
                    advantage_team_id=item.get("advantage_team_id"),
                    day=item.get("day"),
                    home_score=item.get("home_score"),
                    away_score=item.get("away_score"),
                    winner_team_id=item.get("winner_team_id"),
                    loser_team_id=item.get("loser_team_id"),
                )
            )
    payload["matches"] = normalized


def _contains_placeholder(value: object) -> bool:
    if not isinstance(value, str):
        return False
    tokens = ["TBD_", "PENDING_", "_예선통과_", "_PO후보", "승자_"]
    return any(token in value for token in tokens)


def _validate_competition_outputs(competition_payloads: list[dict[str, object]], competition_tables: dict[str, list[dict[str, object]]]) -> None:
    offenders: list[str] = []

    for payload in competition_payloads:
        if not isinstance(payload, dict) or not payload.get("held"):
            continue
        for match in payload.get("matches", []):
            if not isinstance(match, Match):
                continue
            for field_name in ["home_team_id", "away_team_id", "winner_team_id", "loser_team_id"]:
                if _contains_placeholder(getattr(match, field_name, None)):
                    offenders.append(f"{payload.get('competition', 'competition')}.matches.{match.id}.{field_name}")

    for table_name, rows in competition_tables.items():
        for row in rows:
            for key in ["team_id", "team_name"]:
                if _contains_placeholder(row.get(key)):
                    offenders.append(f"standings.{table_name}.{row.get('rank', '')}.{key}")

    if offenders:
        raise ValueError(f"Placeholder tokens remain in competition outputs: {', '.join(offenders[:10])}")


def _apply_league_final_round_floor(
    regular_standings: list[object],
    final_standings: list[object],
    protected_count: int = 4,
) -> list[object]:
    if len(regular_standings) < protected_count:
        return final_standings

    protected_ids = {
        str(getattr(row, "team_id", row.get("team_id", "")) if hasattr(row, "get") else getattr(row, "team_id", ""))
        for row in regular_standings[:protected_count]
    }

    def _team_id(row: object) -> str:
        if hasattr(row, "get"):
            return str(row.get("team_id", ""))
        return str(getattr(row, "team_id", ""))

    protected_rows = [row for row in final_standings if _team_id(row) in protected_ids]
    other_rows = [row for row in final_standings if _team_id(row) not in protected_ids]

    def _sort_key(row: object) -> tuple[int, int, int, int, str]:
        if hasattr(row, "get"):
            getter = row.get
            return (
                int(getter("points", 0)),
                int(getter("goal_difference", getter("gd", 0))),
                int(getter("goals_for", getter("gf", 0))),
                -int(getter("goals_against", getter("ga", 0))),
                str(getter("team_name", getter("team_id", ""))),
            )
        return (
            int(getattr(row, "points", 0)),
            int(getattr(row, "goal_difference", getattr(row, "gd", 0))),
            int(getattr(row, "goals_for", getattr(row, "gf", 0))),
            -int(getattr(row, "goals_against", getattr(row, "ga", 0))),
            str(getattr(row, "team_name", getattr(row, "team_id", ""))),
        )

    protected_rows.sort(key=_sort_key, reverse=True)
    combined = protected_rows + other_rows

    for rank, row in enumerate(combined, start=1):
        if hasattr(row, "rank"):
            row.rank = rank
        elif isinstance(row, dict):
            row["rank"] = rank
    return combined


def create_season(
    seasons_dir: Path | str = "seasons",
    teams: Iterable[Team] | None = None,
    seed: int | None = None,
    teams_file: Path | str | None = None,
) -> Path:
    seed = _resolve_seed(seed)
    root = Path(seasons_dir)
    root.mkdir(parents=True, exist_ok=True)
    year = discover_next_year(root)
    season_dir = root / str(year)
    season_dir.mkdir(exist_ok=True)

    if teams is not None:
        season_teams = list(teams)
    else:
        registry_path = Path(teams_file) if teams_file is not None else root.parent / "teams.json"
        season_teams = ensure_team_file(registry_path)

    schedule = generate_league_schedule(season_teams, seed=seed)
    simulated_regular_schedule = simulate_results(schedule, seed=seed + year)
    regular_standings = calculate_standings(season_teams, simulated_regular_schedule)
    league_final_round = generate_league_final_round(regular_standings)
    if league_final_round:
        simulate_results(league_final_round, seed=seed + year + 1)
    simulated_schedule = simulated_regular_schedule + league_final_round
    standings = calculate_standings(season_teams, simulated_schedule)
    if league_final_round:
        standings = _apply_league_final_round_floor(regular_standings, standings, protected_count=4)

    competitions = ["league"]
    competition_payloads = []
    super_cup = None
    local_cup = None
    championship = None
    fa_cup = None
    metadata = SeasonMetadata(
        year=year,
        competitions=competitions,
        todos=[] if year == 1970 else todo_messages(),
        replay_started_at=datetime.now(UTC).isoformat(),
    )

    if year > 1970:
        previous_standings = load_previous_standings(root, year)
        previous_cup_results = load_previous_cup_results(root, year)
        previous_winner_id = find_previous_league_winner_id(root, year)
        if previous_winner_id is None:
            previous_winner_id = standings[0].team_id

        local_cup = generate_local_cup(season_teams, previous_winner_id, seed=seed + year)
        if local_cup["held"]:
            metadata.competitions.append("local_cup")
        competition_payloads.append(local_cup)

        championship = generate_championship(season_teams, previous_standings, root, year)
        if championship["held"]:
            metadata.competitions.append("championship")
        competition_payloads.append(championship)

        fa_cup = generate_fa_cup(season_teams, previous_standings, seed=seed + year)
        if fa_cup["held"]:
            metadata.competitions.append("fa_cup")
        competition_payloads.append(fa_cup)

        super_cup = generate_super_cup(season_teams, previous_standings, previous_cup_results)
        if super_cup["held"]:
            resolve_super_cup(super_cup, seed=seed + year)
        if super_cup["held"]:
            metadata.competitions.append("super_cup")
        competition_payloads.append(super_cup)

    acl = generate_acl(season_teams, super_cup, root, year, seed=seed + year)
    if acl["held"]:
        metadata.competitions.append("acl")
    competition_payloads.append(acl)
    for payload in [local_cup, championship, fa_cup, super_cup, acl]:
        if isinstance(payload, dict):
            _normalize_matches(payload)

    if isinstance(local_cup, dict):
        resolve_local_cup(local_cup, seed=seed + year)
    if isinstance(championship, dict):
        resolve_linear_bracket(championship, seed=seed + year)
    if isinstance(fa_cup, dict):
        resolve_linear_bracket(fa_cup, seed=seed + year)
    if isinstance(super_cup, dict) and "standings" not in super_cup:
        resolve_super_cup(super_cup, seed=seed + year)
    if isinstance(acl, dict):
        resolve_acl(acl, seed=seed + year, year=year)

    for payload in [local_cup, championship, fa_cup, super_cup, acl]:
        if isinstance(payload, dict):
            _strip_placeholder_metadata(payload)

    assign_season_days(simulated_schedule, competition_payloads, seed=seed + year)

    if isinstance(local_cup, dict):
        write_json(season_dir / "local_cup.json", local_cup)
    if isinstance(championship, dict):
        write_json(season_dir / "championship.json", championship)
    if isinstance(fa_cup, dict):
        write_json(season_dir / "fa_cup.json", fa_cup)
    if isinstance(super_cup, dict):
        write_json(season_dir / "super_cup.json", super_cup)

    write_json(season_dir / "acl.json", acl)

    competition_matches: list[Match] = []
    for payload in competition_payloads:
        if payload.get("held"):
            competition_matches.extend([match for match in payload.get("matches", []) if isinstance(match, Match)])

    result_rows, live_traces = simulate_match_outcomes_with_traces(
        simulated_schedule + competition_matches, seed=seed + year
    )

    league_rows = [asdict(row) for row in standings]
    competition_tables = build_competition_tables(league_rows, competition_payloads, season_teams)

    _validate_competition_outputs(competition_payloads, competition_tables)
    write_json(season_dir / "season.json", metadata)
    write_json(season_dir / "teams.json", season_teams)
    write_json(season_dir / "schedule.json", simulated_schedule)
    write_json(season_dir / "standings.json", standings)
    write_results_csv(season_dir / "results.csv", result_rows)
    write_json(season_dir / "live_feed.json", live_traces)
    write_standings_csv(season_dir / "standings.csv", competition_tables)
    write_standings_html(season_dir / "standings.html", year, competition_tables)
    write_calendar_html(season_dir / "calendar.html", year, season_teams, simulated_schedule, competition_payloads)
    for payload in competition_payloads:
        if payload.get("held") and payload.get("matches") and payload.get("korea_slot"):
            write_acl_participants_html(season_dir / "acl_participants.html", payload)
            break
    return season_dir
