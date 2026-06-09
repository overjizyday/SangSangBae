import unittest

from virtual_league.models import Match, Team
from virtual_league.standings_view import build_competition_tables


class StandingsViewTests(unittest.TestCase):
    def test_knockout_rows_keep_round_priority_and_sort_within_round_by_date(self):
        teams = [
            Team(id="T01", name="Team 01"),
            Team(id="T02", name="Team 02"),
            Team(id="T03", name="Team 03"),
            Team(id="T04", name="Team 04"),
            Team(id="T05", name="Team 05"),
            Team(id="T06", name="Team 06"),
        ]
        league_standings = [
            {
                "rank": idx,
                "team_id": team.id,
                "team_name": team.name,
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "goals_for": 0,
                "goals_against": 0,
                "goal_difference": 0,
                "points": 0,
            }
            for idx, team in enumerate(teams, start=1)
        ]

        competition = {
            "competition": "championship",
            "held": True,
            "standings": league_standings,
            "matches": [
                Match(
                    id="m-final",
                    competition="championship",
                    stage="final",
                    round="Final",
                    week=12,
                    day="\ud654",
                    home_team_id="T05",
                    away_team_id="T06",
                    home_score=1,
                    away_score=0,
                    winner_team_id="T05",
                    loser_team_id="T06",
                ),
                Match(
                    id="m-po",
                    competition="championship",
                    stage="po",
                    round="PO",
                    week=11,
                    day="\uae08",
                    home_team_id="T05",
                    away_team_id="T06",
                    home_score=2,
                    away_score=0,
                    winner_team_id="T05",
                    loser_team_id="T06",
                ),
                Match(
                    id="m-qf-early",
                    competition="championship",
                    stage="qf",
                    round="QF",
                    week=10,
                    day="\uc6d4",
                    home_team_id="T03",
                    away_team_id="T04",
                    home_score=3,
                    away_score=0,
                    winner_team_id="T03",
                    loser_team_id="T04",
                ),
                Match(
                    id="m-qf-late",
                    competition="championship",
                    stage="qf",
                    round="QF",
                    week=10,
                    day="\uc218",
                    match_no=2,
                    home_team_id="T01",
                    away_team_id="T02",
                    home_score=2,
                    away_score=1,
                    winner_team_id="T01",
                    loser_team_id="T02",
                ),
            ],
        }

        tables = build_competition_tables(league_standings, [competition], teams)
        knockout_rows = tables["__knockout__championship"]

        self.assertEqual([row["round"] for row in knockout_rows], ["PO", "QF", "QF", "Final"])
        self.assertEqual([row["match"] for row in knockout_rows[:3]], [0, 0, 2])


if __name__ == "__main__":
    unittest.main()
