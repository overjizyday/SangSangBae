from __future__ import annotations

import random
from collections.abc import Iterable

from .models import Match

BASEBALL_EVENTS = (
    ("out", 0.66),
    ("walk", 0.08),
    ("single", 0.15),
    ("double", 0.06),
    ("triple", 0.02),
    ("home_run", 0.03),
)

EVENT_CODE_CHOICES: dict[str, tuple[int, ...]] = {
    "out": (21, 23, 25, 27, 29, 31, 32, 34, 35, 36, 37, 38, 39, 41, 42, 43, 45, 46, 47, 48, 49, 56, 57, 58, 59, 71, 72, 73, 74, 75, 76, 78, 79, 81, 82, 83, 84, 85, 86, 87, 91, 92, 93, 94, 95, 96, 97),
    "walk": (51, 52, 53, 54),
    "single": (12, 13, 61),
    "double": (14, 15, 16, 24, 26, 62, 63, 67, 68),
    "triple": (17, 18, 19, 64, 65, 98),
    "home_run": (69, 89),
}


def _pick_baseball_event_code(rng: random.Random) -> tuple[int, str]:
    event = _pick_baseball_event(rng)
    codes = EVENT_CODE_CHOICES.get(event, (21,))
    return rng.choice(codes), event


def _pick_baseball_event(rng: random.Random) -> str:
    roll = rng.random()
    total = 0.0
    for event, weight in BASEBALL_EVENTS:
        total += weight
        if roll < total:
            return event
    return "out"


def _advance_for_single(bases: list[bool]) -> tuple[list[bool], int]:
    runs = int(bases[2])
    return [True, bases[0], bases[1]], runs


def _advance_for_double(bases: list[bool]) -> tuple[list[bool], int]:
    runs = int(bases[1]) + int(bases[2])
    return [False, True, bases[0]], runs


def _advance_for_triple(bases: list[bool]) -> tuple[list[bool], int]:
    runs = int(bases[0]) + int(bases[1]) + int(bases[2])
    return [False, False, True], runs


def _advance_for_home_run(bases: list[bool]) -> tuple[list[bool], int]:
    runs = int(bases[0]) + int(bases[1]) + int(bases[2]) + 1
    return [False, False, False], runs


def _advance_for_walk(bases: list[bool]) -> tuple[list[bool], int]:
    # Bases loaded walk forces in one run and keeps the inning alive.
    runs = int(bases[0] and bases[1] and bases[2])
    return [True, bases[0], bases[1]], runs


def _simulate_half_inning(rng: random.Random) -> int:
    bases = [False, False, False]
    outs = 0
    runs = 0

    while outs < 3:
        event = _pick_baseball_event(rng)

        if event == "out":
            outs += 1
            continue

        if event == "walk":
            bases, scored = _advance_for_walk(bases)
        elif event == "single":
            bases, scored = _advance_for_single(bases)
        elif event == "double":
            bases, scored = _advance_for_double(bases)
        elif event == "triple":
            bases, scored = _advance_for_triple(bases)
        else:
            bases, scored = _advance_for_home_run(bases)

        runs += scored

    return runs


def _format_bases(bases: list[bool]) -> str:
    occupied = []
    if bases[0]:
        occupied.append("1B")
    if bases[1]:
        occupied.append("2B")
    if bases[2]:
        occupied.append("3B")
    return ",".join(occupied) if occupied else "-"


