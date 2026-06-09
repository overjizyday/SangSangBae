import json
import tempfile
import unittest
from pathlib import Path

from virtual_league.pages_site import write_pages_site


class PagesSiteTests(unittest.TestCase):
    def test_write_pages_site_honors_replay_started_at_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            seasons_root = root / "seasons"
            season_dir = seasons_root / "1971"
            output_dir = root / "docs"
            season_dir.mkdir(parents=True)

            (season_dir / "season.json").write_text(
                json.dumps({"year": 1971, "competitions": ["league"]}, ensure_ascii=False),
                encoding="utf-8",
            )
            (season_dir / "teams.json").write_text(
                json.dumps(
                    [
                        {"id": "A", "name": "Alpha", "region": "X", "professional": True},
                        {"id": "B", "name": "Beta", "region": "X", "professional": True},
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (season_dir / "live_feed.json").write_text(
                json.dumps(
                    [
                        {
                            "match_id": "M1",
                            "competition": "league",
                            "stage": "regular",
                            "round": 1,
                            "week": 1,
                            "day": "월",
                            "home_team_id": "A",
                            "away_team_id": "B",
                            "home_score": 2,
                            "away_score": 1,
                            "events": [],
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            replay_started_at = "2020-01-01T00:00:00+00:00"
            write_pages_site(seasons_root, output_dir, season_dir=season_dir, replay_started_at=replay_started_at)

            season_payload = json.loads((output_dir / "season.json").read_text(encoding="utf-8"))
            manifest_payload = json.loads((output_dir / "replay_manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(season_payload["replay_started_at"], replay_started_at)
            self.assertEqual(manifest_payload["replay_started_at"], replay_started_at)
            self.assertEqual(manifest_payload["chunks"][0]["start_run_at"], replay_started_at)


if __name__ == "__main__":
    unittest.main()
