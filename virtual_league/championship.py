from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from .models import Match, Team

ROUND_WEEKS = {
    1: 3,
    2: 5,
    3: 11,
    4: 16,
    5: 18,
}


def _ranked_ids(previous_standings: Sequence[dict[str, object]]) -> list[str]:
    return [str(row["team_id"]) for row in sorted(previous_standings, key=lambda row: int(row["rank"]))]


def _previous_championship_participants(seasons_dir: Path, year: int) -> set[str]:
    path = seasons_dir / str(year - 1) / "championship.json"
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data.get("participants", []))


def _round_numbers_needed(team_count: int) -> int:
    return min(5, (team_count - 8) // 6)


def select_championship_teams(
    teams: Sequence[Team],
    previous_standings: Sequence[dict[str, object]],
    seasons_dir: Path,
    year: int,
) -> tuple[list[str], int]:
    if len(teams) < 14 or len(previous_standings) < 14:
        return [], 0

    rounds_needed = _round_numbers_needed(len(teams))
    participant_count = 8 + (6 * rounds_needed)
    ranked = _ranked_ids(previous_standings)
    auto_qf = ranked[:2]

    previous_participants = _previous_championship_participants(seasons_dir, year)
    remaining = ranked[2:]
    if previous_participants:
        fresh = [team_id for team_id in remaining if team_id not in previous_participants]
        returning = [team_id for team_id in remaining if team_id in previous_participants]
        remaining = fresh + returning

    participants = auto_qf + remaining[: participant_count - 2]
    return participants, rounds_needed


def _match(
    stage: str,
    round_label: str,
    week: int,
    match_no: int,
    home: str,
    away: str,
    leg: int | None = None,
) -> Match:
    return Match(
        id=f"CH-{stage.upper()}-{week:02d}-{match_no:03d}",
        competition="championship",
        stage=stage,
        round=round_label,
        week=week,
        match_no=match_no,
        home_team_id=home,
        away_team_id=away,
        leg=leg,
    )


def _two_leg_round(stage: str, label: str, weeks: Sequence[int], slots: Sequence[str]) -> list[Match]:
    matches = []
    for idx in range(0, len(slots), 2):
        home = slots[idx]
        away = slots[idx + 1]
        no = (idx // 2) + 1
        matches.append(_match(stage, label, weeks[0], no, home, away, leg=1))
        matches.append(_match(stage, label, weeks[1], no, away, home, leg=2))
    return matches


def generate_championship(
    teams: Sequence[Team],
    previous_standings: Sequence[dict[str, object]],
    seasons_dir: Path,
    year: int,
) -> dict[str, object]:
    participants, rounds_needed = select_championship_teams(teams, previous_standings, seasons_dir, year)
    if not participants:
        return {
            "held": False,
            "reason": "챔피언십은 14팀 이상일 때 진행합니다.",
            "matches": [],
        }

    auto_qf = participants[:2]
    play_in_slots = participants[-12:]
    byes_by_round: dict[str, list[str]] = {}
    cursor = 2
    for round_no in range(rounds_needed, 1, -1):
        byes_by_round[f"R{round_no}"] = participants[cursor : cursor + 6]
        cursor += 6

    # 필요한 라운드가 5보다 적으면 뒤쪽 주차부터 사용한다.
    active_weeks = [ROUND_WEEKS[idx] for idx in range(6 - rounds_needed, 6)]
    matches: list[Match] = []

    current_slots = play_in_slots
    for idx, week in enumerate(active_weeks, start=1):
        label = f"R{idx}"
        for match_idx in range(0, len(current_slots), 2):
            matches.append(
                _match(
                    "preliminary",
                    label,
                    week,
                    (match_idx // 2) + 1,
                    current_slots[match_idx],
                    current_slots[match_idx + 1],
                )
            )
        winners = [f"{label}승자_{match_no}" for match_no in range(1, 7)]
        current_slots = byes_by_round.get(f"R{idx + 1}", []) + winners

    qf_slots = auto_qf + [f"R{rounds_needed}승자_{idx}" for idx in range(1, 7)]
    matches.extend(_two_leg_round("qf", "QF", [21, 22], qf_slots))
    matches.extend(_two_leg_round("sf", "SF", [25, 26], [f"QF승자_{idx}" for idx in range(1, 5)]))
    matches.append(_match("final", "Final", 29, 1, "SF승자_1", "SF승자_2"))

    return {
        "held": True,
        "participants": participants,
        "participant_count": len(participants),
        "auto_qf": auto_qf,
        "rounds_needed": rounds_needed,
        "byes_by_round": byes_by_round,
        "matches": matches,
    }
