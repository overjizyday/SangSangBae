from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Iterable, Sequence

from .models import Match
from .simulation import simulate_baseball_game, simulate_baseball_game_with_aggregate

WEST_GROUPS = ["A", "B", "C", "D"]
EAST_GROUPS = ["E", "F", "G", "H"]


def simulate_match(match: Match, rng: random.Random, decisive: bool = False, walkoff: bool = True) -> None:
    if match.home_score is None or match.away_score is None:
        generated_home, generated_away = simulate_baseball_game(rng, decisive=decisive, walkoff=walkoff)
        if match.home_score is None:
            match.home_score = generated_home
        if match.away_score is None:
            match.away_score = generated_away

    if match.home_score > match.away_score:
        match.winner_team_id = match.home_team_id
        match.loser_team_id = match.away_team_id
        return
    if match.home_score < match.away_score:
        match.winner_team_id = match.away_team_id
        match.loser_team_id = match.home_team_id
        return

    advantage = match.advantage_team_id
    if advantage == match.home_team_id:
        match.winner_team_id = match.home_team_id
        match.loser_team_id = match.away_team_id
        return
    if advantage == match.away_team_id:
        match.winner_team_id = match.away_team_id
        match.loser_team_id = match.home_team_id
        return

    match.winner_team_id = None
    match.loser_team_id = None


def team_table(matches: Iterable[Match]) -> dict[str, dict[str, int]]:
    table: dict[str, dict[str, int]] = defaultdict(
        lambda: {"played": 0, "wins": 0, "draws": 0, "losses": 0, "gf": 0, "ga": 0}
    )
    for match in matches:
        if match.home_score is None or match.away_score is None:
            continue
        home = table[match.home_team_id]
        away = table[match.away_team_id]
        home["played"] += 1
        away["played"] += 1
        home["gf"] += match.home_score
        home["ga"] += match.away_score
        away["gf"] += match.away_score
        away["ga"] += match.home_score
        if match.home_score > match.away_score:
            home["wins"] += 1
            away["losses"] += 1
        elif match.home_score < match.away_score:
            away["wins"] += 1
            home["losses"] += 1
        else:
            home["draws"] += 1
            away["draws"] += 1
    for values in table.values():
        values["gd"] = values["gf"] - values["ga"]
        values["points"] = values["wins"] * 3 + values["draws"]
    return table


def sort_table(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        rows,
        key=lambda row: (
            int(row.get("points", 0)),
            int(row.get("gd", 0)),
            int(row.get("gf", 0)),
            -int(row.get("ga", 0)),
            str(row.get("team_name", row.get("team_id", ""))),
        ),
        reverse=True,
    )


def _round_priority(competition: str, stage: str, round_label: str) -> tuple[int, int, str]:
    stage = stage.lower()
    round_label = str(round_label)
    if stage == "preliminary":
        return (0, _round_sort_key(round_label)[0], round_label)
    if competition == "fa_cup" and stage == "r16":
        return (1, 0, "R16")
    order = {"qf": 2, "sf": 3, "final": 4}
    return (1, order.get(stage, 9), stage.upper())


