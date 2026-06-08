import json
import tempfile
import unittest
from pathlib import Path

from virtual_league.championship import generate_championship
from virtual_league.fa_cup import generate_fa_cup
from virtual_league.models import Team
from virtual_league.season import create_season
from virtual_league.super_cup import generate_super_cup


def make_teams(count: int, amateur_from: int | None = None) -> list[Team]:
    regions = ["서울", "경기", "강원", "충청", "전라", "경상"]
    return [
        Team(
            id=f"T{idx:02d}",
            name=f"팀{idx:02d}",
            region=regions[(idx - 1) % len(regions)],
            professional=amateur_from is None or idx < amateur_from,
        )
        for idx in range(1, count + 1)
    ]


def standings(count: int) -> list[dict[str, object]]:
    return [
        {
            "rank": idx,
            "team_id": f"T{idx:02d}",
            "team_name": f"팀{idx:02d}",
            "points": count - idx,
        }
        for idx in range(1, count + 1)
    ]


class StageCompetitionsTests(unittest.TestCase):
    def test_championship_14_teams_uses_one_preliminary_round(self):
        with tempfile.TemporaryDirectory() as tmp:
            cup = generate_championship(make_teams(14), standings(14), Path(tmp), 1971)

            self.assertTrue(cup["held"])
            self.assertEqual(cup["participant_count"], 14)
            self.assertEqual(cup["auto_qf"], ["T01", "T02"])
            self.assertEqual(cup["rounds_needed"], 1)
            self.assertEqual(sum(1 for match in cup["matches"] if match.round == "R1"), 6)
            self.assertTrue(all(match.week == 18 for match in cup["matches"] if match.round == "R1"))

    def test_championship_30_teams_selects_26_and_three_rounds(self):
        with tempfile.TemporaryDirectory() as tmp:
            cup = generate_championship(make_teams(30), standings(30), Path(tmp), 1971)

            self.assertTrue(cup["held"])
            self.assertEqual(cup["participant_count"], 26)
            self.assertEqual(cup["rounds_needed"], 3)
            self.assertEqual([match.week for match in cup["matches"] if match.round == "R1"][:1], [11])

    def test_fa_cup_requires_28_teams_and_writes_r16(self):
        cup = generate_fa_cup(make_teams(28), standings(28), seed=31)

        self.assertTrue(cup["held"])
        self.assertEqual(cup["auto_r16"], ["T01", "T02", "T03", "T04"])
        self.assertEqual(sum(1 for match in cup["matches"] if match.round == "R16"), 16)

    def test_super_cup_uses_top_six_points_and_five_rounds(self):
        cup = generate_super_cup(make_teams(6), standings(6))

        self.assertTrue(cup["held"])
        self.assertEqual(len(cup["entrants"]), 6)
        self.assertEqual(len(cup["matches"]), 15)
        self.assertEqual(sum(1 for match in cup["matches"] if match.week == 1), 6)
        self.assertEqual(sum(1 for match in cup["matches"] if match.week == 2), 9)

    def test_super_cup_adds_league_and_cup_bonus_points(self):
        cup = generate_super_cup(
            make_teams(8),
            standings(8),
            {"local_cup": {"winner_id": "T07", "runner_up_id": "T08"}},
        )

        points_by_team = {row["team_id"]: row["points"] for row in cup["entrants"]}
        self.assertEqual(points_by_team["T01"], 10)
        self.assertEqual(points_by_team["T02"], 5)
        self.assertEqual(points_by_team["T03"], 1)
        self.assertEqual(points_by_team["T07"], 7)
        self.assertEqual(points_by_team["T08"], 3)
        self.assertNotIn("T06", points_by_team)

    def test_second_season_writes_new_competition_json_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_season(root, teams=make_teams(28), seed=41)
            season_dir = create_season(root, teams=make_teams(28), seed=42)

            season = json.loads((season_dir / "season.json").read_text(encoding="utf-8"))
            self.assertIn("championship", season["competitions"])
            self.assertIn("fa_cup", season["competitions"])
            self.assertIn("super_cup", season["competitions"])
            for filename in ["championship.json", "fa_cup.json", "super_cup.json"]:
                self.assertTrue((season_dir / filename).exists(), filename)


if __name__ == "__main__":
    unittest.main()
