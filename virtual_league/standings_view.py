from __future__ import annotations

import csv
from dataclasses import asdict, is_dataclass
from collections import defaultdict
from html import escape
import re
from pathlib import Path

from .acl import association_city_pool
from .models import Match, Team
from .tournament_resolution import sort_table, team_table


def _as_dict(row: object) -> dict[str, object]:
    if isinstance(row, dict):
        return dict(row)
    if is_dataclass(row):
        return asdict(row)
    return dict(getattr(row, "__dict__", {}))


def _rank_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    ranked = sort_table(rows)
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx
    return ranked


_TEAM_ID_RE = re.compile(r"^(?P<country>.+)_(?P<slot>[A-Z])_FC(?P<index>\d+)?$")


def _looks_like_code(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_]+", name)) or "_FC" in name or name.startswith("T")


def _display_name(team_id: str, team_name: str, country: str = "") -> str:
    if team_name and team_name != team_id and not _looks_like_code(team_name):
        return team_name
    pool = association_city_pool(country)
    if pool:
        match = _TEAM_ID_RE.match(team_id)
        if match:
            index = int(match.group("index") or 1) - 1
            return pool[index % len(pool)]
        return pool[0]
    return team_name if team_name and team_name != team_id else team_id


def _cup_stage_order(stage: str) -> int:
    return {
        "우승": 0,
        "결승 탈락": 1,
        "4강 탈락": 2,
        "8강 탈락": 3,
        "16강 탈락": 4,
        "r16 탈락": 4,
        "r1 탈락": 5,
        "r2 탈락": 4,
        "지역예선 탈락": 6,
        "조별 탈락": 7,
        "미확정": 99,
    }.get(stage.strip().lower() if isinstance(stage, str) else stage, 50)


def _cup_display_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    ordered = sorted(
        rows,
        key=lambda row: (
            _cup_stage_order(str(row.get("eliminated_stage", ""))),
            -int(row.get("elim_gd", 0)),
            -int(row.get("elim_gf", 0)),
            -int(row.get("gd", 0)),
            -int(row.get("gf", 0)),
            str(row.get("team_name", row.get("team_id", ""))),
        ),
    )
    for idx, row in enumerate(ordered, start=1):
        row["rank"] = idx
    return ordered


_DAY_ORDER = {
    "\uc6d4": 0,
    "\ud654": 1,
    "\uc218": 2,
    "\ubaa9": 3,
    "\uae08": 4,
    "\ud1a0": 5,
    "\uc77c": 6,
}


def _match_execution_key(match: Match) -> tuple[int, int, int, int, str]:
    return (
        int(match.week or 0),
        _DAY_ORDER.get(str(match.day or ""), 99),
        int(match.match_no or 0),
        int(match.leg or 0),
        str(match.id or ""),
    )


def _is_knockout_stage(stage: str) -> bool:
    lower = stage.lower()
    return any(
        token in lower
        for token in [
            "preliminary",
            "po",
            "regional_po",
            "r16",
            "qf",
            "sf",
            "final",
            "_po",
            "_qf",
            "_sf",
            "_final",
        ]
    ) or bool(re.fullmatch(r"r\d+", lower))


def _competition_stage_key(name: str, stage: str) -> str:
    lower = stage.lower()
    if name in {"ACL1", "ACL2", "ACL3"} and lower.startswith(f"{name.lower()}_"):
        return lower.removeprefix(f"{name.lower()}_")
    return lower


def _knockout_stage_order(stage: str) -> int:
    lower = stage.lower()
    if "preliminary" in lower:
        return 0
    if lower.endswith("_po") or lower in {"po", "regional_po"}:
        return 1
    if re.fullmatch(r"r\d+", lower):
        return 2
    if "r16" in lower:
        return 2
    if "qf" in lower:
        return 3
    if "sf" in lower:
        return 4
    if "final" in lower:
        return 5
    return 9


def _team_label(team_id: str, names: dict[str, str]) -> str:
    if not team_id:
        return ""
    return names.get(team_id, team_id)


