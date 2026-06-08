from __future__ import annotations

from collections.abc import Sequence

from .models import Match, Team

LEAGUE_POINTS_BY_RANK = {
    1: 15,
    2: 8,
    3: 3,
    4: 1,
    5: 0,
    6: 0,
}

ROUND_PAIRINGS = {
    1: [(1, 4), (2, 5), (3, 6)],
    2: [(5, 1), (6, 2), (3, 4)],
    3: [(6, 1), (2, 3), (4, 5)],
    4: [(1, 3), (2, 4), (5, 6)],
    5: [(1, 2), (3, 5), (4, 6)],
}


def calculate_super_cup_points(previous_standings: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for row in previous_standings:
        rank = int(row["rank"])
        if rank > 6:
            continue
        rows.append(
            {
                "team_id": str(row["team_id"]),
                "team_name": str(row.get("team_name", row["team_id"])),
                "league_rank": rank,
                "points": LEAGUE_POINTS_BY_RANK[rank],
                "super_cup_table_points": 0,
                "acl_score": LEAGUE_POINTS_BY_RANK[rank],
            }
        )
    rows.sort(key=lambda row: (int(row["points"]), -int(row["league_rank"])), reverse=True)
    return rows


def generate_super_cup(teams: Sequence[Team], previous_standings: Sequence[dict[str, object]]) -> dict[str, object]:
    if len(teams) < 6 or len(previous_standings) < 6:
        return {
            "held": False,
            "reason": "슈퍼컵은 전년도 포인트 상위 6팀이 필요합니다.",
            "matches": [],
        }

    entrants = calculate_super_cup_points(previous_standings)[:6]
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
