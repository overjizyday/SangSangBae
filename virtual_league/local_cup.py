from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Sequence

from .league import make_single_round_robin
from .models import Match, Team

REGIONS = ["서울", "경기", "강원", "충청", "전라", "경상"]


def valid_qualifier_totals(limit: int = 10000) -> list[int]:
    values = []
    k = 3
    while True:
        value = 2 * ((2**k) - 1)
        if value > limit:
            break
        values.append(value)
        k += 1
    return values


def is_power_of_two(value: int) -> bool:
    return value >= 1 and value & (value - 1) == 0


def validate_qualifier_total(total: int) -> None:
    main_total = total // 2 + 1
    if total < 14 or total % 2 or not is_power_of_two(main_total) or main_total < 8:
        near = min(valid_qualifier_totals(max(128, total * 4)), key=lambda item: abs(item - total))
        raise ValueError(
            "로컬컵 참가팀 수는 지역예선 참가팀/2 + 우승팀 1팀이 2^k가 되도록 "
            f"2*(2^k-1)이어야 합니다. 현재 {total}팀, 가까운 유효값 {near}팀."
        )


def select_local_cup_teams(
    teams: Sequence[Team],
    previous_winner_id: str,
    seed: int = 7,
) -> list[Team]:
    rng = random.Random(seed)
    by_id = {team.id: team for team in teams}
    if previous_winner_id not in by_id:
        raise ValueError(f"지난해 우승팀을 참가팀 목록에서 찾을 수 없습니다: {previous_winner_id}")

    required_ids = {team.id for team in teams if team.professional}
    required_ids.add(previous_winner_id)
    required = [by_id[team_id] for team_id in required_ids]
    amateurs = [team for team in teams if not team.professional and team.id not in required_ids]

    valid_totals = valid_qualifier_totals(max(128, len(teams) * 4))
    target = next((value for value in valid_totals if value >= len(required)), None)
    if target is None or target < 14 or target > len(teams):
        return []

    needed = target - len(required)
    if needed > len(amateurs):
        return []

    selected = required + rng.sample(amateurs, needed)
    selected.sort(key=lambda team: team.id)
    validate_qualifier_total(len(selected))
    return selected


def merge_small_regions(region_teams: dict[str, list[Team]]) -> dict[str, list[Team]]:
    merged = {region: items[:] for region, items in region_teams.items() if items}
    while True:
        small = [(region, len(items)) for region, items in merged.items() if len(items) <= 2]
        if not small:
            return merged

        small_region, _ = min(small, key=lambda item: (item[1], item[0]))
        candidates = [(region, len(items)) for region, items in merged.items() if region != small_region]
        if not candidates:
            raise ValueError("로컬컵 지역예선 병합 대상 지역이 없습니다.")

        target_region, _ = min(candidates, key=lambda item: (item[1], item[0]))
        merged[f"{target_region}+{small_region}"] = merged[target_region] + merged[small_region]
        del merged[target_region]
        del merged[small_region]