def _score_label(match: Match, names: dict[str, str]) -> str:
    home = _team_label(match.home_team_id, names)
    away = _team_label(match.away_team_id, names)
    if match.home_score is None or match.away_score is None:
        return f"{home} vs {away}"
    return f"{home} {match.home_score}-{match.away_score} {away}"


def _result_label(matches: list[Match], names: dict[str, str]) -> str:
    if not matches:
        return ""
    latest = sorted(matches, key=lambda match: int(match.leg or 0))[-1]
    if latest.winner_team_id:
        return _team_label(latest.winner_team_id, names)
    if any(match.home_score is None or match.away_score is None for match in matches):
        return ""
    scores: dict[str, int] = defaultdict(int)
    for match in matches:
        scores[match.home_team_id] += int(match.home_score or 0)
        scores[match.away_team_id] += int(match.away_score or 0)
    if len(scores) != 2:
        return ""
    ordered = sorted(scores.items(), key=lambda item: (item[1], item[0]), reverse=True)
    if ordered[0][1] == ordered[1][1]:
        return ""
    return _team_label(ordered[0][0], names)


def _confirmed_match(match: Match, known_team_ids: set[str]) -> bool:
    return match.home_team_id in known_team_ids and match.away_team_id in known_team_ids


def _build_knockout_rows(
    name: str,
    matches: list[Match],
    names: dict[str, str],
    known_team_ids: set[str],
) -> list[dict[str, object]]:
    knockout_matches = [
        match for match in matches if _is_knockout_stage(str(match.stage)) and _confirmed_match(match, known_team_ids)
    ]
    grouped: dict[tuple[str, str, str, int], list[Match]] = defaultdict(list)
    for match in knockout_matches:
        key = (
            _competition_stage_key(name, str(match.stage)),
            str(match.round),
            str(match.region or ""),
            int(match.match_no or 0),
        )
        grouped[key].append(match)

    rows = []
    for (stage, round_label, region, match_no), group in sorted(
        grouped.items(),
        key=lambda item: (
            _knockout_stage_order(item[0][0]),
            min((_match_execution_key(match) for match in item[1]), default=(9999, 99, 9999, 9999, "")),
            item[0][2],
            item[0][3],
        ),
    ):
        by_leg = {int(match.leg or 1): match for match in sorted(group, key=lambda match: int(match.leg or 0))}
        leg1 = by_leg.get(1) or group[0]
        leg2 = by_leg.get(2)
        rows.append(
            {
                "round": round_label,
                "region": region,
                "match": match_no,
                "leg1": _score_label(leg1, names),
                "leg2": _score_label(leg2, names) if leg2 else "",
                "winner": _result_label(group, names),
            }
        )
    return rows