def _build_knockout_standings(matches: list[Match], competition: str) -> list[dict[str, object]]:
    overall = team_table(matches)
    grouped: dict[tuple[str, str, int], list[Match]] = defaultdict(list)
    for match in matches:
        grouped[(str(match.stage).lower(), str(match.round), int(match.match_no or 0))].append(match)

    eliminations: dict[str, dict[str, object]] = {}

    for (stage, round_label, match_no), group in sorted(grouped.items(), key=lambda item: _round_priority(competition, item[0][0], item[0][1])):
        team_scores: dict[str, dict[str, int]] = defaultdict(lambda: {"gf": 0, "ga": 0})
        teams: list[str] = []
        for match in group:
            for team_id in [match.home_team_id, match.away_team_id]:
                if team_id not in teams:
                    teams.append(team_id)
            if match.home_team_id:
                team_scores[match.home_team_id]["gf"] += int(match.home_score or 0)
                team_scores[match.home_team_id]["ga"] += int(match.away_score or 0)
            if match.away_team_id:
                team_scores[match.away_team_id]["gf"] += int(match.away_score or 0)
                team_scores[match.away_team_id]["ga"] += int(match.home_score or 0)

        if len(teams) < 2:
            continue

        ordered = sorted(
            teams,
            key=lambda team_id: (
                team_scores[team_id]["gf"] - team_scores[team_id]["ga"],
                team_scores[team_id]["gf"],
                team_id,
            ),
            reverse=True,
        )
        winner = group[-1].winner_team_id or ordered[0]
        loser = next((team_id for team_id in ordered if team_id != winner), ordered[-1])

        if stage == "final":
            eliminations[winner] = {
                "eliminated_stage": "우승",
                "stage_rank": 500,
                "elim_gf": team_scores[winner]["gf"],
                "elim_ga": team_scores[winner]["ga"],
                "elim_gd": team_scores[winner]["gf"] - team_scores[winner]["ga"],
            }
            eliminations[loser] = {
                "eliminated_stage": "결승 탈락",
                "stage_rank": 400,
                "elim_gf": team_scores[loser]["gf"],
                "elim_ga": team_scores[loser]["ga"],
                "elim_gd": team_scores[loser]["gf"] - team_scores[loser]["ga"],
            }
            continue

        prelim_round_no = 0
        if stage == "preliminary" and isinstance(round_label, str) and round_label.upper().startswith("R"):
            try:
                prelim_round_no = int(round_label[1:])
            except ValueError:
                prelim_round_no = 0

        stage_label = {
            "preliminary": f"{round_label} 탈락",
            "qf": "8강 탈락",
            "sf": "4강 탈락",
            "r16": "16강 탈락",
        }.get(stage, f"{round_label} 탈락")
        # Preliminary rounds must be ordered by how late the team reached:
        # R1 < R2 < R3 ... < R16 < QF < SF < Final.
        stage_rank = {
            "preliminary": 100 + prelim_round_no,
            "r16": 200,
            "qf": 300,
            "sf": 350,
        }.get(stage, 0)
        eliminations[loser] = {
            "eliminated_stage": stage_label,
            "stage_rank": stage_rank,
            "elim_gf": team_scores[loser]["gf"],
            "elim_ga": team_scores[loser]["ga"],
            "elim_gd": team_scores[loser]["gf"] - team_scores[loser]["ga"],
        }

    rows = []
    for team_id, values in overall.items():
        elimination = eliminations.get(
            team_id,
            {
                "eliminated_stage": "미확정",
                "stage_rank": 0,
                "elim_gf": 0,
                "elim_ga": 0,
                "elim_gd": 0,
            },
        )
        placement_points = int(elimination["stage_rank"])
        rows.append(
            {
                "team_id": team_id,
                "team_name": team_id,
                "played": values["played"],
                "wins": values["wins"],
                "draws": values["draws"],
                "losses": values["losses"],
                "gf": values["gf"],
                "ga": values["ga"],
                "gd": values["gd"],
                "points": placement_points,
                "eliminated_stage": elimination["eliminated_stage"],
                "elim_gf": elimination["elim_gf"],
                "elim_ga": elimination["elim_ga"],
                "elim_gd": elimination["elim_gd"],
                "rank": 0,
            }
        )

    unresolved = [row for row in rows if row["eliminated_stage"] == "미확정"]
    if unresolved:
        for row in unresolved:
            row["points"] = 0
            row["rank"] = 0

    rows.sort(
        key=lambda row: (
            int(row.get("points", 0)),
            int(row.get("elim_gd", 0)),
            int(row.get("elim_gf", 0)),
            int(row.get("gd", 0)),
            int(row.get("gf", 0)),
            str(row.get("team_id", "")),
        ),
        reverse=True,
    )
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows


