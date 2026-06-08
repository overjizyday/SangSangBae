from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from .models import Match
from .simulation import simulate_baseball_game

EVENT_CODE_CHOICES: dict[str, tuple[int, ...]] = {
    "out": (21, 23, 25, 27, 29, 31, 32, 34, 35, 36, 37, 38, 39, 41, 42, 43, 45, 46, 47, 48, 49, 56, 57, 58, 59, 71, 72, 73, 74, 75, 76, 78, 79, 81, 82, 83, 84, 85, 86, 87, 91, 92, 93, 94, 95, 96, 97),
    "home_run": (69, 89),
}


def _finalize_match_result(match: Match) -> None:
    if match.home_score is None or match.away_score is None:
        return
    if match.home_score > match.away_score:
        match.winner_team_id = match.home_team_id
        match.loser_team_id = match.away_team_id
    elif match.home_score < match.away_score:
        match.winner_team_id = match.away_team_id
        match.loser_team_id = match.home_team_id
    elif match.winner_team_id is None and match.loser_team_id is None:
        match.winner_team_id = ""
        match.loser_team_id = ""


def simulate_match_outcomes(matches: Iterable[Match], seed: int = 7) -> list[dict[str, object]]:
    import random

    rng = random.Random(seed)
    rows = []
    for match in matches:
        if match.home_score is None or match.away_score is None:
            match.home_score, match.away_score = simulate_baseball_game(rng, decisive=True)
        _finalize_match_result(match)
        rows.append(
            {
                "competition": match.competition,
                "stage": match.stage,
                "round": match.round,
                "week": match.week,
                "day": match.day,
                "match_no": match.match_no,
                "home_team_id": match.home_team_id,
                "away_team_id": match.away_team_id,
                "home_score": match.home_score,
                "away_score": match.away_score,
                "winner_team_id": match.winner_team_id or "",
                "loser_team_id": match.loser_team_id or "",
            }
        )
    return rows


def simulate_match_outcomes_with_traces(
    matches: Iterable[Match], seed: int = 7
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    import random

    rng = random.Random(seed)
    rows = []
    traces = []
    for match in matches:
        if match.home_score is None or match.away_score is None:
            match.home_score, match.away_score = simulate_baseball_game(rng, decisive=True)
        events = _build_pseudo_trace(
            rng,
            home_score=int(match.home_score or 0),
            away_score=int(match.away_score or 0),
        )
        _finalize_match_result(match)
        rows.append(
            {
                "competition": match.competition,
                "stage": match.stage,
                "round": match.round,
                "week": match.week,
                "day": match.day,
                "match_no": match.match_no,
                "home_team_id": match.home_team_id,
                "away_team_id": match.away_team_id,
                "home_score": match.home_score,
                "away_score": match.away_score,
                "winner_team_id": match.winner_team_id or "",
                "loser_team_id": match.loser_team_id or "",
            }
        )
        traces.append(
            {
                "match_id": match.id,
                "competition": match.competition,
                "stage": match.stage,
                "round": match.round,
                "week": match.week,
                "day": match.day,
                "home_team_id": match.home_team_id,
                "away_team_id": match.away_team_id,
                "home_score": match.home_score,
                "away_score": match.away_score,
                "events": events,
            }
        )
    return rows, traces


def _distribute_runs(total_runs: int, innings: int, rng) -> list[int]:
    buckets = [0 for _ in range(innings)]
    for _ in range(total_runs):
        buckets[rng.randrange(innings)] += 1
    return buckets


def _build_half_events(
    *,
    inning: int,
    half: str,
    runs: int,
    score_away: int,
    score_home: int,
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    plate = 1
    current_away = score_away
    current_home = score_home
    bases_before = "-"
    bases_after = "-"

    for run_index in range(runs):
        current = {
            "plate_appearance": plate,
            "event_code": EVENT_CODE_CHOICES["home_run"][run_index % len(EVENT_CODE_CHOICES["home_run"])],
            "inning": inning,
            "half": half,
            "event": "home_run",
            "outs_before": 0,
            "outs_after": 0,
            "bases_before": bases_before,
            "bases_after": bases_after,
            "score_away_before": current_away,
            "score_home_before": current_home,
            "score_away_after": current_away + (1 if half == "top" else 0),
            "score_home_after": current_home + (1 if half == "bottom" else 0),
            "runs_scored": 1,
            "half_over": False,
        }
        current_away = current["score_away_after"]
        current_home = current["score_home_after"]
        events.append(current)
        plate += 1

    for outs_before in range(3):
        event = {
            "plate_appearance": plate,
            "event_code": EVENT_CODE_CHOICES["out"][outs_before % len(EVENT_CODE_CHOICES["out"])],
            "inning": inning,
            "half": half,
            "event": "out",
            "outs_before": outs_before,
            "outs_after": outs_before + 1,
            "bases_before": bases_before,
            "bases_after": bases_after,
            "score_away_before": current_away,
            "score_home_before": current_home,
            "score_away_after": current_away,
            "score_home_after": current_home,
            "runs_scored": 0,
            "half_over": outs_before == 2,
        }
        events.append(event)
        plate += 1

    return events


def _build_pseudo_trace(rng, home_score: int, away_score: int) -> list[dict[str, object]]:
    away_by_inning = _distribute_runs(away_score, 9, rng)
    home_by_inning = _distribute_runs(home_score, 9, rng)
    events: list[dict[str, object]] = []
    score_away = 0
    score_home = 0

    for inning in range(1, 10):
        top_events = _build_half_events(
            inning=inning,
            half="top",
            runs=away_by_inning[inning - 1],
            score_away=score_away,
            score_home=score_home,
        )
        if top_events:
            score_away = int(top_events[-1]["score_away_after"])
            score_home = int(top_events[-1]["score_home_after"])
        events.extend(top_events)

        bottom_events = _build_half_events(
            inning=inning,
            half="bottom",
            runs=home_by_inning[inning - 1],
            score_away=score_away,
            score_home=score_home,
        )
        if bottom_events:
            score_away = int(bottom_events[-1]["score_away_after"])
            score_home = int(bottom_events[-1]["score_home_after"])
        events.extend(bottom_events)

    return events


def write_results_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "competition",
        "stage",
        "round",
        "week",
        "day",
        "match_no",
        "home_team_id",
        "away_team_id",
        "home_score",
        "away_score",
        "winner_team_id",
        "loser_team_id",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