def _build_acl_rows(
    league: str,
    matches: list[Match],
    participants: list[dict[str, object]],
    team_names: dict[str, str],
) -> list[dict[str, object]]:
    overall = team_table(matches)
    stage_rank: dict[str, int] = defaultdict(int)

    ordered_matches = sorted(
        matches,
        key=lambda match: (int(match.week), str(match.round), int(match.match_no or 0), int(match.leg or 0), match.id),
    )
    for match in ordered_matches:
        stage = str(match.stage).lower()
        if not stage.startswith(f"{league.lower()}_"):
            continue
        if stage.endswith("_final"):
            if match.winner_team_id:
                stage_rank[match.winner_team_id] = max(stage_rank[match.winner_team_id], 5)
            if match.loser_team_id:
                stage_rank[match.loser_team_id] = max(stage_rank[match.loser_team_id], 4)
        elif stage.endswith("_sf"):
            if match.winner_team_id:
                stage_rank[match.winner_team_id] = max(stage_rank[match.winner_team_id], 4)
            if match.loser_team_id:
                stage_rank[match.loser_team_id] = max(stage_rank[match.loser_team_id], 3)
        elif stage.endswith("_qf"):
            if match.winner_team_id:
                stage_rank[match.winner_team_id] = max(stage_rank[match.winner_team_id], 3)
            if match.loser_team_id:
                stage_rank[match.loser_team_id] = max(stage_rank[match.loser_team_id], 2)
        elif stage.endswith("_po"):
            if match.winner_team_id:
                stage_rank[match.winner_team_id] = max(stage_rank[match.winner_team_id], 2)
            if match.loser_team_id:
                stage_rank[match.loser_team_id] = max(stage_rank[match.loser_team_id], 1)

    rows: list[dict[str, object]] = []
    for item in participants:
        team_id = str(item.get("team_id", ""))
        if not team_id:
            continue
        raw_team_name = str(item.get("team_name", team_names.get(team_id, team_id)))
        country = str(item.get("country", ""))
        rows.append(
            {
                "team_id": team_id,
                "team_name": _display_name(team_id, raw_team_name, country),
                "played": int(overall.get(team_id, {}).get("played", 0)),
                "wins": int(overall.get(team_id, {}).get("wins", 0)),
                "draws": int(overall.get(team_id, {}).get("draws", 0)),
                "losses": int(overall.get(team_id, {}).get("losses", 0)),
                "gf": int(overall.get(team_id, {}).get("gf", 0)),
                "ga": int(overall.get(team_id, {}).get("ga", 0)),
                "gd": int(overall.get(team_id, {}).get("gd", 0)),
                "points": int(stage_rank.get(team_id, 0)),
            }
        )

    rows.sort(
        key=lambda row: (
            int(row.get("points", 0)),
            int(row.get("gd", 0)),
            int(row.get("gf", 0)),
            -int(row.get("ga", 0)),
            str(row.get("team_name", row.get("team_id", ""))),
        ),
        reverse=True,
    )
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows


def build_competition_tables(
    league_standings: list[object],
    competitions: list[dict[str, object]],
    teams: list[Team],
) -> dict[str, list[dict[str, object]]]:
    team_names = {team.id: team.name for team in teams}
    known_team_ids = set(team_names)
    tables: dict[str, list[dict[str, object]]] = {}

    league_rows = []
    for row in league_standings:
        item = _as_dict(row)
        team_id = str(item.get("team_id", ""))
        raw_team_name = str(item.get("team_name", team_names.get(team_id, "")))
        display_name = raw_team_name
        if _looks_like_code(display_name) or display_name == team_id:
            display_name = team_names.get(team_id, display_name)
        league_rows.append(
            {
                "team_id": team_id,
                "team_name": _display_name(team_id, display_name),
                "played": int(item.get("played", 0)),
                "wins": int(item.get("wins", 0)),
                "draws": int(item.get("draws", 0)),
                "losses": int(item.get("losses", 0)),
                "gf": int(item.get("goals_for", item.get("gf", 0))),
                "ga": int(item.get("goals_against", item.get("ga", 0))),
                "gd": int(item.get("goal_difference", item.get("gd", 0))),
                "points": int(item.get("points", 0)),
            }
        )
    tables["league"] = _rank_rows(league_rows)

    for competition in competitions:
        if not competition.get("held"):
            continue

        matches = [m for m in competition.get("matches", []) if isinstance(m, Match)]
        name = str(
            competition.get("competition")
            or (matches[0].competition if matches else "")
            or competition.get("stage")
            or "competition"
        )

        if name == "super_cup" and competition.get("standings"):
            rows = []
            for row in competition.get("standings", []):
                item = _as_dict(row)
                team_id = str(item.get("team_id", ""))
                raw_team_name = str(item.get("team_name", team_names.get(team_id, "")))
                display_name = raw_team_name
                if _looks_like_code(display_name) or display_name == team_id:
                    display_name = team_names.get(team_id, display_name)
                rows.append(
                    {
                        "team_id": team_id,
                        "team_name": _display_name(team_id, display_name),
                        "played": int(item.get("played", 0)),
                        "wins": int(item.get("wins", 0)),
                        "draws": int(item.get("draws", 0)),
                        "losses": int(item.get("losses", 0)),
                        "gf": int(item.get("gf", item.get("goals_for", 0))),
                        "ga": int(item.get("ga", item.get("goals_against", 0))),
                        "gd": int(item.get("gd", item.get("goal_difference", 0))),
                        "points": int(item.get("points", 0)),
                    }
                )
            tables[name] = _rank_rows(rows)
            continue

        if name in {"local_cup", "championship", "fa_cup"} and competition.get("standings"):
            rows = []
            for row in competition.get("standings", []):
                item = _as_dict(row)
                team_id = str(item.get("team_id", ""))
                raw_team_name = str(item.get("team_name", team_names.get(team_id, team_id)))
                display_name = raw_team_name
                if _looks_like_code(display_name) or display_name == team_id:
                    display_name = team_names.get(team_id, display_name)
                rows.append(
                    {
                        "team_id": team_id,
                        "team_name": _display_name(team_id, display_name),
                        "eliminated_stage": str(item.get("eliminated_stage", "")),
                        "elim_gf": int(item.get("elim_gf", 0)),
                        "elim_ga": int(item.get("elim_ga", 0)),
                        "elim_gd": int(item.get("elim_gd", 0)),
                        "gd": int(item.get("gd", item.get("goal_difference", 0))),
                        "gf": int(item.get("gf", item.get("goals_for", 0))),
                    }
                )
            tables[name] = _cup_display_rows(rows)
            knockout_rows = _build_knockout_rows(name, matches, team_names, known_team_ids)
            if knockout_rows:
                tables[f"__knockout__{name}"] = knockout_rows
            continue

        if name == "acl":
            participant_names = {
                str(item.get("team_id", "")): str(item.get("team_name", item.get("team_id", "")))
                for league_items in competition.get("participants", {}).values()
                for item in league_items
                if isinstance(item, dict)
            }
            known_acl_ids = known_team_ids | set(participant_names)
            for league in ["ACL1", "ACL2", "ACL3"]:
                league_matches = [m for m in matches if str(m.stage).startswith(f"{league}_")]
                league_participants = [
                    item
                    for item in competition.get("participants", {}).get(league, [])
                    if isinstance(item, dict)
                ]
                rows = _build_acl_rows(league, league_matches, league_participants, participant_names)
                if rows:
                    tables[league] = rows
                    knockout_rows = _build_knockout_rows(league, league_matches, participant_names, known_acl_ids)
                    if knockout_rows:
                        tables[f"__knockout__{league}"] = knockout_rows
            continue

        table = team_table(matches)
        rows = [
            {
                "team_id": team_id,
                "team_name": _display_name(team_id, team_names.get(team_id, team_id)),
                **stats,
            }
            for team_id, stats in table.items()
        ]
        tables[name] = _rank_rows(rows)
        knockout_rows = _build_knockout_rows(name, matches, team_names, known_team_ids)
        if knockout_rows:
            tables[f"__knockout__{name}"] = knockout_rows

    return tables


