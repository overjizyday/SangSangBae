import json
import tempfile
import unittest
from pathlib import Path

from virtual_league.team_registry import add_team, ensure_team_file


class TeamRegistryTests(unittest.TestCase):
    def test_ensure_team_file_creates_default_with_regions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "teams.json"
            teams = ensure_team_file(path)

            self.assertTrue(path.exists())
            self.assertEqual([team.region for team in teams], ["충청", "경상", "경상", "전라", "경상", "서울"])

    def test_add_team_appends_to_editable_team_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "teams.json"
            team = add_team(path, "수원", "경기")
            data = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(team.id, "T07")
            self.assertEqual(data[-1]["name"], "수원")
            self.assertEqual(data[-1]["region"], "경기")


if __name__ == "__main__":
    unittest.main()
