import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from virtual_league.calendar import assign_season_days
from virtual_league.calendar_view import render_calendar_html
from virtual_league.models import Match, Team
from virtual_league.season import create_season


def make_teams(count: int) -> list[Team]:
    regions = ["서울", "경기", "강원", "충청", "전라", "경상"]
    return [
        Team(
            id=f"T{idx:02d}",
            name=f"팀{idx:02d}",
            region=regions[(idx - 1) % len(regions)],
            professional=True,
        )
        for idx in range(1, count + 1)
    ]


class CalendarTests(unittest.TestCase):
    def test_league_only_one_round_week_uses_weekend(self):
        league = [
            Match("L1", "league", "regular", 1, 20, "A", "B"),
            Match("L2", "league", "regular", 1, 20, "C", "D"),
        ]

        assign_season_days(league, [], seed=1)

        self.assertTrue(all(match.day in {"금", "토", "일"} for match in league))

    def test_league_games_in_same_round_are_spread_across_days(self):
        league = [
            Match(f"L{idx}", "league", "regular", 1, 20, f"H{idx}", f"A{idx}")
            for idx in range(1, 7)
        ]

        assign_season_days(league, [], seed=11)
        counts = Counter(match.day for match in league)

        self.assertEqual(league[0].day, "토")
        self.assertGreaterEqual(len(counts), 3)
        self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)

    def test_three_round_week_uses_tue_wed_thu_fri_sat_sun_pools(self):
        league = [
            Match("L0", "league", "regular", 1, 1, "X", "Y"),
            Match("L1", "league", "regular", 7, 7, "A", "B"),
            Match("L2", "league", "regular", 7, 7, "C", "D"),
            Match("L3", "league", "regular", 8, 7, "E", "F"),
            Match("L4", "league", "regular", 8, 7, "G", "H"),
            Match("L5", "league", "regular", 9, 7, "I", "J"),
            Match("L6", "league", "regular", 9, 7, "K", "L"),
            Match("L7", "league", "regular", 10, 10, "M", "N"),
        ]

        assign_season_days(league, [], seed=21)

        round7 = {match.day for match in league if match.round == 7}
        round8 = {match.day for match in league if match.round == 8}
        round9 = {match.day for match in league if match.round == 9}

        self.assertTrue(round7 <= {"화", "수"})
        self.assertTrue(round8 <= {"목", "금"})
        self.assertTrue(round9 <= {"토", "일"})
        self.assertEqual(len(round7), 2)
        self.assertEqual(len(round8), 2)
        self.assertEqual(len(round9), 2)

    def test_final_round_week_31_is_fixed_to_mon_thu_sun(self):
        league = [
            Match("L0", "league", "regular", 1, 1, "X", "Y"),
            Match("L1", "league", "regular", 40, 31, "A", "B"),
            Match("L2", "league", "regular", 40, 31, "C", "D"),
            Match("L3", "league", "regular", 41, 31, "E", "F"),
            Match("L4", "league", "regular", 41, 31, "G", "H"),
            Match("L5", "league", "regular", 42, 31, "I", "J"),
            Match("L6", "league", "regular", 42, 31, "K", "L"),
        ]

        assign_season_days(league, [], seed=17)

        round40 = {match.day for match in league if match.round == 40}
        round41 = {match.day for match in league if match.round == 41}
        round42 = {match.day for match in league if match.round == 42}

        self.assertEqual(round40, {"월"})
        self.assertEqual(round41, {"목"})
        self.assertEqual(round42, {"일"})

    def test_cup_final_days_at_week_29_local_then_championship(self):
        local = {
            "held": True,
            "matches": [Match("LCF", "local_cup", "final", "Final", 29, "A", "B")],
        }
        championship = {
            "held": True,
            "matches": [Match("CHF", "championship", "final", "Final", 29, "C", "D")],
        }

        assign_season_days([], [local, championship], seed=2)

        self.assertEqual(local["matches"][0].day, "토")
        self.assertEqual(championship["matches"][0].day, "일")

    def test_local_cup_po_is_monday_and_group_uses_rule_days(self):
        local = {
            "held": True,
            "matches": [
                Match("PO", "local_cup", "regional_po", "PO", 15, "A", "B", match_no=1),
                Match("G1", "local_cup", "group", "Group", 15, "A1", "A2", match_no=1),
                Match("G2", "local_cup", "group", "Group", 15, "A1", "A3", match_no=2),
                Match("G3", "local_cup", "group", "Group", 15, "A1", "A4", match_no=3),
                Match("G4", "local_cup", "group", "Group", 15, "B1", "B2", match_no=4),
            ],
        }

        assign_season_days([], [local], seed=3)

        self.assertEqual(local["matches"][0].day, "월")
        self.assertEqual([match.day for match in local["matches"][1:4]], ["수", "금", "토"])
        self.assertEqual(local["matches"][4].day, "목")

    def test_super_cup_uses_dedicated_weekend_days(self):
        super_cup = {
            "held": True,
            "matches": [
                Match("SC1", "super_cup", "league", 1, 1, "A", "B"),
                Match("SC2", "super_cup", "league", 2, 1, "C", "D"),
                Match("SC3", "super_cup", "league", 3, 2, "A", "C"),
                Match("SC4", "super_cup", "league", 4, 2, "B", "D"),
                Match("SC5", "super_cup", "league", 5, 2, "A", "D"),
            ],
        }

        assign_season_days([], [super_cup], seed=5)

        self.assertEqual([match.day for match in super_cup["matches"]], ["토", "일", "목", "토", "일"])

    def test_created_season_writes_day_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            season_dir = create_season(Path(tmp), teams=make_teams(6), seed=4)
            schedule = json.loads((season_dir / "schedule.json").read_text(encoding="utf-8"))

            self.assertTrue(all(match["day"] in {"월", "화", "수", "목", "금", "토", "일"} for match in schedule))
            self.assertTrue((season_dir / "calendar.html").exists())
            html = (season_dir / "calendar.html").read_text(encoding="utf-8")
            self.assertIn("시즌 캘린더", html)
            self.assertTrue((season_dir / "results.csv").exists())

    def test_calendar_renderer_folds_four_or_more_same_type_matches(self):
        matches = [
            Match(f"L{idx}", "league", "regular", 1, 20, f"H{idx}", f"A{idx}", day="화")
            for idx in range(1, 5)
        ]
        html = render_calendar_html(1970, matches, {})

        self.assertIn("<details", html)

    def test_calendar_renderer_shows_away_team_before_home_team(self):
        match = Match("L1", "league", "regular", 1, 20, "HOME", "AWAY", day="화", home_score=3, away_score=5)
        html = render_calendar_html(1970, [match], {"HOME": "Home FC", "AWAY": "Away FC"})

        self.assertIn("Away FC vs Home FC", html)
        self.assertIn("5 - 3", html)
        self.assertNotIn("Home FC vs Away FC", html)


if __name__ == "__main__":
    unittest.main()