def _build_local_cup_standings(matches: list[Match], participants: Sequence[str]) -> list[dict[str, object]]:
    overall = team_table(matches)
    team_stage: dict[str, tuple[int, str]] = {}
    team_scores: dict[str, dict[str, int]] = defaultdict(lambda: {"gf": 0, "ga": 0})
    stage_rank = {
        "regional_qualifier": 0,
        "group": 1,
        "qf": 2,
        "sf": 3,
        "final": 4,
    }
    stage_label = {
        0: "지역예선 탈락",
        1: "조별 탈락",
        2: "8강 탈락",
        3: "4강 탈락",
        4: "결승 탈락",
        5: "우승",
    }

    for match in matches:
        stage = str(match.stage).lower()
        rank = stage_rank.get(stage, 0)
        for team_id, gf, ga in [
            (match.home_team_id, int(match.home_score or 0), int(match.away_score or 0)),
            (match.away_team_id, int(match.away_score or 0), int(match.home_score or 0)),
        ]:
            if not team_id:
                continue
            if rank > team_stage.get(team_id, (0, ""))[0]:
                team_stage[team_id] = (rank, stage)
            team_scores[team_id]["gf"] += gf
            team_scores[team_id]["ga"] += ga

        if stage == "final" and match.winner_team_id and match.loser_team_id:
            team_stage[match.winner_team_id] = (5, "final")
            team_stage[match.loser_team_id] = (4, "final")
        elif stage == "sf" and match.winner_team_id and match.loser_team_id:
            team_stage[match.winner_team_id] = max(team_stage.get(match.winner_team_id, (0, "")), (3, "sf"))
            team_stage[match.loser_team_id] = max(team_stage.get(match.loser_team_id, (0, "")), (3, "sf"))
        elif stage == "qf" and match.winner_team_id and match.loser_team_id:
            team_stage[match.winner_team_id] = max(team_stage.get(match.winner_team_id, (0, "")), (2, "qf"))
            team_stage[match.loser_team_id] = max(team_stage.get(match.loser_team_id, (0, "")), (2, "qf"))

    rows = []
    participant_ids = [str(team_id) for team_id in participants]
    for team_id in participant_ids:
        stats = overall.get(team_id, {"played": 0, "wins": 0, "draws": 0, "losses": 0, "gf": 0, "ga": 0, "gd": 0, "points": 0})
        rank_value, reached_stage = team_stage.get(team_id, (0, "regional_qualifier"))
        if rank_value >= 4:
            eliminated_stage = "우승" if rank_value == 5 else "결승 탈락"
        elif rank_value == 3:
            eliminated_stage = "4강 탈락"
        elif rank_value == 2:
            eliminated_stage = "8강 탈락"
        elif rank_value == 1:
            eliminated_stage = "조별 탈락"
        else:
            eliminated_stage = stage_label[0]

        elim_gf = team_scores[team_id]["gf"]
        elim_ga = team_scores[team_id]["ga"]
        rows.append(
            {
                "team_id": team_id,
                "team_name": team_id,
                "played": stats["played"],
                "gf": stats["gf"],
                "ga": stats["ga"],
                "gd": stats["gd"],
                "points": rank_value,
                "eliminated_stage": eliminated_stage,
                "elim_gf": elim_gf,
                "elim_ga": elim_ga,
                "elim_gd": elim_gf - elim_ga,
                "rank": 0,
            }
        )

    rows.sort(
        key=lambda row: (
            int(row.get("points", 0)),
            int(row.get("elim_gd", 0)),
            int(row.get("elim_gf", 0)),
            int(row.get("gd", 0)),
            int(row.get("gf", 0)),
            str(row.get("team_id", "")),
        ),
        reverse=True,
    )
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows


def resolve_linear_bracket(payload: dict[str, object], seed: int = 7) -> None:
    matches = [m for m in payload.get("matches", []) if isinstance(m, Match)]
    competition = str(payload.get("competition", ""))
    if not competition:
        if "auto_qf" in payload:
            competition = "championship"
        elif "auto_r16" in payload:
            competition = "fa_cup"
        elif any(m.competition == "championship" for m in matches):
            competition = "championship"
        elif any(m.competition == "fa_cup" for m in matches):
            competition = "fa_cup"
    if competition not in {"championship", "fa_cup"}:
        return
    rng = random.Random(seed)
    if competition == "championship":
        _resolve_championship(payload, matches, rng)
    else:
        _resolve_fa_cup(payload, matches, rng)


def resolve_super_cup(payload: dict[str, object], seed: int = 7) -> None:
    matches = [m for m in payload.get("matches", []) if isinstance(m, Match)]
    entrants = [row for row in payload.get("entrants", []) if isinstance(row, dict)]
    if not matches or not entrants:
        return
    rng = random.Random(seed)
    base_points = {str(row["team_id"]): int(row.get("points", 0)) for row in entrants}
    names = {str(row["team_id"]): str(row.get("team_name", row["team_id"])) for row in entrants}

    for match in matches:
        simulate_match(match, rng, decisive=False)

    table = team_table(matches)
    standings = []
    for team_id, stats in table.items():
        row = {
            "team_id": team_id,
            "team_name": names.get(team_id, team_id),
            "played": stats["played"],
            "wins": stats["wins"],
            "draws": stats["draws"],
            "losses": stats["losses"],
            "gf": stats["gf"],
            "ga": stats["ga"],
            "gd": stats["gd"],
            "points": stats["points"] + base_points.get(team_id, 0),
        }
        standings.append(row)

    standings = sort_table(standings)
    payload["standings"] = standings
    champions = payload.setdefault("champions", {})
    if standings:
        champions["super_cup"] = standings[0]["team_id"]


