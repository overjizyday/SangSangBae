from __future__ import annotations

from collections.abc import Sequence

from .models import Match, Team

LEAGUE_POINTS_BY_RANK = {
    1: 10,
    2: 5,
    3: 1,
}
CUP_WINNER_POINTS = 7
CUP_RUNNER_UP_POINTS = 3

ROUND_PAIRINGS = {
    1: [(1, 4), (2, 5), (3, 6)],
    2: [(5, 1), (6, 2), (3, 4)],
    3: [(6, 1), (2, 3), (4, 5)],
    4: [(1, 3), (2, 4), (5, 6)],
    5: [(1, 2), (3, 5), (4, 6)],
}


def calculate_super_cup_points(
    previous_standings: Sequence[dict[str, object]],
    cup_results: dict[str, dict[str, str | None]] | None = None,
) -> list[dict[str, object]]:
    cup_results = cup_results or {}
    bonuses: dict[str, int] = {}
    for result in cup_results.values():
        winner_id = result.get("winner_id")
        runner_up_id = result.get("runner_up_id")
        if winner_id:
            bonuses[str(winner_id)] = bonuses.get(str(winner_id), 0) + CUP_WINNER_POINTS
        if runner_up_id:
            bonuses[str(runner_up_id)] = bonuses.get(str(runner_up_id), 0) + CUP_RUNNER_UP_POINTS

    rows = []
    for row in previous_standings:
        rank = int(row["rank"])
        team_id = str(row["team_id"])
        league_points = LEAGUE_POINTS_BY_RANK.get(rank, 0)
        cup_points = bonuses.get(team_id, 0)
        rows.append(
            {
                "team_id": team_id,
                "team_name": str(row.get("team_name", row["team_id"])),
                "league_rank": rank,
                "points": league_points + cup_points,
                "league_bonus_points": league_points,
                "cup_bonus_points": cup_points,
                "super_cup_table_points": 0,
                "acl_score": league_points + cup_points,
            }
        )
    rows.sort(key=lambda row: (-int(row["points"]), int(row["league_rank"])))
    return rows


def generate_super_cup(
    teams: Sequence[Team],
    previous_standings: Sequence[dict[str, object]],
    cup_results: dict[str, dict[str, str | None]] | None = None,
) -> dict[str, object]:
    if len(teams) < 6 or len(previous_standings) < 6:
        return {
            "held": False,
            "reason": "슈퍼컵은 전년도 포인트 상위 6팀이 필요합니다.",
            "matches": [],
        }

    entrants = calculate_super_cup_points(previous_standings, cup_results)[:6]
    seed_to_team = {idx: row["team_id"] for idx, row in enumerate(entrants, start=1)}
    matches = []
    match_no = 1
    for round_no, pairings in ROUND_PAIRINGS.items():
        week = 1 if round_no <= 2 else 2
        for home_seed, away_seed in pairings:
            matches.append(
                Match(
                    id=f"SC-R{round_no}-{match_no:03d}",
                    competition="super_cup",
                    stage="league",
                    round=round_no,
                    week=week,
                    match_no=match_no,
                    home_team_id=seed_to_team[home_seed],
                    away_team_id=seed_to_team[away_seed],
                )
            )
            match_no += 1

    return {
        "held": True,
        "entrants": entrants,
        "matches": matches,
    }