def _simulate_half_inning_trace(
    rng: random.Random,
    inning: int,
    half: str,
    score_away: int,
    score_home: int,
    plate_start: int,
) -> tuple[list[dict[str, object]], int, int, int]:
    bases = [False, False, False]
    outs = 0
    events: list[dict[str, object]] = []
    plate_no = plate_start

    while outs < 3:
        event_code, event = _pick_baseball_event_code(rng)
        bases_before = bases[:]
        outs_before = outs
        score_before = (score_away, score_home)

        if event == "out":
            outs += 1
            runs_scored = 0
        elif event == "walk":
            bases, runs_scored = _advance_for_walk(bases)
        elif event == "single":
            bases, runs_scored = _advance_for_single(bases)
        elif event == "double":
            bases, runs_scored = _advance_for_double(bases)
        elif event == "triple":
            bases, runs_scored = _advance_for_triple(bases)
        else:
            bases, runs_scored = _advance_for_home_run(bases)

        if half == "top":
            score_away += runs_scored
        else:
            score_home += runs_scored

        events.append(
            {
                "plate_appearance": plate_no,
                "event_code": event_code,
                "inning": inning,
                "half": half,
                "event": event,
                "outs_before": outs_before,
                "outs_after": outs,
                "bases_before": _format_bases(bases_before),
                "bases_after": _format_bases(bases),
                "score_away_before": score_before[0],
                "score_home_before": score_before[1],
                "score_away_after": score_away,
                "score_home_after": score_home,
                "runs_scored": runs_scored,
                "half_over": outs >= 3,
            }
        )
        plate_no += 1

    return events, score_away, score_home, plate_no


def simulate_baseball_game(rng: random.Random, decisive: bool = False) -> tuple[int, int]:
    away_score = 0
    home_score = 0

    for _ in range(9):
        away_score += _simulate_half_inning(rng)
        home_score += _simulate_half_inning(rng)

    if decisive:
        extra_innings = 0
        while away_score == home_score and extra_innings < 18:
            away_score += _simulate_half_inning(rng)
            home_score += _simulate_half_inning(rng)
            extra_innings += 1

        if away_score == home_score:
            if rng.random() < 0.5:
                home_score += 1
            else:
                away_score += 1

    return home_score, away_score


def simulate_baseball_game_trace(
    rng: random.Random, decisive: bool = False
) -> tuple[int, int, list[dict[str, object]]]:
    away_score = 0
    home_score = 0
    events: list[dict[str, object]] = []
    plate_no = 1

    inning = 1
    while inning <= 9:
        half_events, away_score, home_score, plate_no = _simulate_half_inning_trace(
            rng, inning, "top", away_score, home_score, plate_no
        )
        events.extend(half_events)
        half_events, away_score, home_score, plate_no = _simulate_half_inning_trace(
            rng, inning, "bottom", away_score, home_score, plate_no
        )
        events.extend(half_events)
        inning += 1

    extra_innings = 0
    while decisive and away_score == home_score and extra_innings < 18:
        inning = 10 + extra_innings
        half_events, away_score, home_score, plate_no = _simulate_half_inning_trace(
            rng, inning, "top", away_score, home_score, plate_no
        )
        events.extend(half_events)
        half_events, away_score, home_score, plate_no = _simulate_half_inning_trace(
            rng, inning, "bottom", away_score, home_score, plate_no
        )
        events.extend(half_events)
        extra_innings += 1

    if decisive and away_score == home_score:
        if rng.random() < 0.5:
            home_score += 1
            winning_team = "home"
        else:
            away_score += 1
            winning_team = "away"
        events.append(
            {
                "plate_appearance": plate_no,
                "event_code": 99,
                "inning": 10 + extra_innings,
                "half": "bottom",
                "event": "coinflip_run",
                "outs_before": 0,
                "outs_after": 0,
                "bases_before": "-",
                "bases_after": "-",
                "score_away_before": away_score - (1 if winning_team == "away" else 0),
                "score_home_before": home_score - (1 if winning_team == "home" else 0),
                "score_away_after": away_score,
                "score_home_after": home_score,
                "runs_scored": 1,
                "half_over": True,
            }
        )

    return home_score, away_score, events


def simulate_results(matches: Iterable[Match], seed: int = 7) -> list[Match]:
    rng = random.Random(seed)
    simulated = []
    for match in matches:
        match.home_score, match.away_score = simulate_baseball_game(rng, decisive=True)
        simulated.append(match)
    return simulated