def resolve_local_cup(payload: dict[str, object], seed: int = 7) -> None:
    matches = [m for m in payload.get("matches", []) if isinstance(m, Match)]
    if not matches:
        return
    rng = random.Random(seed)
    previous_winner = payload.get("previous_winner_id")
    participants = list(payload.get("participants", []))
    participant_ids = [str(team_id) for team_id in participants]
    slot_rules = {
        (str(item.get("region")), str(item.get("group") or "")): {
            "direct_slots": int(item.get("direct_slots", 0)),
            "po_slots": int(item.get("po_slots", 0)),
            "original_size": int(item.get("original_size", 0)),
        }
        for item in payload.get("regional_slot_rules", [])
        if isinstance(item, dict)
    }
    merged_regions = {
        str(region): [str(team_id) for team_id in members]
        for region, members in dict(payload.get("merged_regions", {})).items()
        if isinstance(members, list)
    }

    def _fill_slots(current: list[str], target_count: int) -> list[str]:
        filled: list[str] = []
        seen: set[str] = set()
        for team_id in current:
            team_id = str(team_id)
            if not team_id or team_id in seen:
                continue
            filled.append(team_id)
            seen.add(team_id)
        for team_id in participant_ids:
            if len(filled) >= target_count:
                break
            if team_id in seen:
                continue
            filled.append(team_id)
            seen.add(team_id)
        return filled[:target_count]

    regional_matches = [m for m in matches if m.stage == "regional_qualifier"]
    po_matches = [m for m in matches if "po" in str(m.stage).lower()]
    group_matches = [m for m in matches if m.stage == "group"]
    knockout_matches = [m for m in matches if m.stage in {"qf", "r16", "sf", "final"}]

    group_map: dict[tuple[str | None, str | None], list[Match]] = defaultdict(list)
    for match in regional_matches:
        group_map[(match.region, match.group)].append(match)

    advancers: list[str] = []
    po_candidates: list[str] = []
    for key in sorted(group_map):
        group = group_map[key]
        teams = sorted({team for match in group for team in (match.home_team_id, match.away_team_id)})
        for match in group:
            simulate_match(match, rng, decisive=False)
        stats = team_table(group)
        ranked = sort_table(
            [{"team_id": team_id, **values} for team_id, values in stats.items()]
        )
        rule = slot_rules.get((str(key[0]), str(key[1] or "")))
        if rule:
            direct_slots = int(rule["direct_slots"])
            po_slots = int(rule["po_slots"])
        else:
            original_size = len(teams)
            region_members = merged_regions.get(str(key[0]), [])
            if previous_winner and str(previous_winner) in region_members and str(previous_winner) not in teams:
                original_size += 1
            direct_slots = original_size // 2
            po_slots = 1 if original_size % 2 == 1 else 0
        advancers.extend(row["team_id"] for row in ranked[:direct_slots])
        if po_slots and len(ranked) > direct_slots:
            po_candidates.append(ranked[direct_slots]["team_id"])

    for idx, match in enumerate(sorted(po_matches, key=lambda m: (m.match_no or 0, m.id))):
        pair_idx = idx * 2
        if pair_idx + 1 >= len(po_candidates):
            po_candidates = _fill_slots(po_candidates, pair_idx + 2)
        if pair_idx + 1 >= len(po_candidates):
            break
        match.home_team_id = po_candidates[pair_idx]
        match.away_team_id = po_candidates[pair_idx + 1]
        simulate_match(match, rng, decisive=True)
        advancers.append(match.winner_team_id or match.home_team_id)

    unresolved_po_matches = [
        match
        for match in matches
        if any(
            token in match.home_team_id or token in match.away_team_id
            for token in ["_PO후보", "_예선통과_", "승자_", "TBD_", "PENDING_"]
        )
    ]
    for idx, match in enumerate(unresolved_po_matches):
        pair_idx = idx * 2
        if pair_idx + 1 >= len(po_candidates):
            po_candidates = _fill_slots(po_candidates, pair_idx + 2)
        if pair_idx + 1 >= len(po_candidates):
            break
        match.home_team_id = po_candidates[pair_idx]
        match.away_team_id = po_candidates[pair_idx + 1]
        simulate_match(match, rng, decisive=True)

    main_teams = list(advancers)
    if previous_winner:
        main_teams.insert(0, str(previous_winner))

    main_total = int(payload.get("participant_count", len(main_teams))) // 2 + 1
    rounds_present = {str(match.round).upper() for match in knockout_matches}
    qf_matches = [m for m in knockout_matches if str(m.round).upper() == "QF"]
    r16_matches = [m for m in knockout_matches if str(m.round).upper() == "R16"]
    sf_matches = [m for m in knockout_matches if str(m.round).upper() == "SF"]
    final_match = next((m for m in knockout_matches if str(m.round).upper() == "FINAL"), None)

    def _finalize() -> None:
        payload["standings"] = _build_local_cup_standings(matches, participant_ids)

    if group_matches:
        group_names = sorted({str(match.group) for match in group_matches if match.group})
        group_size = 4 if len(group_names) >= 4 else 3
        slots_per_group = 4 if group_size == 4 else 3
        cursor = 0
        group_advancers: list[list[str]] = []

        for group_name in group_names:
            members = main_teams[cursor : cursor + slots_per_group]
            cursor += slots_per_group
            group_rounds = sorted(
                [m for m in group_matches if m.group == group_name],
                key=lambda m: (int(m.match_no or 0), m.id),
            )
            pairings = _local_group_pairings(members)
            for idx, match in enumerate(group_rounds):
                home, away = pairings[idx % len(pairings)]
                match.home_team_id = home
                match.away_team_id = away
                simulate_match(match, rng, decisive=False)

            stats = team_table(group_rounds)
            ranked = sort_table(
                [{"team_id": team_id, **values} for team_id, values in stats.items()]
            )
            direct_slots = len(members) // 2
            group_advancers.append([str(row["team_id"]) for row in ranked[:direct_slots]])

        if main_total == 16 and qf_matches:
            advancing_slots = _fill_slots(_local_post_group_first_round_slots(group_advancers), 8)
            _resolve_advantage_single_leg_round(qf_matches, advancing_slots[:8], rng)
            winners = _collect_winners(qf_matches)
            _resolve_single_leg_round(sf_matches, _bracket_order(winners), rng)
            final_teams = _collect_winners(sf_matches)
            if final_match and len(final_teams) >= 2:
                final_match.home_team_id, final_match.away_team_id = final_teams[:2]
                simulate_match(final_match, rng, decisive=True)
                payload.setdefault("champions", {})["local_cup"] = final_match.winner_team_id or final_match.home_team_id
            _finalize()
            return

        if main_total == 32 and r16_matches:
            advancing_slots = _fill_slots(_local_post_group_first_round_slots(group_advancers), 16)
            _resolve_advantage_single_leg_round(r16_matches, advancing_slots[:16], rng)
            winners = _collect_winners(r16_matches)
            _resolve_single_leg_round(qf_matches, _bracket_order(winners), rng)
            winners = _collect_winners(qf_matches)
            _resolve_single_leg_round(sf_matches, _bracket_order(winners), rng)
            final_teams = _collect_winners(sf_matches)
            if final_match and len(final_teams) >= 2:
                final_match.home_team_id, final_match.away_team_id = final_teams[:2]
                simulate_match(final_match, rng, decisive=True)
                payload.setdefault("champions", {})["local_cup"] = final_match.winner_team_id or final_match.home_team_id
            _finalize()
            return

    if main_total == 8 and qf_matches:
        main_teams = _fill_slots(main_teams, 8)
        winners = _resolve_two_leg_pairs(qf_matches, _pair_up(main_teams[:8]), rng)
        final_teams = _resolve_two_leg_pairs(sf_matches, _pair_up(_bracket_order(winners)), rng)
        if final_match and len(final_teams) >= 2:
            final_match.home_team_id, final_match.away_team_id = final_teams[:2]
            simulate_match(final_match, rng, decisive=True)
            payload.setdefault("champions", {})["local_cup"] = final_match.winner_team_id or final_match.home_team_id
        _finalize()
        return

    # Fallback for other shapes.
    if qf_matches:
        _resolve_single_leg_round(qf_matches, main_teams[: len(qf_matches) * 2], rng)
    if sf_matches:
        _resolve_single_leg_round(sf_matches, _collect_winners(qf_matches), rng)
    if final_match:
        finalists = _collect_winners(sf_matches)
        if len(finalists) >= 2:
            final_match.home_team_id, final_match.away_team_id = finalists[:2]
            simulate_match(final_match, rng, decisive=True)
            payload.setdefault("champions", {})["local_cup"] = final_match.winner_team_id or final_match.home_team_id

    _finalize()

    payload["standings"] = _build_local_cup_standings(matches, participant_ids)


