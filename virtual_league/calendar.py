from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Iterable

from .models import Match

DAYS = ["월", "화", "수", "목", "금", "토", "일"]
CUP_PRIORITY = ["acl", "local_cup", "championship", "fa_cup"]
PRIORITY = {"acl": 0, "local_cup": 1, "championship": 2, "fa_cup": 3, "super_cup": 3, "league": 4}
MIDWEEK = ["화", "수", "목"]
WEEKEND = ["금", "토", "일"]


def assign_season_days(
    league_matches: list[Match],
    competitions: list[dict[str, object]],
    seed: int = 7,
) -> None:
    rng = random.Random(seed)
    cup_matches = []
    for competition in competitions:
        if competition.get("held"):
            cup_matches.extend(_matches_from_payload(competition))

    _assign_cup_days(cup_matches, rng)
    _assign_league_days(league_matches, cup_matches, rng)
    _resolve_lower_priority_conflicts(league_matches + cup_matches, rng)


def _matches_from_payload(payload: dict[str, object]) -> list[Match]:
    return [item for item in payload.get("matches", []) if isinstance(item, Match)]


def _assign_cup_days(matches: list[Match], rng: random.Random) -> None:
    team_week_competitions = _team_week_competitions(matches)

    finals_by_week_comp = {(match.week, match.competition) for match in matches if match.round == "Final"}
    for match in sorted(matches, key=lambda item: (PRIORITY.get(item.competition, 99), item.week, item.id)):
        if match.round == "Final":
            if match.week == 29 and match.competition == "championship" and (29, "local_cup") in finals_by_week_comp:
                match.day = "일"
            else:
                match.day = "토"
            continue

        if match.competition == "super_cup":
            match.day = _super_cup_day(match)
            continue

        if match.competition == "local_cup":
            if match.stage == "regional_qualifier":
                continue
            if match.stage == "regional_po":
                match.day = "월"
                continue
            if match.stage == "group":
                match.day = _local_cup_group_day(match)
                continue

        if match.competition == "acl" and str(match.stage).endswith("_po"):
            match.day = "수"
            continue

        match.day = _cup_day_for_match(match, team_week_competitions)

    _assign_local_cup_regional_qualifier_days(
        [match for match in matches if match.competition == "local_cup" and match.stage == "regional_qualifier"],
        rng,
    )


def _team_week_competitions(matches: Iterable[Match]) -> dict[tuple[str, int], set[str]]:
    result: dict[tuple[str, int], set[str]] = defaultdict(set)
    for match in matches:
        if match.round == "Final":
            continue
        for team_id in [match.home_team_id, match.away_team_id]:
            if _is_real_team_reference(team_id):
                result[(team_id, match.week)].add(match.competition)
    return result


def _is_real_team_reference(team_id: str) -> bool:
    placeholder_tokens = ["승자", "진출", "홈", "원정", "예선통과", "후보", "_"]
    return bool(team_id) and not any(token in team_id for token in placeholder_tokens)


def _cup_day_for_match(match: Match, team_week_competitions: dict[tuple[str, int], set[str]]) -> str:
    candidate_positions = []
    for team_id in [match.home_team_id, match.away_team_id]:
        competitions = team_week_competitions.get((team_id, match.week), set())
        if len(competitions) >= 2 and match.competition in competitions:
            ordered = [item for item in CUP_PRIORITY if item in competitions]
            if match.competition in ordered:
                candidate_positions.append(ordered.index(match.competition))

    if not candidate_positions:
        return "수"

    position = min(candidate_positions)
    return ["화", "목", "수", "화"][min(position, 3)]


def _super_cup_day(match: Match) -> str:
    if match.round == 1:
        return "토"
    if match.round == 2:
        return "일"
    if match.round == 3:
        return "목"
    if match.round == 4:
        return "토"
    if match.round == 5:
        return "일"
    return "토"


