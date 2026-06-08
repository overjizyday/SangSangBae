import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from virtual_league.live_view import render_live_dashboard, replay_season
from virtual_league.models import Team


class LiveViewTests(unittest.TestCase):
    def test_live_dashboard_renders_plate_appearance_state(self):
        teams = [Team(id="A", name="Alpha"), Team(id="B", name="Beta")]
        state = {
            "season_year": 1970,
            "groups": [((1, "Mon"), [{"match_id": "M1", "competition": "league", "week": 1, "day": "Mon", "home_team_id": "A", "away_team_id": "B", "events": [{"inning": 1, "half": "top", "event": "single", "outs_before": 0, "outs_after": 0, "bases_before": "-", "bases_after": "1B", "score_away_before": 0, "score_home_before": 0, "score_away_after": 0, "score_home_after": 0, "runs_scored": 0, "half_over": False}] }])],
            "group_index": 0,
            "progress_by_match": {"M1": 1},
            "started_at": datetime(2026, 1, 1, 12, 0),
            "tick_seconds": 2,
            "virtual_day_minutes": 5,
            "tick_count": 1,
            "teams": teams,
        }

        html = render_live_dashboard(state)
        self.assertIn("Inning 1 top", html)
        self.assertIn("Last play: single", html)
        self.assertIn("Alpha", html)
        self.assertIn("Beta", html)

    def test_replay_season_writes_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            season_dir = Path(tmp)
            (season_dir / "teams.json").write_text(
                json.dumps(
                    [
                        {"id": "A", "name": "Alpha", "region": "X", "professional": True},
                        {"id": "B", "name": "Beta", "region": "X", "professional": True},
                    ]
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
                            "day": "Mon",
                            "home_team_id": "A",
                            "away_team_id": "B",
                            "home_score": 3,
                            "away_score": 1,
                            "events": [
                                {
                                    "plate_appearance": 1,
                                    "inning": 1,
                                    "half": "top",
                                    "event": "single",
                                    "outs_before": 0,
                                    "outs_after": 0,
                                    "bases_before": "-",
                                    "bases_after": "1B",
                                    "score_away_before": 0,
                                    "score_home_before": 0,
                                    "score_away_after": 0,
                                    "score_home_after": 0,
                                    "runs_scored": 0,
                                    "half_over": False,
                                }
                            ],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            dashboard = replay_season(season_dir, tick_seconds=0, virtual_day_minutes=5, open_browser=False)

            self.assertTrue(dashboard.exists())
            html = dashboard.read_text(encoding="utf-8")
            self.assertIn("Live Replay", html)
            self.assertIn("Alpha", html)
            self.assertIn("Beta", html)


if __name__ == "__main__":
    unittest.main()