def resolve_acl(payload: dict[str, object], seed: int = 7, year: int = 1970) -> None:
    matches = [m for m in payload.get("matches", []) if isinstance(m, Match)]
    if not matches:
        return

    rng = random.Random(seed)
    champions = payload.setdefault("champions", {})

    for league in ["ACL1", "ACL2", "ACL3"]:
        league_matches = [m for m in matches if m.stage.startswith(f"{league}_")]
        group_matches = [m for m in league_matches if m.stage.endswith("_group")]
        if not group_matches:
            continue

        for match in group_matches:
            simulate_match(match, rng, decisive=False)

        group_tables: dict[str, list[dict[str, object]]] = {}
        for group_name in sorted({m.group for m in group_matches if m.group}):
            round_matches = [m for m in group_matches if m.group == group_name]
            table = team_table(round_matches)
            group_tables[group_name] = sort_table(
                [{"team_id": team_id, **values} for team_id, values in table.items()]
            )

        west_advancers: list[str] = []
        east_advancers: list[str] = []
        for group_name in WEST_GROUPS:
            rows = group_tables.get(group_name, [])
            if len(rows) >= 2:
                west_advancers.extend([rows[0]["team_id"], rows[1]["team_id"]])
        for group_name in EAST_GROUPS:
            rows = group_tables.get(group_name, [])
            if len(rows) >= 2:
                east_advancers.extend([rows[0]["team_id"], rows[1]["team_id"]])

        west_r16 = [m for m in league_matches if m.stage.endswith("_r16") and m.region == "west"]
        east_r16 = [m for m in league_matches if m.stage.endswith("_r16") and m.region == "east"]
        west_r16_winners = _resolve_two_leg_pairs(
            west_r16,
            [
                (west_advancers[0], west_advancers[3]),
                (west_advancers[2], west_advancers[1]),
                (west_advancers[4], west_advancers[7]),
                (west_advancers[6], west_advancers[5]),
            ],
            rng,
        )
        east_r16_winners = _resolve_two_leg_pairs(
            east_r16,
            [
                (east_advancers[0], east_advancers[3]),
                (east_advancers[2], east_advancers[1]),
                (east_advancers[4], east_advancers[7]),
                (east_advancers[6], east_advancers[5]),
            ],
            rng,
        )

        west_qf = [m for m in league_matches if m.stage.endswith("_qf") and m.region == "west"]
        east_qf = [m for m in league_matches if m.stage.endswith("_qf") and m.region == "east"]
        west_qf_winners = _resolve_two_leg_pairs(
            west_qf,
            [
                (west_r16_winners[0], west_r16_winners[3]),
                (west_r16_winners[2], west_r16_winners[1]),
            ],
            rng,
        )
        east_qf_winners = _resolve_two_leg_pairs(
            east_qf,
            [
                (east_r16_winners[0], east_r16_winners[3]),
                (east_r16_winners[2], east_r16_winners[1]),
            ],
            rng,
        )

        west_sf = [m for m in league_matches if m.stage.endswith("_sf") and m.region == "west"]
        east_sf = [m for m in league_matches if m.stage.endswith("_sf") and m.region == "east"]
        west_sf_winner = _resolve_two_leg_pairs(
            west_sf,
            [(west_qf_winners[0], west_qf_winners[1])],
            rng,
        )[0]
        east_sf_winner = _resolve_two_leg_pairs(
            east_sf,
            [(east_qf_winners[0], east_qf_winners[1])],
            rng,
        )[0]
        regional_champions = payload.setdefault("regional_champions", {})
        if isinstance(regional_champions, dict):
            regional_champions[league] = {"west": west_sf_winner, "east": east_sf_winner}

        final_match = next((m for m in league_matches if m.stage.endswith("_final")), None)
        if final_match:
            if year % 2 == 1:
                final_match.home_team_id = west_sf_winner
                final_match.away_team_id = east_sf_winner
            else:
                final_match.home_team_id = east_sf_winner
                final_match.away_team_id = west_sf_winner
            simulate_match(final_match, rng, decisive=True)
            champions[league] = final_match.winner_team_id or final_match.home_team_id