def _assign_local_cup_regional_qualifier_days(matches: list[Match], rng: random.Random) -> None:
    if not matches:
        return

    grouped: dict[tuple[str | None, str | None], list[Match]] = defaultdict(list)
    for match in matches:
        grouped[(match.region, match.group)].append(match)

    for group_matches in grouped.values():
        group_matches.sort(key=lambda item: item.match_no or 0)
        team_ids = {team_id for match in group_matches for team_id in [match.home_team_id, match.away_team_id]}
        rounds_needed = _infer_round_count(len(team_ids), len(group_matches))
        round_days = _local_cup_regional_round_days(rounds_needed, rng)
        for idx, match in enumerate(group_matches):
            match.day = round_days[idx % len(round_days)]


def _infer_round_count(team_count: int, match_count: int) -> int:
    if team_count == 3 and match_count >= 6:
        return 6
    if team_count == 5:
        return 5
    if team_count in {4, 6}:
        return 3
    return max(1, min(6, match_count))


def _local_cup_regional_round_days(rounds_needed: int, rng: random.Random) -> list[str]:
    if rounds_needed >= 6:
        return ["월", "화", "수", "금", "토", "일"]
    if rounds_needed == 5:
        days = ["화", "수", "목", "금", "토", "일"]
        days.remove(rng.choice(["목", "금"]))
        return days
    if rounds_needed == 3:
        return ["화", "목", "토"]
    return _balanced_days(rounds_needed, ["화", "수", "목", "금", "토", "일"], rng)


def _local_cup_group_day(match: Match) -> str:
    if match.match_no is None:
        return "수"
    group_index = (match.match_no - 1) // 3
    round_in_group = ((match.match_no - 1) % 3) + 1
    first_half = group_index % 2 == 0
    if round_in_group == 1:
        return "수" if first_half else "목"
    if round_in_group == 2:
        return "금" if first_half else "토"
    return "토" if first_half else "일"


def _assign_league_days(league_matches: list[Match], cup_matches: list[Match], rng: random.Random) -> None:
    rounds_by_week: dict[int, dict[int, list[Match]]] = defaultdict(lambda: defaultdict(list))
    for match in league_matches:
        if int(match.round) > 40:
            continue
        rounds_by_week[match.week][int(match.round)].append(match)

    weeks_with_cups = {match.week for match in cup_matches if match.day is not None}
    local_cup_pressure_weeks = {
        match.week
        for match in cup_matches
        if match.competition == "local_cup" and match.week in {9, 15}
    }

    final_teams_by_week = _final_teams_by_week(cup_matches)
    league_day_loads: dict[tuple[int, str], int] = defaultdict(int)
    for match in cup_matches:
        if match.day is not None:
            league_day_loads[(match.week, match.day)] += 1

    fixed_league_match_ids = _fix_opening_and_final_league_matches(league_matches)

    for week, round_map in rounds_by_week.items():
        round_numbers = sorted(round_map)
        round_day_pools = _league_round_day_pools(
            week,
            len(round_numbers),
            week in weeks_with_cups,
            week + 1 in local_cup_pressure_weeks,
        )
        for round_no, day_pool in zip(round_numbers, round_day_pools):
            for match in round_map[round_no]:
                if match.id in fixed_league_match_ids:
                    league_day_loads[(week, match.day or "토")] += 1
                    continue
                if week in final_teams_by_week and {match.home_team_id, match.away_team_id} & final_teams_by_week[week]:
                    match.day = _choose_balanced_day(["화", "수"], league_day_loads, week, rng)
                else:
                    match.day = _choose_balanced_day(day_pool, league_day_loads, week, rng)
                league_day_loads[(week, match.day)] += 1


def _fix_opening_and_final_league_matches(league_matches: list[Match]) -> set[str]:
    regular_matches = [match for match in league_matches if int(match.round) <= 39]
    if not regular_matches:
        fixed_ids = set()
    else:
        ordered = sorted(regular_matches, key=lambda match: (int(match.round), match.id))
        ordered[0].day = "토"
        ordered[-1].day = "토"
        fixed_ids = {ordered[0].id, ordered[-1].id}

    final_round_matches = [match for match in league_matches if match.week == 31 and int(match.round) in {40, 41, 42}]
    final_round_day_map = {40: "월", 41: "목", 42: "일"}
    for match in final_round_matches:
        match.day = final_round_day_map[int(match.round)]
        fixed_ids.add(match.id)

    return fixed_ids