def split_group_sizes(team_count: int) -> list[int]:
    for fours in range(team_count // 4, -1, -1):
        remain = team_count - (4 * fours)
        if remain % 3 == 0:
            return [4] * fours + [3] * (remain // 3)
    raise ValueError(f"{team_count}팀은 3팀/4팀 조합으로 분할할 수 없습니다.")


def split_region_groups(region: str, teams: list[Team]) -> list[tuple[str, str, list[Team], list[Team] | None]]:
    count = len(teams)
    if count in [3, 4, 5]:
        return [(region, "", teams, None)]
    if count == 6:
        return [(region, "", teams[:3], teams[3:])]
    if count <= 12:
        sizes_by_count = {
            7: [4, 3],
            8: [4, 4],
            9: [3, 3, 3],
            10: [5, 5],
            11: [4, 4, 3],
            12: [4, 4, 4],
        }
        if count not in sizes_by_count:
            raise ValueError(f"{region}은 {count}팀입니다. 지원하지 않는 지역 팀 수입니다.")
        sizes = sizes_by_count[count]
    else:
        sizes = split_group_sizes(count)

    groups = []
    start = 0
    for idx, size in enumerate(sizes):
        group_name = chr(65 + idx)
        groups.append((region, group_name, teams[start : start + size], None))
        start += size
    return groups


def balanced_round_robin(teams: Sequence[Team], double: bool = False) -> list[tuple[Team, Team]]:
    team_ids = [team.id for team in teams]
    by_id = {team.id: team for team in teams}
    matches = []
    for round_no, round_pairs in enumerate(make_single_round_robin(team_ids)):
        for home_id, away_id in round_pairs:
            if round_no % 2:
                home_id, away_id = away_id, home_id
            matches.append((by_id[home_id], by_id[away_id]))

    if double:
        matches.extend([(away, home) for home, away in matches])
    return matches


def cross_slot_matches(slot_a: Sequence[Team], slot_b: Sequence[Team]) -> list[tuple[Team, Team]]:
    matches = []
    for i, team_a in enumerate(slot_a):
        for j, team_b in enumerate(slot_b):
            matches.append((team_a, team_b) if (i + j) % 2 == 0 else (team_b, team_a))
    return matches


def spread_matches(matches: Sequence[tuple[Team, Team]], seed: int = 7) -> list[tuple[Team, Team]]:
    rng = random.Random(seed)
    remaining = list(matches)
    rng.shuffle(remaining)
    ordered = []
    last_team_ids: set[str] = set()

    while remaining:
        scored = []
        for idx, (home, away) in enumerate(remaining):
            overlap = len({home.id, away.id} & last_team_ids)
            scored.append((overlap, idx))
        min_overlap = min(item[0] for item in scored)
        _, selected_idx = rng.choice([item for item in scored if item[0] == min_overlap])
        home, away = remaining.pop(selected_idx)
        ordered.append((home, away))
        last_team_ids = {home.id, away.id}

    return ordered


def _without_winner(matches: Sequence[tuple[Team, Team]], winner_id: str) -> list[tuple[Team, Team]]:
    return [(home, away) for home, away in matches if winner_id not in {home.id, away.id}]


def _advancer_slots(region: str, group: str, original_size: int) -> tuple[list[str], str | None]:
    group_part = f"_{group}" if group else ""
    direct = [f"{region}{group_part}_예선통과_{idx}" for idx in range(1, original_size // 2 + 1)]
    po = f"{region}{group_part}_PO후보" if original_size % 2 else None
    return direct, po


def generate_regional_qualifiers(
    teams: Sequence[Team], previous_winner_id: str, seed: int = 7
) -> tuple[list[Match], list[str], list[str], dict[str, list[str]], list[dict[str, object]]]:
    rng = random.Random(seed)
    region_teams: dict[str, list[Team]] = defaultdict(list)
    for team in teams:
        region = team.region if team.region in REGIONS else "경상"
        region_teams[region].append(team)

    merged = merge_small_regions(dict(region_teams))
    matches: list[Match] = []
    advancers: list[str] = []
    po_candidates: list[str] = []
    slot_rules: list[dict[str, object]] = []
    match_no = 1

    for region, region_members in merged.items():
        members = region_members[:]
        rng.shuffle(members)
        for region_name, group_name, group_a, group_b in split_region_groups(region, members):
            original_size = len(group_a) + (len(group_b) if group_b else 0)
            if group_b is None:
                group_matches = balanced_round_robin(group_a, double=original_size == 3)
            else:
                group_matches = cross_slot_matches(group_a, group_b)

            group_matches = spread_matches(_without_winner(group_matches, previous_winner_id), seed + match_no)
            for home, away in group_matches:
                matches.append(
                    Match(
                        id=f"LC-RQ-{match_no:03d}",
                        competition="local_cup",
                        stage="regional_qualifier",
                        round="RQ",
                        week=9,
                        match_no=match_no,
                        region=region_name,
                        group=group_name,
                        home_team_id=home.id,
                        away_team_id=away.id,
                    )
                )
                match_no += 1

            direct, po = _advancer_slots(region_name, group_name, original_size)
            slot_rules.append(
                {
                    "region": region_name,
                    "group": group_name,
                    "original_size": original_size,
                    "direct_slots": len(direct),
                    "po_slots": 1 if po else 0,
                }
            )
            advancers.extend(direct)
            if po:
                po_candidates.append(po)

    rng.shuffle(po_candidates)
    if len(po_candidates) % 2:
        raise ValueError(f"로컬컵 PO 후보 수가 홀수입니다: {len(po_candidates)}")

    for idx in range(0, len(po_candidates), 2):
        po_no = (idx // 2) + 1
        home = po_candidates[idx]
        away = po_candidates[idx + 1]
        matches.append(
            Match(
                id=f"LC-PO-{po_no:03d}",
                competition="local_cup",
                stage="regional_po",
                round="PO",
                week=15,
                match_no=po_no,
                region="통합PO",
                group=f"PO{po_no}",
                home_team_id=home,
                away_team_id=away,
            )
        )

    merged_summary = {region: [team.id for team in members] for region, members in merged.items()}
    return matches, advancers, po_candidates, merged_summary, slot_rules


def _placeholder_match(
    stage: str,
    round_label: str,
    week: int,
    match_no: int,
    home: str,
    away: str,
    leg: int | None = None,
    advantage: str | None = None,
) -> Match:
    return Match(
        id=f"LC-{stage.upper()}-{week:02d}-{match_no:03d}",
        competition="local_cup",
        stage=stage,
        round=round_label,
        week=week,
        match_no=match_no,
        home_team_id=home,
        away_team_id=away,
        leg=leg,
        advantage_team_id=advantage,
    )


def generate_main_round_placeholders(qualifier_total: int, previous_winner_id: str) -> list[Match]:
    matches: list[Match] = []
    main_total = qualifier_total // 2 + 1

    if main_total == 8:
        qf_count = 8
        sf_count = 4
        r16_count = 0
        qf_week = 22
        sf_week = 26
        final_week = 29
    elif main_total == 16:
        qf_count = 4
        sf_count = 4
        r16_count = 0
        qf_week = 22
        sf_week = 26
        final_week = 29
    elif main_total == 32:
        qf_count = 8
        sf_count = 4
        r16_count = 4
        qf_week = 23
        sf_week = 27
        final_week = 29
    else:
        qf_count = 0
        sf_count = 0
        r16_count = 0
        qf_week = 0
        sf_week = 0
        final_week = 0

    for idx in range(r16_count):
        matches.append(
            Match(
                id=f"LC-R16-{idx+1:03d}",
                competition="local_cup",
                stage="r16",
                round="R16",
                week=17,
                match_no=idx + 1,
                home_team_id=f"PENDING_R16_{idx+1}_A",
                away_team_id=f"PENDING_R16_{idx+1}_B",
            )
        )

    for idx in range(qf_count):
        matches.append(
            Match(
                id=f"LC-QF-{idx+1:03d}",
                competition="local_cup",
                stage="qf",
                round="QF",
                week=qf_week + (idx % 2),
                match_no=idx + 1,
                home_team_id=f"PENDING_QF_{idx+1}_A",
                away_team_id=f"PENDING_QF_{idx+1}_B",
                leg=(idx % 2) + 1,
            )
        )

    for idx in range(sf_count):
        matches.append(
            Match(
                id=f"LC-SF-{idx+1:03d}",
                competition="local_cup",
                stage="sf",
                round="SF",
                week=sf_week + (idx % 2),
                match_no=idx + 1,
                home_team_id=f"PENDING_SF_{idx+1}_A",
                away_team_id=f"PENDING_SF_{idx+1}_B",
                leg=(idx % 2) + 1,
            )
        )

    if final_week:
        matches.append(
            Match(
                id="LC-FINAL-001",
                competition="local_cup",
                stage="final",
                round="Final",
                week=final_week,
                match_no=1,
                home_team_id="PENDING_FINAL_A",
                away_team_id="PENDING_FINAL_B",
            )
        )

    return matches


def generate_local_cup(
    teams: Sequence[Team],
    previous_winner_id: str,
    seed: int = 7,
) -> dict[str, object]:
    participants = select_local_cup_teams(teams, previous_winner_id, seed=seed)
    if not participants:
        return {
            "held": False,
            "reason": "로컬컵은 14팀 이상이 참여해야 진행됩니다.",
            "matches": [],
        }

    qualifier_matches, advancers, po_candidates, merged_regions, regional_slot_rules = generate_regional_qualifiers(
        participants, previous_winner_id, seed=seed
    )
    main_matches = generate_main_round_placeholders(len(participants), previous_winner_id)

    return {
        "held": True,
        "competition": "local_cup",
        "previous_winner_id": previous_winner_id,
        "participants": [team.id for team in participants],
        "participant_count": len(participants),
        "regional_advancers": advancers,
        "po_candidates": po_candidates,
        "merged_regions": merged_regions,
        "regional_slot_rules": regional_slot_rules,
        "matches": qualifier_matches + main_matches,
    }
