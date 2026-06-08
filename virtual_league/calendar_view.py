from __future__ import annotations

from collections import defaultdict
from html import escape
import re
from datetime import date, timedelta
from pathlib import Path

from .acl import association_city_pool
from .models import Match, Team

DAY_ORDER = ["월", "화", "수", "목", "금", "토", "일"]
DAY_INDEX = {day: idx for idx, day in enumerate(DAY_ORDER)}
WEEK_ANCHOR_WEEK = 7
WEEK_ANCHOR_DAY_INDEX = DAY_INDEX["일"]
WEEK_ANCHOR_MONTH_DAY = (5, 5)
COMPETITION_LABELS = {
    "league": "리그",
    "local_cup": "로컬컵",
    "championship": "챔피언십",
    "fa_cup": "FA컵",
    "super_cup": "슈퍼컵",
    "acl": "ACL",
}


def _build_team_names(teams: list[Team], competitions: list[dict[str, object]]) -> dict[str, str]:
    team_names = {team.id: team.name for team in teams}
    for competition in competitions:
        participants = competition.get("participants")
        if not isinstance(participants, dict):
            continue
        for league_items in participants.values():
            for item in league_items:
                if isinstance(item, dict):
                    team_id = str(item.get("team_id", ""))
                    team_name = _display_name(
                        team_id,
                        str(item.get("team_name", team_id)),
                        str(item.get("country", "")),
                    )
                    if team_id:
                        team_names[team_id] = team_name
    return team_names


_TEAM_ID_RE = re.compile(r"^(?P<country>.+)_(?P<slot>[A-Z])_FC(?P<index>\d+)?$")


def _looks_like_code(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_]+", name)) or "_FC" in name or name.startswith("T")


def _display_name(team_id: str, team_name: str, country: str) -> str:
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


def write_calendar_html(
    path: Path,
    year: int,
    teams: list[Team],
    league_matches: list[Match],
    competitions: list[dict[str, object]],
) -> None:
    matches = collect_matches(league_matches, competitions)
    team_names = _build_team_names(teams, competitions)
    path.write_text(render_calendar_html(year, matches, team_names), encoding="utf-8")


def collect_matches(league_matches: list[Match], competitions: list[dict[str, object]]) -> list[Match]:
    matches = list(league_matches)
    for competition in competitions:
        if competition.get("held"):
            matches.extend(item for item in competition.get("matches", []) if isinstance(item, Match))
    return matches


def season_day_date(year: int, week: int, day: str) -> date:
    anchor = date(year, *WEEK_ANCHOR_MONTH_DAY)
    day_index = DAY_INDEX.get(day, 0)
    delta_days = (week - WEEK_ANCHOR_WEEK) * 7 + (day_index - WEEK_ANCHOR_DAY_INDEX)
    return anchor + timedelta(days=delta_days)


def season_week_label(year: int, week: int) -> str:
    start = season_day_date(year, week, "월")
    end = season_day_date(year, week, "일")
    return f"{week}주차 ({start.month}/{start.day} - {end.month}/{end.day})"