def _resolve_championship(payload: dict[str, object], matches: list[Match], rng: random.Random) -> None:
    prelim_matches = [m for m in matches if str(m.stage).lower() == "preliminary"]
    qf_matches = [m for m in matches if str(m.stage).lower() == "qf"]
    sf_matches = [m for m in matches if str(m.stage).lower() == "sf"]
    final_match = next((m for m in matches if str(m.stage).lower() == "final"), None)

    rounds_needed = int(payload.get("rounds_needed", 0))
    byes_by_round = {str(key): list(value) for key, value in payload.get("byes_by_round", {}).items()}
    auto_qf = list(payload.get("auto_qf", []))

    current_slots: list[str] = []
    for round_no in range(1, rounds_needed + 1):
        label = f"R{round_no}"
        round_matches = sorted(
            [m for m in prelim_matches if str(m.round) == label],
            key=lambda m: (m.match_no or 0, m.id),
        )
        if not round_matches:
            continue
        if current_slots:
            _assign_single_leg_round(round_matches, current_slots, rng)
        else:
            for match in round_matches:
                simulate_match(match, rng, decisive=True)
        winners = _collect_winners(round_matches)
        current_slots = list(byes_by_round.get(f"R{round_no + 1}", [])) + winners

    if not current_slots:
        current_slots = _collect_winners(sorted(prelim_matches, key=lambda m: (str(m.round), m.match_no or 0, m.id)))

    qf_slots = auto_qf + current_slots
    qf_winners = _resolve_two_leg_pairs(qf_matches, _pair_up(qf_slots), rng)
    sf_winners = _resolve_two_leg_pairs(sf_matches, _pair_up(_bracket_order(qf_winners)), rng)

    if final_match and len(sf_winners) >= 2:
        final_match.home_team_id = sf_winners[0]
        final_match.away_team_id = sf_winners[1]
        simulate_match(final_match, rng, decisive=True)
        payload.setdefault("champions", {})["championship"] = final_match.winner_team_id or final_match.home_team_id
    payload["standings"] = _build_knockout_standings(matches, "championship")


