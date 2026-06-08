from __future__ import annotations

import random
from collections.abc import Sequence

from .models import Match, Team


def _ranked_ids(previous_standings: Sequence[dict[str, object]]) -> list[str]:
    return [str(row["team_id"]) for row in sorted(previous_standings, key=lambda row: int(row["rank"]))]


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
        id=f"FA-{stage.upper()}-{week:02d}-{match_no:03d}",
        competition="fa_cup",
        stage=stage,
        round=round_label,
        week=week,
        match_no=match_no,
        home_team_id=home,
        away_team_id=away,
        leg=leg,
    )


def _two_leg_round(stage: str, label: str, weeks: Sequence[int], slots: Sequence[str]) -> list[Match]:
    rows = []
    for idx in range(0, len(slots), 2):
        home = slots[idx]
        away = slots[idx + 1]
        no = (idx // 2) + 1
        rows.append(_match(stage, label, weeks[0], no, home, away, leg=1))
        rows.append(_match(stage, label, weeks[1], no, away, home, leg=2))
    return rows


def select_fa_cup_teams(
    teams: Sequence[Team],
    previous_standings: Sequence[dict[str, object]],
    seed: int = 7,
) -> list[str]:
    if len(teams) < 28 or len(previous_standings) < 4:
        return []

    rng = random.Random(seed)
    by_id = {team.id: team for team in teams}
    ranked = [team_id for team_id in _ranked_ids(previous_standings) if team_id in by_id]
    auto_r16 = ranked[:4]
    required = [team.id for team in teams if team.professional and team.id not in auto_r16]
    amateurs = [team.id for team in teams if not team.professional and team.id not in auto_r16]

    max_supported = 52
    participant_count = min(len(teams), max_supported)
    needed_non_auto = participant_count - 4
    if len(required) > needed_non_auto:
        needed_non_auto = len(required)
        participant_count = needed_non_auto + 4

    if needed_non_auto > len(required) + len(amateurs):
        return []

    selected_non_auto = required + rng.sample(amateurs, needed_non_auto - len(required))
    return auto_r16 + selected_non_auto


def _preliminary_plan(non_auto_count: int) -> list[tuple[str, int, int, int]]:
    """Return (round label, week, playing team count, bye count)."""
    if non_auto_count <= 24:
        return [("1R", 1, non_auto_count, 0)]
    if non_auto_count <= 36:
        playing = 2 * (non_auto_count - 24)
        return [("1R", 1, playing, non_auto_count - playing), ("2R", 5, 24, 0)]
    playing = 2 * (non_auto_count - 36)
    return [
        ("1R", 1, playing, non_auto_count - playing),
        ("2R", 5, 24, 12),
        ("3R", 11, 24, 0),
    ]


def generate_fa_cup(
    teams: Sequence[Team],
    previous_standings: Sequence[dict[str, object]],
    seed: int = 7,
) -> dict[str, object]:
    participants = select_fa_cup_teams(teams, previous_standings, seed=seed)
    if not participants:
        return {
            "held": False,
            "reason": "FA컵은 비프로팀 포함 28팀 이상 참여할 수 있을 때 진행합니다.",
            "matches": [],
        }

    auto_r16 = participants[:4]
    current_slots = participants[4:]
    matches: list[Match] = []
    for label, week, playing_count, bye_count in _preliminary_plan(len(current_slots)):
        playing = current_slots[:playing_count]
        byes = current_slots[playing_count : playing_count + bye_count]
        for idx in range(0, len(playing), 2):
            matches.append(_match("preliminary", label, week, (idx // 2) + 1, playing[idx], playing[idx + 1]))
        winners = [f"{label}승자_{idx}" for idx in range(1, (playing_count // 2) + 1)]
        current_slots = byes + winners

    r16_slots = auto_r16 + [f"{matches[-1].round if matches else '1R'}승자_{idx}" for idx in range(1, 13)]
    matches.extend(_two_leg_round("r16", "R16", [13, 16], r16_slots))
    matches.extend(_two_leg_round("qf", "QF", [20, 21], [f"R16승자_{idx}" for idx in range(1, 9)]))
    matches.extend(_two_leg_round("sf", "SF", [24, 25], [f"QF승자_{idx}" for idx in range(1, 5)]))
    matches.append(_match("final", "Final", 28, 1, "SF승자_1", "SF승자_2"))

    return {
        "held": True,
        "participants": participants,
        "participant_count": len(participants),
        "auto_r16": auto_r16,
        "matches": matches,
    }