def render_calendar_html(
    year: int,
    matches: list[Match],
    team_names: dict[str, str],
    *,
    refresh_seconds: int | None = None,
) -> str:
    by_week_day: dict[int, dict[str, list[Match]]] = defaultdict(lambda: defaultdict(list))
    for match in matches:
        if match.day is None:
            continue
        by_week_day[match.week][match.day].append(match)

    rows = []
    for week in sorted(by_week_day):
        week_label = season_week_label(year, week)
        cells = []
        for day in DAY_ORDER:
            day_matches = sorted(
                by_week_day[week].get(day, []),
                key=lambda match: (competition_order(match.competition), str(match.round), match.id),
            )
            cells.append(f"<td>{render_day_matches(day_matches, team_names)}</td>")
        rows.append(f"<tr><th>{week_label}</th>{''.join(cells)}</tr>")

    refresh_tag = f'<meta http-equiv="refresh" content="{refresh_seconds}">' if refresh_seconds else ""
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  {refresh_tag}
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{year} 시즌 캘린더</title>
  <style>
    :root {{
      color-scheme: light;
      --line: #d8dee8;
      --text: #172033;
      --muted: #657083;
      --bg: #f6f8fb;
      --panel: #ffffff;
      --league: #2f6fed;
      --local: #138a63;
      --championship: #7c4dff;
      --fa: #c25a14;
      --super: #b32664;
      --acl: #075985;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, "Malgun Gothic", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      padding: 20px 24px 12px;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      letter-spacing: 0;
    }}
    .sub {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
    }}
    main {{
      padding: 0 16px 24px;
      overflow-x: auto;
    }}
    table {{
      width: 100%;
      min-width: 1120px;
      border-collapse: separate;
      border-spacing: 0;
      background: var(--panel);
      border: 1px solid var(--line);
    }}
    th, td {{
      border-right: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    thead th {{
      position: sticky;
      top: 0;
      z-index: 2;
      background: #eef3f9;
      padding: 10px;
      font-size: 13px;
      text-align: center;
    }}
    tbody th {{
      width: 132px;
      padding: 10px 8px;
      background: #f2f5fa;
      font-size: 13px;
      white-space: nowrap;
      line-height: 1.35;
    }}
    td {{
      width: 14.2%;
      min-height: 120px;
      padding: 6px;
    }}
    .match {{
      border-left: 4px solid var(--league);
      background: #fff;
      border-radius: 6px;
      padding: 7px 8px;
      margin-bottom: 6px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, .08);
      font-size: 12px;
      line-height: 1.35;
    }}
    .local_cup {{ border-left-color: var(--local); }}
    .championship {{ border-left-color: var(--championship); }}
    .fa_cup {{ border-left-color: var(--fa); }}
    .super_cup {{ border-left-color: var(--super); }}
    .acl {{ border-left-color: var(--acl); }}
    .meta {{
      color: var(--muted);
      font-size: 11px;
      margin-bottom: 4px;
    }}
    .teams {{
      font-weight: 700;
      word-break: keep-all;
      overflow-wrap: anywhere;
    }}
    .score {{
      color: var(--muted);
      margin-top: 3px;
    }}
    details.fold {{
      margin-bottom: 6px;
    }}
    details.fold > summary {{
      list-style: none;
      cursor: pointer;
      font-size: 11px;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    details.fold > summary::-webkit-details-marker {{
      display: none;
    }}
  </style>
</head>
<body>
  <header>
    <h1>{year} 시즌 캘린더</h1>
    <div class="sub">주차별, 요일별 전체 경기 일정</div>
  </header>
  <main>
    <table>
      <thead>
        <tr><th>주차</th>{''.join(f'<th>{day}</th>' for day in DAY_ORDER)}</tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </main>
  <script src="./spoiler_guard.js?v=sync-clock-11" defer></script>
</body>
</html>
"""


def _pretty_stage(match: Match) -> str:
    stage = str(match.stage)
    if stage == "final_round":
        return "40"
    if stage.startswith("ACL") and "_" in stage:
        league, phase = stage.split("_", 1)
        labels = {
            "group": "조별",
            "po": "PO",
            "qf": "8강",
            "sf": "4강",
            "final": "결승",
        }
        return f"{league} {labels.get(phase, phase.upper())}"
    return stage


def render_match(match: Match, team_names: dict[str, str]) -> str:
    label = COMPETITION_LABELS.get(match.competition, match.competition)
    home = escape(team_names.get(match.home_team_id, match.home_team_id))
    away = escape(team_names.get(match.away_team_id, match.away_team_id))
    round_label = escape(str(match.round))
    stage = escape(_pretty_stage(match))
    score = ""
    if match.home_score is not None and match.away_score is not None:
        score = f'<div class="score">{match.away_score} - {match.home_score}</div>'
    return (
        f'<div class="match {escape(match.competition)}" data-match-id="{escape(match.id)}">'
        f'<div class="meta">{escape(label)} · {round_label} · {stage}</div>'
        f'<div class="teams">{away} vs {home}</div>'
        f"{score}</div>"
    )


def render_day_matches(day_matches: list[Match], team_names: dict[str, str]) -> str:
    grouped: dict[str, list[Match]] = defaultdict(list)
    for match in day_matches:
        grouped[match.competition].append(match)

    parts = []
    for competition in sorted(grouped, key=competition_order):
        comp_matches = grouped[competition]
        rendered = "".join(render_match(match, team_names) for match in comp_matches)
        if len(comp_matches) >= 4:
            label = COMPETITION_LABELS.get(competition, competition)
            parts.append(
                f'<details class="fold"><summary>{escape(label)} {len(comp_matches)}경기</summary>{rendered}</details>'
            )
        else:
            parts.append(rendered)
    return "".join(parts)


def competition_order(competition: str) -> int:
    order = {
        "acl": 0,
        "local_cup": 1,
        "championship": 2,
        "fa_cup": 3,
        "super_cup": 4,
        "league": 5,
    }
    return order.get(competition, 99)
