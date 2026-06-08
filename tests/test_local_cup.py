import json
import tempfile
import unittest
from pathlib import Path

from virtual_league.local_cup import REGIONS, generate_local_cup, select_local_cup_teams
from virtual_league.models import Team
from virtual_league.season import create_season
from virtual_league.tournament_resolution import resolve_local_cup


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


class LocalCupTests(unittest.TestCase):
    def test_local_cup_is_not_held_below_14_teams(self):
        cup = generate_local_cup(make_teams(13), "T01", seed=21)

        self.assertFalse(cup["held"])
        self.assertEqual(cup["matches"], [])

    def test_local_cup_14_teams_generates_qf_without_group_stage(self):
        cup = generate_local_cup(make_teams(14), "T01", seed=22)
        resolve_local_cup(cup, seed=22)

        self.assertTrue(cup["held"])
        self.assertEqual(cup["participant_count"], 14)
        stages = [match.stage for match in cup["matches"]]
        self.assertIn("regional_qualifier", stages)
        self.assertNotIn("group", stages)
        self.assertEqual(sum(1 for match in cup["matches"] if match.stage == "qf"), 8)
        qf_pairs = [
            (match.home_team_id, match.away_team_id)
            for match in cup["matches"]
            if match.stage == "qf"
        ]
        self.assertTrue(all(home != away for home, away in qf_pairs))
        finals = [match for match in cup["matches"] if match.stage == "final"]
        self.assertTrue(finals)
        self.assertNotEqual(finals[0].home_team_id, finals[0].away_team_id)

    def test_professional_teams_are_required_and_amateurs_fill_valid_total(self):
        teams = [
            Team(id=f"P{idx:02d}", name=f"프로{idx:02d}", region="서울", professional=True)
            for idx in range(1, 13)
        ] + [
            Team(id=f"A{idx:02d}", name=f"아마{idx:02d}", region="경기", professional=False)
            for idx in range(1, 6)
        ]

        selected = select_local_cup_teams(teams, "P01", seed=23)
        self.assertEqual(len(selected), 14)
        self.assertEqual(sum(1 for team in selected if team.id.startswith("P")), 12)

    def test_second_season_writes_local_cup_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_season(root, teams=make_teams(14), seed=24)
            season_dir = create_season(root, teams=make_teams(14), seed=25)

            local_cup = json.loads((season_dir / "local_cup.json").read_text(encoding="utf-8"))
            season = json.loads((season_dir / "season.json").read_text(encoding="utf-8"))
            standings = (season_dir / "standings.csv").read_text(encoding="utf-8")

            self.assertEqual(season_dir.name, "1971")
            self.assertTrue(local_cup["held"])
            self.assertIn("local_cup", season["competitions"])
            self.assertNotIn("TBD_", standings)
            self.assertNotIn("PENDING_", standings)

    def test_previous_winner_keeps_original_regional_po_slot(self):
        teams = [
            Team(id="R1", name="R1", region=REGIONS[0], professional=True),
            Team(id="R2", name="R2", region=REGIONS[0], professional=True),
            Team(id="R3", name="R3", region=REGIONS[0], professional=True),
            Team(id="R4", name="R4", region=REGIONS[0], professional=True),
            Team(id="WIN", name="WIN", region=REGIONS[0], professional=True),
        ] + [
            Team(id=f"O{idx}", name=f"O{idx}", region=REGIONS[(idx % (len(REGIONS) - 1)) + 1], professional=True)
            for idx in range(1, 10)
        ]

        cup = generate_local_cup(teams, "WIN", seed=31)
        self.assertTrue(cup["held"])
        rule = next(item for item in cup["regional_slot_rules"] if item["region"] == REGIONS[0])
        self.assertEqual(rule["original_size"], 5)
        self.assertEqual(rule["direct_slots"], 2)
        self.assertEqual(rule["po_slots"], 1)

        resolve_local_cup(cup, seed=31)
        po_matches = [match for match in cup["matches"] if match.stage == "regional_po"]
        self.assertTrue(po_matches)
        po_teams = {team_id for match in po_matches for team_id in [match.home_team_id, match.away_team_id]}
        self.assertTrue(po_teams & {"R1", "R2", "R3", "R4"})


if __name__ == "__main__":
    unittest.main()
