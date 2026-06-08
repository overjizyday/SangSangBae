import json
import tempfile
import unittest
from pathlib import Path

from virtual_league.league import generate_league_schedule, max_home_away_streak
from virtual_league.season import create_season
from virtual_league.team_registry import default_teams
from virtual_league.standings import calculate_standings


class Stage1Tests(unittest.TestCase):
    def test_create_first_season_1970_outputs_json_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            season_dir = create_season(Path(tmp), seed=11)

            self.assertEqual(season_dir.name, "1970")
            for filename in ["season.json", "teams.json", "schedule.json", "standings.json"]:
                self.assertTrue((season_dir / filename).exists(), filename)

            teams = json.loads((season_dir / "teams.json").read_text(encoding="utf-8"))
            self.assertEqual([team["name"] for team in teams], ["서산", "대구", "부산", "광주", "경산", "동대문"])
            self.assertEqual([team["region"] for team in teams], ["충청", "경상", "경상", "전라", "경상", "서울"])

            season = json.loads((season_dir / "season.json").read_text(encoding="utf-8"))
            self.assertEqual(season["year"], 1970)
            self.assertEqual(season["competitions"], ["league", "acl"])
            self.assertEqual(season["todos"], [])

    def test_existing_year_creates_next_year_with_todos(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "1970").mkdir()

            season_dir = create_season(root, seed=12)
            self.assertEqual(season_dir.name, "1971")

            season = json.loads((season_dir / "season.json").read_text(encoding="utf-8"))
            self.assertIn("league", season["competitions"])
            self.assertTrue(any("promotion_relegation_playoffs" in item for item in season["todos"]))

    def test_create_season_reads_editable_team_file_next_to_seasons_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            teams_file = root / "teams.json"
            teams_file.write_text(
                json.dumps(
                    [
                        {"id": "A", "name": "서울", "region": "서울", "professional": True},
                        {"id": "B", "name": "인천", "region": "경기", "professional": True},
                        {"id": "C", "name": "강릉", "region": "강원", "professional": True},
                        {"id": "D", "name": "청주", "region": "충청", "professional": True},
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            season_dir = create_season(root / "seasons", seed=15)
            teams = json.loads((season_dir / "teams.json").read_text(encoding="utf-8"))

            self.assertEqual([team["name"] for team in teams], ["서울", "인천", "강릉", "청주"])

    def test_schedule_is_full_round_robin_under_40_rounds_and_balanced(self):
        teams = default_teams()
        schedule = generate_league_schedule(teams, seed=13)

        self.assertEqual(max(match.round for match in schedule), 40)
        self.assertEqual(len(schedule), 120)

        raw = [
            {"home": match.home_team_id, "away": match.away_team_id}
            for match in sorted(schedule, key=lambda match: (match.round, match.id))
        ]
        self.assertLessEqual(max_home_away_streak(raw, [team.id for team in teams]), 2)

    def test_simulated_scores_and_standings_are_consistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            season_dir = create_season(Path(tmp), seed=14)
            schedule = json.loads((season_dir / "schedule.json").read_text(encoding="utf-8"))
            standings = json.loads((season_dir / "standings.json").read_text(encoding="utf-8"))

            self.assertTrue(all(match["home_score"] >= 0 for match in schedule))
            self.assertTrue(all(match["away_score"] >= 0 for match in schedule))
            self.assertEqual([row["rank"] for row in standings], list(range(1, 7)))
            self.assertEqual(sum(row["played"] for row in standings), len(schedule) * 2)


if __name__ == "__main__":
    unittest.main()
