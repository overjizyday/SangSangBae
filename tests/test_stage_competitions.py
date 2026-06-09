import json
import tempfile
import unittest
from pathlib import Path

from virtual_league.championship import generate_championship
from virtual_league.fa_cup import generate_fa_cup
from virtual_league.models import Match, Team
from virtual_league.season import (
    create_season,
    load_previous_championship_standings,
    load_previous_local_cup_winner_id,
)
from virtual_league.super_cup import generate_super_cup
from virtual_league.tournament_resolution import _build_knockout_standings


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


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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

    def test_previous_local_cup_winner_prefers_previous_cup_over_league(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "1970" / "local_cup.json",
                {
                    "held": True,
                    "standings": [
                        {"team_id": "T05", "team_name": "?05", "rank": 1},
                        {"team_id": "T06", "team_name": "?06", "rank": 2},
                    ],
                },
            )
            write_json(root / "1970" / "standings.json", standings(8))

            self.assertEqual(load_previous_local_cup_winner_id(root, 1971), "T05")

    def test_previous_local_cup_winner_falls_back_to_league_when_no_previous_cup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "1970" / "standings.json", standings(8))

            self.assertEqual(load_previous_local_cup_winner_id(root, 1971), "T01")

    def test_previous_championship_standings_prefers_previous_championship(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "1970" / "championship.json",
                {
                    "held": True,
                    "standings": [
                        {"team_id": "T07", "team_name": "?07", "rank": 1},
                        {"team_id": "T03", "team_name": "?03", "rank": 2},
                        {"team_id": "T01", "team_name": "?01", "rank": 3},
                    ],
                },
            )
            write_json(root / "1970" / "standings.json", standings(8))

            previous = load_previous_championship_standings(root, 1971)
            self.assertEqual([row["team_id"] for row in previous[:3]], ["T07", "T03", "T01"])

    def test_previous_championship_standings_falls_back_to_league_when_no_previous_championship(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "1970" / "standings.json", standings(8))

            previous = load_previous_championship_standings(root, 1971)
            self.assertEqual([row["team_id"] for row in previous[:3]], ["T01", "T02", "T03"])

    def test_knockout_standings_order_preliminary_rounds_by_late_exit(self):
        matches = [
            Match(
                id="CH-PRELIMINARY-11-001",
                competition="championship",
                stage="preliminary",
                round="R1",
                week=11,
                home_team_id="T01",
                away_team_id="T02",
                home_score=1,
                away_score=0,
                winner_team_id="T01",
                loser_team_id="T02",
            ),
            Match(
                id="CH-PRELIMINARY-12-001",
                competition="championship",
                stage="preliminary",
                round="R2",
                week=12,
                home_team_id="T03",
                away_team_id="T04",
                home_score=1,
                away_score=0,
                winner_team_id="T03",
                loser_team_id="T04",
            ),
        ]

        rows = _build_knockout_standings(matches, "championship")
        ranks = {row["team_id"]: row["rank"] for row in rows}

        self.assertLess(ranks["T04"], ranks["T02"])

    def test_knockout_standings_place_final_loser_ahead_of_semifinal_losers(self):
        matches = [
            Match(
                id="CH-SF-25-001",
                competition="championship",
                stage="sf",
                round="SF",
                week=25,
                home_team_id="T01",
                away_team_id="T02",
                home_score=4,
                away_score=1,
                winner_team_id="T01",
                loser_team_id="T02",
            ),
            Match(
                id="CH-SF-25-002",
                competition="championship",
                stage="sf",
                round="SF",
                week=25,
                home_team_id="T03",
                away_team_id="T04",
                home_score=3,
                away_score=0,
                winner_team_id="T03",
                loser_team_id="T04",
            ),
            Match(
                id="CH-FINAL-29-001",
                competition="championship",
                stage="final",
                round="Final",
                week=29,
                home_team_id="T01",
                away_team_id="T03",
                home_score=2,
                away_score=5,
                winner_team_id="T03",
                loser_team_id="T01",
            ),
        ]

        rows = _build_knockout_standings(matches, "championship")
        ranks = {row["team_id"]: row["rank"] for row in rows}

        self.assertLess(ranks["T01"], ranks["T02"])
        self.assertLess(ranks["T01"], ranks["T04"])


if __name__ == "__main__":
    unittest.main()