def _resolve_fa_cup(payload: dict[str, object], matches: list[Match], rng: random.Random) -> None:
    participants = list(payload.get("participants", []))
    if not participants:
        return

    auto_r16 = list(participants[:4])
    current_slots = list(participants[4:])

    prelim_matches = [m for m in matches if str(m.stage).lower() == "preliminary"]
    round_labels = sorted({str(m.round) for m in prelim_matches}, key=_round_sort_key)
    for label in round_labels:
        round_matches = sorted(
            [m for m in prelim_matches if str(m.round) == label],
            key=lambda m: (m.match_no or 0, m.id),
        )
        if not round_matches:
            continue
        _assign_single_leg_round(round_matches, current_slots, rng)
        winners = _collect_winners(round_matches)
        byes_count = max(0, len(current_slots) - len(round_matches) * 2)
        byes = current_slots[len(round_matches) * 2 : len(round_matches) * 2 + byes_count]
        current_slots = list(byes) + winners

    r16_matches = [m for m in matches if str(m.stage).lower() == "r16"]
    qf_matches = [m for m in matches if str(m.stage).lower() == "qf"]
    sf_matches = [m for m in matches if str(m.stage).lower() == "sf"]
    final_match = next((m for m in matches if str(m.stage).lower() == "final"), None)

    r16_slots = auto_r16 + current_slots
    r16_winners = _resolve_two_leg_pairs(r16_matches, _pair_up(r16_slots), rng)
    qf_winners = _resolve_two_leg_pairs(qf_matches, _pair_up(_bracket_order(r16_winners)), rng)
    sf_winners = _resolve_two_leg_pairs(sf_matches, _pair_up(_bracket_order(qf_winners)), rng)

    if final_match and len(sf_winners) >= 2:
        final_match.home_team_id = sf_winners[0]
        final_match.away_team_id = sf_winners[1]
        simulate_match(final_match, rng, decisive=True)
        payload.setdefault("champions", {})["fa_cup"] = final_match.winner_team_id or final_match.home_team_id
    payload["standings"] = _build_knockout_standings(matches, "fa_cup")


def _assign_single_leg_round(matches: list[Match], teams: Sequence[str], rng: random.Random) -> None:
    ordered_matches = sorted(matches, key=lambda m: (m.match_no or 0, m.id))
    for idx, match in enumerate(ordered_matches):
        home_idx = idx * 2
        away_idx = home_idx + 1
        if away_idx >= len(teams):
            break
        match.home_team_id = teams[home_idx]
        match.away_team_id = teams[away_idx]
        simulate_match(match, rng, decisive=True)