def write_standings_csv(path: Path, tables: dict[str, list[dict[str, object]]]) -> None:
    fieldnames = [
        "competition",
        "rank",
        "team_id",
        "team_name",
        "played",
        "wins",
        "draws",
        "losses",
        "gf",
        "ga",
        "gd",
        "points",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for competition, rows in tables.items():
            if competition.startswith("__knockout__"):
                continue
            for row in rows:
                writer.writerow(
                    {
                        "competition": competition,
                        "rank": row.get("rank", ""),
                        "team_id": row.get("team_id", ""),
                        "team_name": row.get("team_name", ""),
                        "played": row.get("played", 0),
                        "wins": row.get("wins", 0),
                        "draws": row.get("draws", 0),
                        "losses": row.get("losses", 0),
                        "gf": row.get("gf", 0),
                        "ga": row.get("ga", 0),
                        "gd": row.get("gd", 0),
                        "points": row.get("points", 0),
                    }
                )


def write_standings_html(path: Path, year: int, tables: dict[str, list[dict[str, object]]]) -> None:
    path.write_text(render_standings_html(year, tables), encoding="utf-8")


def render_standings_html(year: int, tables: dict[str, list[dict[str, object]]]) -> str:
    def render_rank_table(name: str, rows: list[dict[str, object]]) -> str:
        if not rows:
            return ""
        compact = name != "league" and name != "super_cup"
        if compact:
            headers = ["순위", "팀"]
            columns = ["rank", "team_name"]
        else:
            headers = ["순위", "팀", "경기", "승", "무", "패", "득점", "실점", "득실", "승점"]
            columns = ["rank", "team_name", "played", "wins", "draws", "losses", "gf", "ga", "gd", "points"]
        body = "".join(
            "<tr>"
            + "".join(f"<td>{escape(str(row.get(col, '')))}</td>" for col in columns)
            + "</tr>"
            for row in rows
        )
        return f"""
              <table>
                <thead>
                  <tr>{"".join(f"<th>{escape(header)}</th>" for header in headers)}</tr>
                </thead>
                <tbody>{body}</tbody>
              </table>
        """

    def render_knockout_table(rows: list[dict[str, object]]) -> str:
        headers = ["라운드", "지역", "매치", "1차전", "2차전", "승자"]
        columns = ["round", "region", "match", "leg1", "leg2", "winner"]
        body = "".join(
            "<tr>"
            + "".join(f"<td>{escape(str(row.get(col, '')))}</td>" for col in columns)
            + "</tr>"
            for row in rows
        )
        return f"""
              <table>
                <thead>
                  <tr>{"".join(f"<th>{escape(header)}</th>" for header in headers)}</tr>
                </thead>
                <tbody>{body}</tbody>
              </table>
        """

    def render_section(name: str, rows: list[dict[str, object]]) -> str:
        section_class = "panel wide" if name == "league" else "panel"
        knockout_rows = tables.get(f"__knockout__{name}", [])
        has_knockout = bool(knockout_rows)
        if name == "championship":
            body = render_knockout_table(knockout_rows) if has_knockout else '<p class="pending">토너먼트 일정이 없습니다.</p>'
            return f"""
            <section class="{section_class}">
              <h2>{escape(name)}</h2>
              <div class="view-panel" id="{escape(name)}-knockout">
                {body}
              </div>
            </section>
            """
        if name == "super_cup":
            return f"""
            <section class="{section_class}">
              <h2>{escape(name)}</h2>
              <div class="view-panel" id="{escape(name)}-rank">
                {render_rank_table(name, rows)}
              </div>
            </section>
            """
        if name == "local_cup":
            knockout_body = render_knockout_table(knockout_rows) if has_knockout else ""
            return f"""
            <section class="{section_class}">
              <h2>{escape(name)}</h2>
              <div class="view-toggle" role="group" aria-label="{escape(name)} 보기">
                <button class="toggle-btn active" type="button" data-target="{escape(name)}-regional">지역예선순위</button>
                <button class="toggle-btn" type="button" data-target="{escape(name)}-groups" disabled>조별예선순위</button>
                <button class="toggle-btn" type="button" data-target="{escape(name)}-knockout"{"" if has_knockout else " disabled"}>토너먼트</button>
              </div>
              <div class="view-panel" id="{escape(name)}-regional">
                {render_rank_table(name, rows)}
              </div>
              <div class="view-panel" id="{escape(name)}-groups" hidden>
                <p class="pending">조별예선은 지역예선 종료 후 표시됩니다.</p>
              </div>
              <div class="view-panel" id="{escape(name)}-knockout" hidden>
                {knockout_body}
              </div>
            </section>
            """
        rank_label = "조별리그 순위" if name.startswith("ACL") else "순위"
        controls = ""
        knockout_view = ""
        if name != "league":
            disabled_attr = "" if has_knockout else " disabled"
            controls = f"""
              <div class="view-toggle" role="group" aria-label="{escape(name)} 보기">
                <button class="toggle-btn active" type="button" data-target="{escape(name)}-rank">{rank_label}</button>
                <button class="toggle-btn" type="button" data-target="{escape(name)}-knockout"{disabled_attr}>토너먼트</button>
              </div>
            """
            knockout_body = render_knockout_table(knockout_rows) if has_knockout else ""
            knockout_view = f"""
              <div class="view-panel" id="{escape(name)}-knockout" hidden>
                {knockout_body}
              </div>
            """
        return f"""
            <section class="{section_class}">
              <h2>{escape(name)}</h2>
              {controls}
              <div class="view-panel" id="{escape(name)}-rank">
                {render_rank_table(name, rows)}
              </div>
              {knockout_view}
            </section>
            """

    sections: dict[str, str] = {}
    for name, rows in tables.items():
        if name.startswith("__knockout__") or not rows:
            continue
        sections[name] = render_section(name, rows)

    top_row = [sections[name] for name in ["league", "super_cup"] if name in sections]
    middle_row = [sections[name] for name in ["local_cup", "championship", "fa_cup"] if name in sections]
    bottom_row = [sections[name] for name in ["ACL1", "ACL2", "ACL3"] if name in sections]

    def wrap_row(items: list[str], class_name: str) -> str:
        if not items:
            return ""
        return f'<section class="row {class_name}">{"".join(items)}</section>'

    rows_html = "".join(
        item
        for item in [
            wrap_row(top_row, "top"),
            wrap_row(middle_row, "middle"),
            wrap_row(bottom_row, "bottom"),
            "".join(section for name, section in sections.items() if name not in {"league", "super_cup", "local_cup", "championship", "fa_cup", "ACL1", "ACL2", "ACL3"}),
        ]
        if item
    )

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{year} 대회 성적표</title>
  <style>
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      font-family: Arial, "Malgun Gothic", sans-serif;
      background: #f6f8fb;
      color: #172033;
    }}
    header {{
      padding: 20px 24px 12px;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
    }}
    .sub {{
      margin-top: 6px;
      color: #657083;
      font-size: 13px;
    }}
    main.grid {{
      padding: 0 16px 24px;
    }}
    .row {{
      display: grid;
      gap: 12px;
      align-items: start;
      margin-bottom: 12px;
    }}
    .row.top {{
      grid-template-columns: minmax(0, 2.2fr) minmax(280px, 1fr);
    }}
    .row.middle,
    .row.bottom {{
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }}
    @media (max-width: 1100px) {{
      .row.top,
      .row.middle,
      .row.bottom {{
        grid-template-columns: 1fr;
      }}
    }}
    .panel {{
      padding: 16px;
      background: #fff;
      border: 1px solid #d8dee8;
      border-radius: 8px;
      min-width: 0;
    }}
    .panel.wide {{
      grid-column: 1 / -1;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 16px;
      text-transform: none;
    }}
    .view-toggle {{
      display: inline-flex;
      gap: 4px;
      margin: 0 0 12px;
      padding: 3px;
      background: #eef3f9;
      border: 1px solid #d8dee8;
      border-radius: 7px;
    }}
    .toggle-btn {{
      border: 0;
      border-radius: 5px;
      padding: 6px 10px;
      background: transparent;
      color: #344054;
      font: inherit;
      font-size: 12px;
      cursor: pointer;
    }}
    .toggle-btn.active {{
      background: #172033;
      color: #fff;
    }}
    .toggle-btn:disabled {{
      color: #98a2b3;
      cursor: not-allowed;
    }}
    .view-panel {{
      overflow-x: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}
    th, td {{
      border: 1px solid #d8dee8;
      padding: 6px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: #eef3f9;
      white-space: nowrap;
    }}
  </style>
</head>
<body>
  <header>
    <h1>{year} 대회 성적표</h1>
    <div class="sub">리그와 각 컵대회의 누적 성적</div>
  </header>
  <main class="grid">
    {rows_html}
  </main>
  <script>
    document.querySelectorAll(".view-toggle").forEach((toggle) => {{
      const panel = toggle.closest(".panel");
      toggle.querySelectorAll(".toggle-btn").forEach((button) => {{
        button.addEventListener("click", () => {{
          if (button.disabled || !panel) {{
            return;
          }}
          toggle.querySelectorAll(".toggle-btn").forEach((item) => item.classList.remove("active"));
          button.classList.add("active");
          panel.querySelectorAll(".view-panel").forEach((view) => {{
            view.hidden = view.id !== button.dataset.target;
          }});
        }});
      }});
    }});
  </script>
  <script src="./spoiler_guard.js?v=cup-views-2" defer></script>
</body>
</html>"""
