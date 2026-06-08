from __future__ import annotations

from collections.abc import Iterable, Sequence

from .models import Match, Standing, Team


def calculate_standings(teams: Sequence[Team], matches: Iterable[Match]) -> list[Standing]:
    names = {team.id: team.name for team in teams}
    table = {
        team.id: {
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_for": 0,
            "goals_against": 0,
            "points": 0,
        }
        for team in teams
    }

    for match in matches:
        if match.home_score is None or match.away_score is None:
            continue
        if match.home_team_id not in table or match.away_team_id not in table:
            continue

        home = table[match.home_team_id]
        away = table[match.away_team_id]
        home["played"] += 1
        away["played"] += 1
        home["goals_for"] += match.home_score
        home["goals_against"] += match.away_score
        away["goals_for"] += match.away_score
        away["goals_against"] += match.home_score

        if match.home_score > match.away_score:
            home["wins"] += 1
            away["losses"] += 1
            home["points"] += 3
        elif match.home_score < match.away_score:
            away["wins"] += 1
            home["losses"] += 1
            away["points"] += 3
        else:
            home["draws"] += 1
            away["draws"] += 1
            home["points"] += 1
            away["points"] += 1

    rows = []
    for team_id, values in table.items():
        goal_difference = values["goals_for"] - values["goals_against"]
        rows.append(
            Standing(
                rank=0,
                team_id=team_id,
                team_name=names[team_id],
                played=values["played"],
                wins=values["wins"],
                draws=values["draws"],
                losses=values["losses"],
                goals_for=values["goals_for"],
                goals_against=values["goals_against"],
                goal_difference=goal_difference,
                points=values["points"],
            )
        )

    rows.sort(
        key=lambda row: (
            row.points,
            row.goal_difference,
            row.goals_for,
            -row.goals_against,
            row.team_name,
        ),
        reverse=True,
    )

    for rank, row in enumerate(rows, start=1):
        row.rank = rank
    return rows