def _resolve_single_leg_round(matches: list[Match], teams: Sequence[str], rng: random.Random) -> None:
    ordered_matches = sorted(matches, key=lambda m: (m.match_no or 0, m.id))
    _assign_single_leg_round(ordered_matches, teams, rng)


def _resolve_advantage_single_leg_round(matches: list[Match], teams: Sequence[str], rng: random.Random) -> None:
    ordered_matches = sorted(matches, key=lambda m: (m.match_no or 0, m.id))
    for idx, match in enumerate(ordered_matches):
        home_idx = idx * 2
        away_idx = home_idx + 1
        if away_idx >= len(teams):
            break
        match.home_team_id = teams[home_idx]
        match.away_team_id = teams[away_idx]
        match.advantage_team_id = match.home_team_id
        simulate_match(match, rng, decisive=False, walkoff=True)


def _local_post_group_first_round_slots(group_advancers: Sequence[Sequence[str]]) -> list[str]:
    slots: list[str] = []
    for idx in range(0, len(group_advancers) - 1, 2):
        first_group = list(group_advancers[idx])
        second_group = list(group_advancers[idx + 1])
        if len(first_group) < 2 or len(second_group) < 2:
            continue
        first_winner, first_runner_up = first_group[0], first_group[1]
        second_winner, second_runner_up = second_group[0], second_group[1]
        slots.extend(
            [
                second_winner,
                first_runner_up,
                first_winner,
                second_runner_up,
            ]
        )
    return slots


def _resolve_two_leg_pairs(matches: list[Match], pairs: list[tuple[str, str]], rng: random.Random) -> list[str]:
    ordered = sorted(matches, key=lambda m: (m.match_no or 0, m.leg or 0, m.id))
    winners: list[str] = []
    for idx, (home, away) in enumerate(pairs):
        if idx * 2 + 1 >= len(ordered):
            break
        leg1 = ordered[idx * 2]
        leg2 = ordered[idx * 2 + 1]
        leg1.home_team_id = home
        leg1.away_team_id = away
        simulate_match(leg1, rng, decisive=False, walkoff=False)
        leg2.home_team_id = away
        leg2.away_team_id = home
        if leg2.home_score is None or leg2.away_score is None:
            leg2.home_score, leg2.away_score = simulate_baseball_game_with_aggregate(
                rng,
                prior_away_total=int(leg1.home_score or 0),
                prior_home_total=int(leg1.away_score or 0),
            )
        home_agg = (leg1.home_score or 0) + (leg2.away_score or 0)
        away_agg = (leg1.away_score or 0) + (leg2.home_score or 0)
        if home_agg > away_agg:
            leg2.winner_team_id = home
            leg2.loser_team_id = away
            winners.append(home)
        else:
            leg2.winner_team_id = away
            leg2.loser_team_id = home
            winners.append(away)
    return winners


def _pair_up(teams: Sequence[str]) -> list[tuple[str, str]]:
    pairs = []
    for idx in range(0, len(teams) - 1, 2):
        pairs.append((teams[idx], teams[idx + 1]))
    return pairs


def _bracket_order(teams: Sequence[str]) -> list[str]:
    ordered = list(teams)
    if len(ordered) == 4:
        return [ordered[0], ordered[3], ordered[1], ordered[2]]
    if len(ordered) == 8:
        return [ordered[0], ordered[7], ordered[1], ordered[6], ordered[2], ordered[5], ordered[3], ordered[4]]
    return ordered


def _collect_winners(matches: Sequence[Match]) -> list[str]:
    winners = []
    for match in sorted(matches, key=lambda m: (m.match_no or 0, m.leg or 0, m.id)):
        winners.append(match.winner_team_id or match.home_team_id)
    return winners


def _local_group_pairings(members: Sequence[str]) -> list[tuple[str, str]]:
    if len(members) == 4:
        a, b, c, d = members
        return [
            (a, b),
            (c, d),
            (d, a),
            (b, c),
            (a, c),
            (b, d),
            (b, a),
            (d, c),
            (c, a),
            (d, b),
            (a, d),
            (c, b),
        ]
    if len(members) == 3:
        a, b, c = members
        return [
            (a, b),
            (b, c),
            (c, a),
            (b, a),
            (c, b),
            (a, c),
        ]
    if len(members) == 2:
        a, b = members
        return [(a, b), (b, a)]
    return [(member, member) for member in members]


def _round_sort_key(label: str) -> tuple[int, str]:
    digits = "".join(ch for ch in label if ch.isdigit())
    return (int(digits) if digits else 0, label)
