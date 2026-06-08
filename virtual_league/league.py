from __future__ import annotations

import math
import random
from collections.abc import Sequence

from .models import Match, Team

BYE = "__BYE__"
MAX_ROUNDS = 40


def rounds_per_robin(team_count: int) -> int:
    if team_count < 2:
        raise ValueError("리그 일정 생성에는 최소 2팀이 필요합니다.")
    return team_count if team_count % 2 else team_count - 1


def robin_count_for(team_count: int, max_rounds: int = MAX_ROUNDS) -> int:
    count = max_rounds // rounds_per_robin(team_count)
    if count < 1:
        raise ValueError(
            f"{team_count}팀은 1회 라운드로빈에 {rounds_per_robin(team_count)}라운드가 필요합니다."
        )
    return count


def make_single_round_robin(team_ids: Sequence[str]) -> list[list[tuple[str, str]]]:
    teams = list(team_ids)
    if len(teams) % 2:
        teams.append(BYE)

    arr = teams[:]
    rounds: list[list[tuple[str, str]]] = []

    for _ in range(len(arr) - 1):
        pairs = []
        for idx in range(len(arr) // 2):
            a = arr[idx]
            b = arr[len(arr) - 1 - idx]
            if a != BYE and b != BYE:
                pairs.append((a, b))
        rounds.append(pairs)
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]

    return rounds


def build_initial_schedule(
    team_ids: Sequence[str], robin_count: int, rng: random.Random
) -> list[dict[str, object]]:
    base_rounds = make_single_round_robin(team_ids)
    schedule: list[dict[str, object]] = []
    round_no = 1

    for robin in range(1, robin_count + 1):
        rr_rounds = [round_matches[:] for round_matches in base_rounds]
        if robin > 1:
            rng.shuffle(rr_rounds)

        for base_round_no, pairs in enumerate(rr_rounds, start=1):
            shuffled_pairs = pairs[:]
            rng.shuffle(shuffled_pairs)
            for a, b in shuffled_pairs:
                home, away = (a, b) if rng.random() < 0.5 else (b, a)
                schedule.append(
                    {
                        "round": round_no,
                        "robin": robin,
                        "base_round": base_round_no,
                        "home": home,
                        "away": away,
                    }
                )
            round_no += 1

    return schedule


def _home_away_sequences(
    schedule: Sequence[dict[str, object]], team_ids: Sequence[str]
) -> dict[str, list[str]]:
    sequences = {team_id: [] for team_id in team_ids}
    for game in schedule:
        sequences[str(game["home"])].append("H")
        sequences[str(game["away"])].append("A")
    return sequences


def max_home_away_streak(
    schedule: Sequence[dict[str, object]], team_ids: Sequence[str]
) -> int:
    sequences = _home_away_sequences(schedule, team_ids)
    max_streak = 0
    for values in sequences.values():
        current = 0
        previous = None
        for side in values:
            if side == previous:
                current += 1
            else:
                current = 1
                previous = side
            max_streak = max(max_streak, current)
    return max_streak


def _violation_score(
    schedule: Sequence[dict[str, object]], team_ids: Sequence[str], limit: int = 2
) -> tuple[float, int]:
    sequences = _home_away_sequences(schedule, team_ids)
    score = 0.0
    max_streak = 0

    for values in sequences.values():
        current = 0
        previous = None
        for side in values:
            if side == previous:
                current += 1
            else:
                current = 1
                previous = side
            max_streak = max(max_streak, current)
            if current > limit:
                score += ((current - limit) ** 2) * 100

    for values in sequences.values():
        score += abs(values.count("H") - values.count("A")) * 0.01

    return score, max_streak


def _flip_home_away(game: dict[str, object]) -> None:
    game["home"], game["away"] = game["away"], game["home"]