def _league_round_day_pools(
    week: int,
    round_count: int,
    has_cup: bool,
    avoid_sunday: bool,
) -> list[list[str]]:
    if week == 31 and round_count == 3:
        return [["월"], ["목"], ["일"]]
    weekend = ["금", "토"] if avoid_sunday else WEEKEND[:]
    if round_count >= 3:
        return [
            ["화", "수"],
            ["목", "금"] if avoid_sunday else ["목", "금"],
            ["토"] if avoid_sunday else ["토", "일"],
        ][:round_count]
    if round_count == 2 and has_cup:
        return [
            ["목", "금"],
            ["토"] if avoid_sunday else ["토", "일"],
        ]
    if round_count == 2:
        return [
            MIDWEEK[:],
            weekend[:],
        ]
    if round_count == 1:
        return [weekend[:]]
    return []


def _choose_balanced_day(candidates: list[str], loads: dict[tuple[int, str], int], week: int, rng: random.Random) -> str:
    if len(candidates) == 1:
        return candidates[0]
    picked = rng.sample(candidates, k=min(2, len(candidates)))
    picked.sort(key=lambda day: (loads[(week, day)], rng.random()))
    return picked[0]


def _balanced_days(count: int, candidates: list[str], rng: random.Random) -> list[str]:
    loads = {day: 0 for day in candidates}
    days = []
    for _ in range(count):
        picked = rng.sample(candidates, k=min(2, len(candidates)))
        picked.sort(key=lambda day: (loads[day], rng.random()))
        day = picked[0]
        loads[day] += 1
        days.append(day)
    return days


def _final_teams_by_week(matches: Iterable[Match]) -> dict[int, set[str]]:
    result: dict[int, set[str]] = defaultdict(set)
    for match in matches:
        if match.round != "Final":
            continue
        for team_id in [match.home_team_id, match.away_team_id]:
            if _is_real_team_reference(team_id):
                result[match.week].add(team_id)
    return result


def _resolve_lower_priority_conflicts(matches: list[Match], rng: random.Random) -> None:
    by_team_week_day: dict[tuple[str, int, str], list[Match]] = defaultdict(list)
    for match in matches:
        if match.day is None:
            continue
        for team_id in [match.home_team_id, match.away_team_id]:
            if _is_real_team_reference(team_id):
                by_team_week_day[(team_id, match.week, match.day)].append(match)

    for (team_id, week, day), conflicted in by_team_week_day.items():
        if len(conflicted) <= 1:
            continue
        fixed = [match for match in conflicted if _is_fixed_league_day(match)]
        if fixed:
            movable = [match for match in conflicted if match not in fixed]
            movable.sort(key=lambda item: PRIORITY.get(item.competition, 99))
            for match in movable:
                if match.competition == "league":
                    alternatives = _league_alternatives(day)
                else:
                    alternatives = [item for item in MIDWEEK if item != day]
                match.day = rng.choice(alternatives)
            continue
        conflicted.sort(key=lambda item: PRIORITY.get(item.competition, 99))
        for match in conflicted[1:]:
            if match.competition == "league" and _is_opening_or_final_marker(match):
                continue
            if match.competition == "league":
                alternatives = _league_alternatives(day)
            else:
                alternatives = [item for item in MIDWEEK if item != day]
            match.day = rng.choice(alternatives)


def _is_opening_or_final_marker(match: Match) -> bool:
    return match.day == "토" and match.competition == "league"


def _is_fixed_league_day(match: Match) -> bool:
    return match.competition == "league" and (
        _is_opening_or_final_marker(match) or (match.week == 31 and int(match.round) in {40, 41, 42})
    )


def _league_alternatives(day: str) -> list[str]:
    if day == "월":
        return ["화", "수"]
    if day in {"화", "수"}:
        return [item for item in ["화", "수"] if item != day]
    if day in {"목", "금"}:
        return [item for item in ["목", "금"] if item != day]
    if day in {"토", "일"}:
        return [item for item in ["토", "일"] if item != day]
    return [item for item in DAYS if item != day]
