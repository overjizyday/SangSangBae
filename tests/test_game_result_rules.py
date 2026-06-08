import random
import unittest
from unittest.mock import patch

from virtual_league.models import Match
from virtual_league.simulation import simulate_baseball_game, simulate_baseball_game_with_aggregate
from virtual_league.tournament_resolution import _local_post_group_first_round_slots, _resolve_two_leg_pairs


class GameResultRuleTests(unittest.TestCase):
    def test_de_can_end_in_draw(self):
        draw = None
        for seed in range(500):
            home, away = simulate_baseball_game(random.Random(seed), decisive=False, walkoff=True)
            if home == away:
                draw = (home, away)
                break

        self.assertIsNotNone(draw)

    def test_two_leg_first_leg_uses_dn_and_can_remain_drawn(self):
        matches = [
            Match("M1", "cup", "qf", "QF", 1, "A", "B", match_no=1, leg=1),
            Match("M2", "cup", "qf", "QF", 2, "B", "A", match_no=1, leg=2),
        ]

        with patch("virtual_league.tournament_resolution.simulate_baseball_game", return_value=(3, 3)), patch(
            "virtual_league.tournament_resolution.simulate_baseball_game_with_aggregate",
            return_value=(1, 0),
        ):
            winners = _resolve_two_leg_pairs(matches, [("A", "B")], random.Random(1))

        self.assertEqual((matches[0].home_score, matches[0].away_score), (3, 3))
        self.assertIsNone(matches[0].winner_team_id)
        self.assertEqual(winners, ["B"])

    def test_aggregate_le_walkoff_uses_two_leg_total_not_current_game_score(self):
        half_innings = iter([0, 5] + [0] * 15)

        def fake_half(_rng):
            return next(half_innings)

        def fake_controlled(_rng, add_runs, _should_stop):
            add_runs(5)
            return 5

        with patch("virtual_league.simulation._simulate_half_inning", fake_half), patch(
            "virtual_league.simulation._simulate_half_inning_controlled",
            fake_controlled,
        ):
            home, away = simulate_baseball_game_with_aggregate(
                random.Random(1),
                prior_away_total=9,
                prior_home_total=0,
            )

        self.assertEqual((home, away), (10, 0))

    def test_le_gives_home_half_after_away_scores_in_extra_innings(self):
        half_innings = iter([0] * 17 + [1])
        bottom_calls = []

        def fake_half(_rng):
            return next(half_innings)

        def fake_controlled(_rng, _add_runs, _should_stop):
            bottom_calls.append(True)
            return 0

        with patch("virtual_league.simulation._simulate_half_inning", fake_half), patch(
            "virtual_league.simulation._simulate_half_inning_controlled",
            fake_controlled,
        ):
            home, away = simulate_baseball_game(random.Random(1), decisive=True, walkoff=True)

        self.assertEqual((home, away), (0, 1))
        self.assertEqual(len(bottom_calls), 2)

    def test_local_post_group_first_round_pairs_runner_up_at_group_winner_home(self):
        slots = _local_post_group_first_round_slots(
            [
                ["A1", "A2"],
                ["B1", "B2"],
                ["C1", "C2"],
                ["D1", "D2"],
            ]
        )

        self.assertEqual(slots, ["B1", "A2", "A1", "B2", "D1", "C2", "C1", "D2"])


if __name__ == "__main__":
    unittest.main()