def generate_balanced_round_robin(
    teams: Sequence[Team],
    max_rounds: int = MAX_ROUNDS,
    seed: int = 7,
    restarts: int = 80,
    iterations: int = 120_000,
) -> list[dict[str, object]]:
    team_ids = [team.id for team in teams]
    robin_count = robin_count_for(len(team_ids), max_rounds)
    best_schedule: list[dict[str, object]] | None = None
    best_score = float("inf")

    for restart in range(restarts):
        rng = random.Random(seed + restart * 10007)
        schedule = build_initial_schedule(team_ids, robin_count, random.Random(seed + restart))
        score, max_streak = _violation_score(schedule, team_ids)
        temperature = 5.0

        for _ in range(iterations):
            if max_streak <= 2:
                return schedule

            if score < best_score:
                best_score = score
                best_schedule = [game.copy() for game in schedule]

            idx = rng.randrange(len(schedule))
            _flip_home_away(schedule[idx])
            new_score, new_max_streak = _violation_score(schedule, team_ids)
            delta = new_score - score

            if delta <= 0 or rng.random() < math.exp(-delta / max(temperature, 1e-9)):
                score = new_score
                max_streak = new_max_streak
            else:
                _flip_home_away(schedule[idx])

            temperature *= 0.99995

    if best_schedule and max_home_away_streak(best_schedule, team_ids) <= 2:
        return best_schedule

    final_streak = max_home_away_streak(best_schedule or [], team_ids)
    raise RuntimeError(f"홈/원정 연속 2경기 제한을 만족하는 일정을 찾지 못했습니다: {final_streak}")


def generate_league_schedule(
    teams: Sequence[Team], max_rounds: int = MAX_ROUNDS, seed: int = 7
) -> list[Match]:
    raw_schedule = generate_balanced_round_robin(teams, max_rounds=max_rounds, seed=seed)
    matches = []
    for idx, game in enumerate(raw_schedule, start=1):
        round_no = int(game["round"])
        matches.append(
            Match(
                id=f"L-{round_no:02d}-{idx:03d}",
                competition="league",
                stage="regular",
                round=round_no,
                week=round_no_to_week(round_no),
                home_team_id=str(game["home"]),
                away_team_id=str(game["away"]),
            )
        )
    return matches


def generate_league_final_round(standings: Sequence[object]) -> list[Match]:
    if len(standings) < 4:
        return []

    top4 = []
    for row in standings[:4]:
        if hasattr(row, "get"):
            team_id = str(row.get("team_id", ""))
        else:
            team_id = str(getattr(row, "team_id", ""))
        top4.append(team_id)
    if len(top4) < 4 or any(not team_id for team_id in top4):
        return []

    pairings = [
        (40, "월", top4[0], top4[3]),
        (40, "월", top4[1], top4[2]),
        (41, "목", top4[0], top4[2]),
        (41, "목", top4[1], top4[3]),
        (42, "일", top4[0], top4[1]),
        (42, "일", top4[2], top4[3]),
    ]

    matches: list[Match] = []
    for idx, (round_no, day, home, away) in enumerate(pairings, start=1):
        matches.append(
            Match(
                id=f"L-FR-{idx:03d}",
                competition="league",
                stage="regular",
                round=round_no,
                week=31,
                home_team_id=home,
                away_team_id=away,
                day=day,
            )
        )
    return matches


def round_no_to_week(round_no: int) -> int:
    """Map league round numbers to weeks using the 40-round template.

    The template preserves the rule that May 5 belongs to week 7 at the calendar
    layer. This stage stores week numbers only; date materialization can be added later.
    """
    week_round_counts = [
        (3, 1),
        (4, 2),
        (5, 1),
        (6, 2),
        (7, 3),
        (8, 2),
        (10, 2),
        (11, 1),
        (12, 2),
        (13, 2),
        (14, 2),
        (16, 1),
        (17, 2),
        (18, 2),
        (19, 2),
        (20, 1),
        (21, 1),
        (22, 1),
        (23, 1),
        (24, 1),
        (25, 1),
        (26, 1),
        (27, 1),
        (28, 1),
        (29, 1),
        (30, 3),
    ]
    current = 0
    for week, count in week_round_counts:
        current += count
        if round_no <= current:
            return week
    raise ValueError(f"지원하지 않는 리그 라운드입니다: {round_no}")
