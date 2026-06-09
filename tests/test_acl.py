import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from virtual_league.acl import _super_cup_acl_candidates, association_city_pool, generate_acl, rank_countries
from virtual_league.acl_view import render_acl_participants_html
from virtual_league.models import Match, Team
from virtual_league.standings_view import build_competition_tables
from virtual_league.season import create_season
from virtual_league.super_cup import generate_super_cup


def make_teams(count: int) -> list[Team]:
    regions = ["Seoul", "Gyeonggi", "Gangwon", "Chungcheong", "Jeolla", "Gyeongsang"]
    return [
        Team(
            id=f"T{idx:02d}",
            name=f"Team {idx:02d}",
            region=regions[(idx - 1) % len(regions)],
            professional=True,
        )
        for idx in range(1, count + 1)
    ]


def standings(count: int) -> list[dict[str, object]]:
    return [
        {
            "rank": idx,
            "team_id": f"T{idx:02d}",
            "team_name": f"Team {idx:02d}",
            "points": count - idx,
        }
        for idx in range(1, count + 1)
    ]


class AclTests(unittest.TestCase):
    def test_korean_acl_candidates_use_super_cup_final_standings(self):
        teams = make_teams(6)
        super_cup = {
            "held": True,
            "entrants": [
                {"team_id": "T01", "points": 10},
                {"team_id": "T02", "points": 5},
                {"team_id": "T03", "points": 1},
                {"team_id": "T04", "points": 0},
                {"team_id": "T05", "points": 0},
                {"team_id": "T06", "points": 0},
            ],
            "standings": [
                {"team_id": "T01", "team_name": "Team 01", "points": 17},
                {"team_id": "T02", "team_name": "Team 02", "points": 14},
                {"team_id": "T03", "team_name": "Team 03", "points": 11},
                {"team_id": "T06", "team_name": "Team 06", "points": 6},
                {"team_id": "T05", "team_name": "Team 05", "points": 4},
                {"team_id": "T04", "team_name": "Team 04", "points": 3},
            ],
        }

        candidates = _super_cup_acl_candidates(super_cup, teams)

        self.assertEqual([row["team_id"] for row in candidates[:5]], ["T01", "T02", "T03", "T06", "T05"])

    def test_country_ranking_has_west_and_east_a_to_v(self):
        ranking = rank_countries(51)

        self.assertEqual(len(ranking), 48)
        west = [row for row in ranking if row["region"] == "west"]
        east = [row for row in ranking if row["region"] == "east"]
        self.assertEqual([row["slot"] for row in west], list("ABCDEFGHIJKLMNOPQRSTUVWXY"))
        self.assertEqual([row["slot"] for row in east], list("ABCDEFGHIJKLMNOPQRSTUVW"))
        self.assertEqual(east[1]["country"], "대한민국")

    def test_acl_ranking_html_adds_display_only_reserve_slots(self):
        ranking = rank_countries(51)
        html = render_acl_participants_html(
            {
                "country_rankings": ranking,
                "groups": {},
                "participants": {},
            }
        )

        self.assertIn("W", html)
        self.assertIn("Z", html)
        self.assertNotIn("예비 슬롯", html)

    def test_acl_city_pools_are_loaded_from_csv_columns(self):
        self.assertEqual(len(association_city_pool("대한민국")), 10)
        self.assertEqual(len(association_city_pool("일본")), 10)
        self.assertEqual(len(association_city_pool("홍콩")), 10)
        self.assertTrue(all(association_city_pool("일본")))
        self.assertTrue(all(association_city_pool("홍콩")))

    def test_acl_generates_three_leagues_with_16_teams_per_region(self):
        teams = make_teams(28)
        super_cup = generate_super_cup(teams, standings(28))

        with tempfile.TemporaryDirectory() as tmp:
            acl = generate_acl(teams, super_cup, Path(tmp), 1971, seed=52)

        self.assertTrue(acl["held"])
        self.assertEqual(len(acl["korean_qualifiers"]), 5)
        self.assertEqual(len(acl["po"]), 8)

        for league in ["ACL1", "ACL2", "ACL3"]:
            self.assertEqual(len(acl["participants"][league]), 32)
            self.assertEqual(set(acl["groups"][league].keys()), {"A", "B", "C", "D", "E", "F", "G", "H"})
            self.assertTrue(all(len(members) == 4 for members in acl["groups"][league].values()))
            self.assertTrue(all(item["team_name"] for item in acl["participants"][league]))

            east_b_names = [
                item["team_name"]
                for item in acl["participants"][league]
                if item["region"] == "east" and item["slot"] == "B"
            ]
            if league in {"ACL1", "ACL2"}:
                self.assertTrue(east_b_names)
                self.assertTrue(all(name.startswith("Team ") for name in east_b_names))
            else:
                self.assertFalse(east_b_names)

            counts = Counter(item["region"] for item in acl["participants"][league])
            self.assertEqual(counts["west"], 16)
            self.assertEqual(counts["east"], 16)

            by_country: dict[str, list[str]] = {}
            for item in acl["participants"][league]:
                by_country.setdefault(item["country"], []).append(item["team_name"])
            for country, names in by_country.items():
                self.assertEqual(
                    len(names),
                    len(set(names)),
                    msg=f"{league} {country} has duplicate team names: {names}",
                )

        group_matches = [match for match in acl["matches"] if "group" in match.stage]
        self.assertEqual(len(group_matches), 288)
        self.assertEqual(set(match.week for match in group_matches), {4, 6, 8, 10, 12, 14})

        r16_matches = [match for match in acl["matches"] if match.round == "R16"]
        qf_matches = [match for match in acl["matches"] if match.round == "QF"]
        sf_matches = [match for match in acl["matches"] if match.round == "SF"]
        finals = [match for match in acl["matches"] if match.round == "Final"]
        self.assertEqual(len(r16_matches), 48)
        self.assertEqual(len(qf_matches), 24)
        self.assertEqual(len(sf_matches), 12)
        self.assertEqual(len(finals), 3)
        self.assertEqual(set(match.week for match in r16_matches), {19, 20})
        self.assertEqual(set(match.week for match in qf_matches), {23, 24})
        self.assertEqual(set(match.week for match in sf_matches), {27, 28})
        self.assertEqual(set(match.week for match in finals), {32})
        self.assertTrue(all(match.home_team_id == "west_SF_1" for match in finals if acl["final_home_region"] == "west"))
        self.assertTrue(all(match.home_team_id == "east_SF_1" for match in finals if acl["final_home_region"] == "east"))

        self.assertTrue(any(item["country"] == "대한민국" for item in acl["participants"]["ACL1"]))

    def test_acl_without_super_cup_shifts_korea_slot_to_next_country(self):
        teams = make_teams(28)

        with tempfile.TemporaryDirectory() as tmp:
            acl = generate_acl(teams, None, Path(tmp), 1971, seed=52)

        shifted_east = [row for row in acl["country_rankings"] if row["region"] == "east"]
        normal_east = [row for row in rank_countries(52) if row["region"] == "east"]
        east_participants = [item for item in acl["participants"]["ACL1"] if item["region"] == "east"]

        self.assertTrue(acl["held"])
        self.assertEqual(len(acl["korean_qualifiers"]), 0)
        self.assertNotIn("대한민국", {row["country"] for row in shifted_east})
        self.assertEqual(shifted_east[1]["country"], normal_east[2]["country"])
        self.assertEqual(len(east_participants), 16)

    def test_acl_fallback_champion_slots_use_real_countries(self):
        teams = make_teams(28)

        with tempfile.TemporaryDirectory() as tmp:
            acl = generate_acl(teams, None, Path(tmp), 1970, seed=52)

        z_rows = [
            row
            for league_rows in acl["participants"].values()
            for row in league_rows
            if row["slot"] == "Z"
        ]

        self.assertTrue(z_rows)
        self.assertTrue(all(row["country"] != "Unknown" for row in z_rows))
        self.assertTrue(all(not str(row["team_name"]).startswith("Unknown") for row in z_rows))
        self.assertTrue(all(str(row["team_id"]).isascii() for row in z_rows))
        self.assertTrue(all(not any("\uac00" <= ch <= "\ud7a3" for ch in str(row["team_id"])) for row in z_rows))

    def test_1970_season_still_writes_acl(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            season_dir = create_season(root, teams=make_teams(28), seed=51)

            acl = json.loads((season_dir / "acl.json").read_text(encoding="utf-8"))
            season = json.loads((season_dir / "season.json").read_text(encoding="utf-8"))

            self.assertEqual(season["year"], 1970)
            self.assertIn("acl", season["competitions"])
            self.assertTrue(acl["held"])
            self.assertTrue((season_dir / "acl_participants.html").exists())

    def test_acl_even_year_final_home_is_east(self):
        teams = make_teams(28)
        super_cup = generate_super_cup(teams, standings(28))

        with tempfile.TemporaryDirectory() as tmp:
            acl = generate_acl(teams, super_cup, Path(tmp), 1972, seed=52)

        finals = [match for match in acl["matches"] if match.round == "Final"]
        self.assertTrue(all(match.home_team_id == "east_SF_1" for match in finals))
        self.assertEqual(acl["final_home_region"], "east")

    def test_second_season_writes_acl_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_season(root, teams=make_teams(28), seed=53)
            season_dir = create_season(root, teams=make_teams(28), seed=54)

            acl = json.loads((season_dir / "acl.json").read_text(encoding="utf-8"))
            season = json.loads((season_dir / "season.json").read_text(encoding="utf-8"))

            self.assertTrue(acl["held"])
            self.assertIn("acl", season["competitions"])
            self.assertTrue((season_dir / "acl_participants.html").exists())
            html = (season_dir / "acl_participants.html").read_text(encoding="utf-8")
            self.assertIn("대체", html)
            self.assertIn("국가 충돌", html)
            standings = (season_dir / "standings.csv").read_text(encoding="utf-8")
            self.assertNotIn("TBD_", standings)
            self.assertNotIn("PENDING_", standings)

    def test_acl_participants_renderer_does_not_show_team_ids(self):
        html = render_acl_participants_html(
            {
                "country_rankings": [
                    {"regional_rank": 1, "slot": "A", "country": "대한민국", "region": "east", "adjusted_score": 100}
                ],
                "groups": {"ACL1": {"A": ["KOR_A_FC"]}},
                "participants": {
                    "ACL1": [
                        {
                            "slot": "A",
                            "country": "대한민국",
                            "team_name": "서울",
                            "team_id": "KOR_A_FC",
                            "region": "east",
                        }
                    ]
                },
            }
        )

        self.assertNotIn("ID</th>", html)
        self.assertNotIn("team_id", html)
        self.assertNotIn("KOR_A_FC</td>", html)
        self.assertIn("서울", html)

    def test_acl_standings_rank_champions_first(self):
        base = Path("seasons/1970")
        teams = [Team(**item) for item in json.loads((base / "teams.json").read_text(encoding="utf-8"))]
        acl = json.loads((base / "acl.json").read_text(encoding="utf-8"))
        acl["matches"] = [Match(**item) for item in acl["matches"]]

        tables = build_competition_tables([], [acl], teams)

        for league in ["ACL1", "ACL2", "ACL3"]:
            champion_id = acl["champions"][league]
            champion_name = next(
                item["team_name"]
                for item in acl["participants"][league]
                if item["team_id"] == champion_id
            )
            self.assertEqual(tables[league][0]["team_id"], champion_id)
            self.assertEqual(tables[league][0]["team_name"], champion_name)

    def test_acl_participant_team_names_are_unique_and_not_english(self):
        teams = make_teams(28)
        super_cup = generate_super_cup(teams, standings(28))

        with tempfile.TemporaryDirectory() as tmp:
            acl = generate_acl(teams, super_cup, Path(tmp), 1971, seed=52)

        for league in ["ACL1", "ACL2", "ACL3"]:
            rows = acl["participants"][league]
            names = [row["team_name"] for row in rows]
            self.assertEqual(len(names), len(set(names)), msg=f"{league} has duplicate team names: {names}")

        participant_names = {
            item["team_id"]: item["team_name"]
            for items in acl["participants"].values()
            for item in items
        }
        for match in acl["matches"]:
            home_name = participant_names.get(match.home_team_id)
            away_name = participant_names.get(match.away_team_id)
            if home_name is None or away_name is None:
                continue
            self.assertNotEqual(home_name, away_name, msg=f"{match.id} has duplicate team names: {home_name}")


if __name__ == "__main__":
    unittest.main()
