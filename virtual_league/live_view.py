from __future__ import annotations

import html
import json
import re
import signal
import threading
import time
import webbrowser
from collections import defaultdict
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterable

from .calendar_view import render_calendar_html, season_day_date
from .models import Match, Team
from .standings import calculate_standings

TICK_SECONDS = 2
VIRTUAL_DAY_MINUTES = 5

COMPETITION_ORDER = {
    "acl": 0,
    "local_cup": 1,
    "championship": 2,
    "fa_cup": 3,
    "super_cup": 4,
    "league": 5,
}

WEEKDAY_ORDER = {"월": 0, "화": 1, "수": 2, "목": 3, "금": 4, "토": 5, "일": 6}

ACTION_CODE_TO_LABEL = {
    12: "H1",
    13: "H1",
    14: "H2",
    15: "H2",
    16: "H2",
    17: "H3",
    18: "H3",
    19: "H3",
    21: "K",
    23: "K",
    24: "2B1",
    25: "K",
    26: "2B1",
    27: "K",
    28: "2B2",
    29: "K",
    31: "GO",
    32: "GO",
    34: "GO",
    35: "GO",
    36: "GO",
    37: "DO",
    38: "DO",
    39: "DO",
    41: "FO",
    42: "FO",
    43: "FO",
    45: "SF1",
    46: "SF1",
    47: "SF2",
    48: "SF2",
    49: "TO",
    51: "B",
    52: "B",
    53: "B",
    54: "HP",
    56: "SB",
    57: "SB",
    58: "SB",
    59: "SB",
    61: "H1",
    62: "H2",
    63: "H2",
    64: "H3",
    65: "H3",
    67: "2B1",
    68: "2B2",
    69: "HR",
    71: "K",
    72: "K",
    73: "K",
    74: "K",
    75: "K",
    76: "K",
    78: "K",
    79: "K",
    81: "FO",
    82: "FO",
    83: "FO",
    84: "SF1",
    85: "SF1",
    86: "SF2",
    87: "SF2",
    89: "HR",
    91: "GO",
    92: "GO",
    93: "GO",
    94: "GO",
    95: "DO",
    96: "DO",
    97: "E",
    98: "3B",
}


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_teams(season_dir: Path) -> list[Team]:
    path = season_dir / "teams.json"
    if not path.exists():
        return []
    data = _load_json(path)
    if not isinstance(data, list):
        return []
    teams: list[Team] = []
    for item in data:
        if isinstance(item, dict):
            teams.append(Team(**item))
    return teams


def _load_acl_team_names(season_dir: Path) -> dict[str, str]:
    path = season_dir / "acl.json"
    if not path.exists():
        return {}
    data = _load_json(path)
    if not isinstance(data, dict):
        return {}
    names: dict[str, str] = {}
    participants = data.get("participants", {})
    if isinstance(participants, dict):
        for league_rows in participants.values():
            if not isinstance(league_rows, list):
                continue
            for item in league_rows:
                if not isinstance(item, dict):
                    continue
                team_id = str(item.get("team_id", "")).strip()
                team_name = str(item.get("team_name", "")).strip()
                if team_id and team_name:
                    names[team_id] = team_name
    return names


def _load_competition_payload(season_dir: Path, filename: str) -> dict[str, object]:
    path = season_dir / filename
    if not path.exists():
        return {}
    data = _load_json(path)
    return data if isinstance(data, dict) else {}


def _load_matches(season_dir: Path) -> list[Match]:
    matches: list[Match] = []
    for filename in [
        "schedule.json",
        "local_cup.json",
        "championship.json",
        "fa_cup.json",
        "super_cup.json",
        "acl.json",
    ]:
        path = season_dir / filename
        if not path.exists():
            continue
        data = _load_json(path)
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("matches", [])
        else:
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            matches.append(
                Match(
                    id=str(item.get("id", "")),
                    competition=str(item.get("competition", "")),
                    stage=str(item.get("stage", "")),
                    round=item.get("round", ""),
                    week=int(item.get("week", 0)),
                    home_team_id=str(item.get("home_team_id", "")),
                    away_team_id=str(item.get("away_team_id", "")),
                    match_no=item.get("match_no"),
                    region=item.get("region"),
                    group=item.get("group"),
                    leg=item.get("leg"),
                    advantage_team_id=item.get("advantage_team_id"),
                    day=item.get("day"),
                    home_score=item.get("home_score"),
                    away_score=item.get("away_score"),
                    winner_team_id=item.get("winner_team_id"),
                    loser_team_id=item.get("loser_team_id"),
                )
            )
    return matches


def _load_live_feed(season_dir: Path) -> list[dict[str, object]]:
    path = season_dir / "live_feed.json"
    if path.exists():
        data = _load_json(path)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
    # Fallback for older seasons without live_feed.json.
    feeds = []
    for match in _load_matches(season_dir):
        feeds.append(
            {
                "match_id": match.id,
                "competition": match.competition,
                "stage": match.stage,
                "round": match.round,
                "week": match.week,
                "day": match.day,
                "home_team_id": match.home_team_id,
                "away_team_id": match.away_team_id,
                "home_score": match.home_score or 0,
                "away_score": match.away_score or 0,
                "events": [
                    {
                        "plate_appearance": 1,
                        "inning": 9,
                        "half": "bottom",
                        "event": "final",
                        "outs_before": 0,
                        "outs_after": 3,
                        "bases_before": "-",
                        "bases_after": "-",
                        "score_away_before": 0,
                        "score_home_before": 0,
                        "score_away_after": match.away_score or 0,
                        "score_home_after": match.home_score or 0,
                        "runs_scored": 0,
                        "half_over": True,
                    }
                ],
            }
        )
    return feeds


def _team_name_map(teams: Iterable[Team]) -> dict[str, str]:
    return {team.id: team.name for team in teams}


def _looks_like_code(name: str) -> bool:
    value = str(name).strip()
    return bool(re.fullmatch(r"[A-Za-z0-9_]+", value)) or "_FC" in value or value.startswith("T")


def _display_team_name(team_id: str, raw_name: str, team_names: dict[str, str]) -> str:
    if raw_name and raw_name != team_id and not _looks_like_code(raw_name):
        return raw_name
    return team_names.get(team_id, raw_name or team_id)


def _day_key(feed: dict[str, object]) -> tuple[int, str, int, str]:
    return (
        int(feed.get("week", 0)),
        str(feed.get("day") or ""),
        COMPETITION_ORDER.get(str(feed.get("competition", "")), 99),
        str(feed.get("match_id", "")),
    )


def _group_sort_key(group: tuple[tuple[int, str], list[dict[str, object]]]) -> tuple[int, int]:
    (week, day), _ = group
    return int(week), WEEKDAY_ORDER.get(day, 99)


def _season_date_label(season_year: int, week: int, day: str) -> str:
    if week <= 0:
        return f"{season_year} / Season complete"
    current = season_day_date(season_year, week, day)
    return f"{current.strftime('%Y-%m-%d')} | W{week} / {day}"


def _render_live_calendar_html(state: dict[str, object]) -> str:
    season_year = int(state.get("season_year") or 1970)
    season_dir = Path(str(state.get("season_dir", ".")))
    teams = state["teams"]
    team_names = _team_name_map(teams)
    team_names.update(state.get("acl_team_names", {}))

    progress_by_match = state["progress_by_match"]
    live_matches: list[Match] = []
    for feed in _load_live_feed(season_dir):
        match_id = str(feed.get("match_id", ""))
        events = feed.get("events", [])
        if not isinstance(events, list):
            events = []
        progress = int(progress_by_match.get(match_id, 0))
        done = progress >= len(events)
        live_matches.append(
            Match(
                id=match_id,
                competition=str(feed.get("competition", "")),
                stage=str(feed.get("stage", "")),
                round=feed.get("round", ""),
                week=int(feed.get("week", 0)),
                home_team_id=str(feed.get("home_team_id", "")),
                away_team_id=str(feed.get("away_team_id", "")),
                match_no=feed.get("match_no"),
                region=feed.get("region"),
                group=feed.get("group"),
                leg=feed.get("leg"),
                advantage_team_id=feed.get("advantage_team_id"),
                day=feed.get("day"),
                home_score=int(feed.get("home_score", 0)) if done else None,
                away_score=int(feed.get("away_score", 0)) if done else None,
                winner_team_id=feed.get("winner_team_id"),
                loser_team_id=feed.get("loser_team_id"),
            )
        )

    return render_calendar_html(season_year, live_matches, team_names, refresh_seconds=int(state["tick_seconds"]))


def _group_feed_by_day(feeds: list[dict[str, object]]) -> list[tuple[tuple[int, str], list[dict[str, object]]]]:
    grouped: dict[tuple[int, str], list[dict[str, object]]] = {}
    order: list[tuple[int, str]] = []
    for feed in sorted(feeds, key=_day_key):
        key = (int(feed.get("week", 0)), str(feed.get("day") or ""))
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(feed)
    return [(key, grouped[key]) for key in order]


def _match_progress(state: dict[str, object], match_id: str) -> int:
    progress = state["progress_by_match"]
    return int(progress.get(match_id, 0))


def _match_final_event(feed: dict[str, object]) -> dict[str, object] | None:
    events = feed.get("events", [])
    if not isinstance(events, list) or not events:
        return None
    return events[min(len(events), len(events)) - 1] if events else None


def _event_at(feed: dict[str, object], index: int) -> dict[str, object] | None:
    events = feed.get("events", [])
    if not isinstance(events, list):
        return None
    if index < 0 or index >= len(events):
        return None
    item = events[index]
    return item if isinstance(item, dict) else None


def _format_bases(value: str) -> str:
    return value if value and value != "-" else "empty"


def _bases_state(value: str) -> tuple[bool, bool, bool]:
    normalized = (value or "").strip().lower()
    if not normalized or normalized in {"-", "empty", "none"}:
        return False, False, False
    return (
        any(token in normalized for token in ("1", "first", "1b")),
        any(token in normalized for token in ("2", "second", "2b")),
        any(token in normalized for token in ("3", "third", "3b")),
    )


def _fallback_event_code(event_name: str) -> int | None:
    mapping = {
        "out": 21,
        "walk": 51,
        "single": 12,
        "double": 14,
        "triple": 17,
        "home_run": 69,
        "coinflip_run": 69,
    }
    return mapping.get(event_name)


def _current_snapshot(feed: dict[str, object], progress: int) -> dict[str, object]:
    events = feed.get("events", [])
    if not isinstance(events, list) or not events:
        return {
            "inning": 1,
            "half": "top",
            "outs": 0,
            "bases": "-",
            "last_event": "pregame",
            "plate_appearance": None,
            "event_code": None,
            "score_away": int(feed.get("away_score", 0)),
            "score_home": int(feed.get("home_score", 0)),
            "done": True,
        }

    if progress <= 0:
        first = events[0] if isinstance(events[0], dict) else {}
        return {
            "inning": int(first.get("inning", 1)),
            "half": str(first.get("half", "top")),
            "outs": 0,
            "bases": "empty",
            "last_event": "pregame",
            "plate_appearance": None,
            "event_code": None,
            "score_away": int(feed.get("away_score", 0)) if len(events) == 0 else int(first.get("score_away_before", 0)),
            "score_home": int(feed.get("home_score", 0)) if len(events) == 0 else int(first.get("score_home_before", 0)),
            "done": False,
        }

    last = events[min(progress, len(events)) - 1]
    if not isinstance(last, dict):
        last = {}
    done = progress >= len(events)

    if not done and int(last.get("outs_after", 0)) >= 3:
        inning = int(last.get("inning", 1))
        half = str(last.get("half", "top"))
        next_inning = inning + 1 if half == "bottom" else inning
        next_half = "top" if half == "bottom" else "bottom"
        return {
            "inning": next_inning,
            "half": next_half,
            "outs": 0,
            "bases": "empty",
            "last_event": str(last.get("event", "play")),
            "plate_appearance": int(last.get("plate_appearance", 0) or 0) if last.get("plate_appearance") is not None else None,
            "event_code": int(last.get("event_code", 0) or 0)
            if last.get("event_code") is not None
            else _fallback_event_code(str(last.get("event", ""))),
            "score_away": int(last.get("score_away_after", feed.get("away_score", 0))),
            "score_home": int(last.get("score_home_after", feed.get("home_score", 0))),
            "done": False,
        }

    return {
        "inning": int(last.get("inning", 1)),
        "half": str(last.get("half", "top")),
        "outs": int(last.get("outs_after", 0)),
        "bases": _format_bases(str(last.get("bases_after", "empty"))),
        "last_event": str(last.get("event", "play")),
        "plate_appearance": int(last.get("plate_appearance", 0) or 0) if last.get("plate_appearance") is not None else None,
        "event_code": int(last.get("event_code", 0) or 0)
        if last.get("event_code") is not None
        else _fallback_event_code(str(last.get("event", ""))),
        "score_away": int(last.get("score_away_after", feed.get("away_score", 0))),
        "score_home": int(last.get("score_home_after", feed.get("home_score", 0))),
        "done": done,
    }


def _completed_matches(groups: list[tuple[tuple[int, str], list[dict[str, object]]]], state: dict[str, object]) -> list[Match]:
    completed: list[Match] = []
    progress_by_match = state["progress_by_match"]
    for _, day_matches in groups:
        for feed in day_matches:
            match_id = str(feed.get("match_id", ""))
            progress = int(progress_by_match.get(match_id, 0))
            events = feed.get("events", [])
            if not isinstance(events, list) or progress < len(events):
                continue
            completed.append(
                Match(
                    id=match_id,
                    competition=str(feed.get("competition", "")),
                    stage=str(feed.get("stage", "")),
                    round=feed.get("round", ""),
                    week=int(feed.get("week", 0)),
                    home_team_id=str(feed.get("home_team_id", "")),
                    away_team_id=str(feed.get("away_team_id", "")),
                    day=str(feed.get("day") or None),
                    home_score=int(feed.get("home_score", 0)),
                    away_score=int(feed.get("away_score", 0)),
                )
            )
    return completed


def _remaining_ticks(groups: list[tuple[tuple[int, str], list[dict[str, object]]]], state: dict[str, object]) -> int:
    progress_by_match = state["progress_by_match"]
    current_group = int(state["group_index"])
    remaining = 0
    for group_index, (_, day_matches) in enumerate(groups):
        if group_index < current_group:
            continue
        remaining_in_day = 0
        for feed in day_matches:
            match_id = str(feed.get("match_id", ""))
            events = feed.get("events", [])
            if not isinstance(events, list):
                continue
            progress = int(progress_by_match.get(match_id, 0)) if group_index == current_group else 0
            remaining_in_day = max(remaining_in_day, max(len(events) - progress, 0))
        remaining += remaining_in_day
    return remaining


def _render_team_block(name: str, label: str = "") -> str:
    escaped_name = html.escape(name)
    escaped_label = html.escape(label.strip())
    rank_html = f'<div class="team-rank">{escaped_label}</div>' if escaped_label else ""
    return (
        '<div class="team-block">'
        f'  <div class="team-name">{escaped_name}</div>'
        f'  {rank_html}'
        "</div>"
    )


def _render_table(rows: list[dict[str, object]], team_names: dict[str, str], columns: list[tuple[str, str]], *, compact: bool = False) -> str:
    if not rows:
        return "<p class='empty'>No standings available.</p>"
    body = []
    for row in rows:
        cells = []
        for key, _ in columns:
            value = row.get(key, "")
            if key == "team_name":
                team_id = str(row.get("team_id", ""))
                value = _display_team_name(team_id, str(value or team_id), team_names)
            cells.append(f"<td>{html.escape(str(value))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    head = "".join(f"<th>{html.escape(label)}</th>" for _, label in columns)
    table_class = "compact" if compact else ""
    return f'<table class="{table_class}"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def _render_standings_from_rows(rows: list[dict[str, object]], team_names: dict[str, str], *, compact: bool = False) -> str:
    if compact:
        columns = [("rank", "#"), ("team_name", "Team"), ("played", "P"), ("wins", "W"), ("draws", "D"), ("losses", "L"), ("gf", "GF"), ("ga", "GA"), ("gd", "GD"), ("points", "Pts")]
    else:
        columns = [("rank", "#"), ("team_name", "Team"), ("played", "P"), ("wins", "W"), ("draws", "D"), ("losses", "L"), ("gf", "GF"), ("ga", "GA"), ("gd", "GD"), ("points", "Pts")]
    return _render_table(rows, team_names, columns, compact=compact)


def _detail_block(
    title: str,
    content: str,
    *,
    open: bool = False,
    class_name: str = "fold",
    key: str | None = None,
) -> str:
    open_attr = " open" if open else ""
    data_attr = f' data-fold-key="{html.escape(key)}"' if key else ""
    return f'<details class="{class_name}"{open_attr}{data_attr}><summary>{html.escape(title)}</summary>{content}</details>'


def _table_section(title: str, rows: list[dict[str, object]], team_names: dict[str, str], *, open: bool = False) -> str:
    return _detail_block(title, _render_standings_from_rows(rows, team_names), open=open, key=title)


def _render_diamond(bases: str) -> str:
    on1, on2, on3 = _bases_state(bases)
    return (
        '<div class="diamond">'
        f'<div class="base b2 {"on" if on2 else ""}"></div>'
        f'<div class="base b3 {"on" if on3 else ""}"></div>'
        f'<div class="base b1 {"on" if on1 else ""}"></div>'
        '<div class="base home"></div>'
        "</div>"
    )


def _format_last_play(snapshot: dict[str, object], *, debug: bool = False) -> str:
    last_event = str(snapshot.get("last_event", "play"))
    event_code = snapshot.get("event_code")
    if last_event == "pregame":
        return "pregame"
    if debug and event_code is not None:
        label = ACTION_CODE_TO_LABEL.get(int(event_code), last_event.upper())
        return f"{event_code} {label}"
    return last_event


def _render_match_card(
    feed: dict[str, object],
    snapshot: dict[str, object],
    team_names: dict[str, str],
    index: int,
    *,
    debug: bool = False,
) -> str:
    home = team_names.get(str(feed.get("home_team_id", "")), str(feed.get("home_team_id", "")))
    away = team_names.get(str(feed.get("away_team_id", "")), str(feed.get("away_team_id", "")))
    badge_class = "over" if snapshot["done"] else ("top" if str(snapshot["half"]) == "top" else "bot")
    badge_text = f'Inning {snapshot["inning"]} {str(snapshot["half"])}'
    score_away = html.escape(str(snapshot["score_away"]))
    score_home = html.escape(str(snapshot["score_home"]))
    outdots = "".join('<span class="outdot"></span>' for _ in range(min(int(snapshot["outs"]), 3)))
    last_play = html.escape(_format_last_play(snapshot, debug=debug))
    return (
        '<div class="card">'
        '<div class="header">'
        f'<div>Game {index + 1}</div>'
        f'<div class="badge {badge_class}">{badge_text}</div>'
        '</div>'
        '<div class="teams-row">'
        f'{_render_team_block(away)}'
        f'<div class="score-center"><span class="score-away">{score_away}</span><span class="score-sep">:</span><span class="score-home">{score_home}</span></div>'
        f'{_render_team_block(home)}'
        "</div>"
        '<div class="row"><div class="meta">Outs</div><div class="outs">'
        f"{outdots}"
        "</div></div>"
        f'{_render_diamond(str(snapshot["bases"]))}'
        f'<div class="lastact">Last play: {last_play}</div>'
        "</div>"
    )


def _team_subset_for_matches(teams: list[Team], matches: list[Match]) -> list[Team]:
    team_ids = {match.home_team_id for match in matches} | {match.away_team_id for match in matches}
    return [team for team in teams if team.id in team_ids]


def _standings_rows_for_matches(teams: list[Team], matches: list[Match]) -> list[dict[str, object]]:
    subset = _team_subset_for_matches(teams, matches)
    if not subset or not matches:
        return []
    standings = calculate_standings(subset, matches)
    return [
        {
            "rank": row.rank,
            "team_id": row.team_id,
            "team_name": row.team_name,
            "played": row.played,
            "wins": row.wins,
            "draws": row.draws,
            "losses": row.losses,
            "gf": row.goals_for,
            "ga": row.goals_against,
            "gd": row.goal_difference,
            "points": row.points,
        }
        for row in standings
    ]


def _render_standings_table(teams: list[Team], matches: list[Match], team_names: dict[str, str]) -> str:
    rows = _standings_rows_for_matches(teams, matches)
    return _render_standings_from_rows(rows, team_names) if rows else "<p class='empty'>No standings available.</p>"


def _match_filter(matches: list[Match], *, competition: str | None = None, stage: str | None = None) -> list[Match]:
    rows = matches
    if competition is not None:
        rows = [match for match in rows if match.competition == competition]
    if stage is not None:
        rows = [match for match in rows if str(match.stage) == stage]
    return rows


def _group_matches(matches: list[Match], key_fn) -> dict[str, list[Match]]:
    grouped: dict[str, list[Match]] = defaultdict(list)
    for match in matches:
        grouped[str(key_fn(match) or "")].append(match)
    return grouped


def _render_payload_standings(payload: dict[str, object], team_names: dict[str, str]) -> str:
    standings = payload.get("standings", [])
    rows = []
    if isinstance(standings, list):
        for item in standings:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "rank": int(item.get("rank", 0)),
                    "team_id": str(item.get("team_id", "")),
                    "team_name": str(item.get("team_name", item.get("team_id", ""))),
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
    return _render_standings_from_rows(rows, team_names, compact=True) if rows else "<p class='empty'>No standings available.</p>"


def _render_super_cup_live_standings(
    season_dir: Path,
    teams: list[Team],
    completed_matches: list[Match],
    team_names: dict[str, str],
) -> str:
    payload = _load_competition_payload(season_dir, "super_cup.json")
    entrants = payload.get("entrants", []) if isinstance(payload, dict) else []
    if not isinstance(entrants, list) or not entrants:
        return "<p class='empty'>No standings available.</p>"

    active_matches = [match for match in completed_matches if match.competition == "super_cup"]
    participant_ids = [str(row.get("team_id", "")) for row in entrants if isinstance(row, dict) and str(row.get("team_id", ""))]
    subset = [team for team in teams if team.id in set(participant_ids)]
    if not subset:
        return "<p class='empty'>No standings available.</p>"

    base_points = {
        str(row.get("team_id", "")): int(row.get("points", 0))
        for row in entrants
        if isinstance(row, dict) and str(row.get("team_id", ""))
    }
    names = {
        str(row.get("team_id", "")): str(row.get("team_name", row.get("team_id", "")))
        for row in entrants
        if isinstance(row, dict) and str(row.get("team_id", ""))
    }
    standings = calculate_standings(subset, active_matches)
    rows = []
    for row in standings:
        rows.append(
            {
                "rank": row.rank,
                "team_id": row.team_id,
                "team_name": names.get(row.team_id, team_names.get(row.team_id, row.team_name)),
                "played": row.played,
                "wins": row.wins,
                "draws": row.draws,
                "losses": row.losses,
                "gf": row.goals_for,
                "ga": row.goals_against,
                "gd": row.goal_difference,
                "points": row.points + base_points.get(row.team_id, 0),
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
    return _render_standings_from_rows(rows, team_names, compact=True) if rows else "<p class='empty'>No standings available.</p>"


def _render_local_cup_sections(matches: list[Match], teams: list[Team], team_names: dict[str, str], season_dir: Path) -> str:
    local_matches = _match_filter(matches, competition="local_cup")
    if not local_matches:
        return "<p class='empty'>No local cup data available.</p>"

    sections: list[str] = []
    qualifier_matches = [match for match in local_matches if str(match.stage) == "regional_qualifier"]
    if qualifier_matches:
        region_groups = _group_matches(qualifier_matches, key_fn=lambda match: match.region or "지역")
        region_parts = []
        for region in sorted(region_groups):
            region_matches = region_groups[region]
            rows = _standings_rows_for_matches(teams, region_matches)
            if rows:
                region_parts.append(
                    _detail_block(
                        region or "지역예선",
                        _render_standings_from_rows(rows, team_names),
                        open=True,
                        key=f"local-region-{region or 'default'}",
                    )
                )
        if region_parts:
            sections.append(_detail_block("지역예선", "".join(region_parts), open=True, key="local-region-root"))

    po_matches = [match for match in local_matches if str(match.stage) == "regional_po"]
    if po_matches:
        po_groups = _group_matches(po_matches, key_fn=lambda match: match.group or "PO")
        po_parts = []
        for group_name in sorted(po_groups):
            rows = _standings_rows_for_matches(teams, po_groups[group_name])
            if rows:
                po_parts.append(
                    _detail_block(
                        group_name or "PO",
                        _render_standings_from_rows(rows, team_names),
                        open=True,
                        key=f"local-po-{group_name or 'default'}",
                    )
                )
        if po_parts:
            sections.append(_detail_block("조별예선 / PO", "".join(po_parts), open=True, key="local-po-root"))

    if not sections and local_matches:
        payload = _load_competition_payload(season_dir, "local_cup.json")
        if payload:
            return _render_payload_standings(payload, team_names)
    return "".join(sections) if sections else "<p class='empty'>No local cup standings available.</p>"


def _render_acl_sections(matches: list[Match], teams: list[Team], team_names: dict[str, str], season_dir: Path) -> str:
    acl_matches = _match_filter(matches, competition="acl")
    if not acl_matches:
        return "<p class='empty'>No ACL data available.</p>"

    acl_payload = _load_competition_payload(season_dir, "acl.json")
    participants = acl_payload.get("participants", {}) if isinstance(acl_payload, dict) else {}
    if not isinstance(participants, dict):
        participants = {}

    sections: list[str] = []
    for league in ["ACL1", "ACL2", "ACL3"]:
        league_matches = [match for match in acl_matches if str(match.stage).startswith(f"{league}_")]
        group_matches = [match for match in league_matches if str(match.stage).endswith("_group")]
        if not group_matches:
            continue
        league_parts = []
        group_names = sorted({str(match.group) for match in group_matches if match.group})
        for group_name in group_names:
            group_rows = _standings_rows_for_matches(teams, [match for match in group_matches if str(match.group) == group_name])
            if not group_rows:
                continue
            league_parts.append(
                _detail_block(
                    group_name,
                    _render_standings_from_rows(group_rows, team_names, compact=True),
                    open=True,
                    key=f"acl-{league}-{group_name}",
                )
            )
        if league_parts:
            sections.append(_detail_block(league, "".join(league_parts), open=True, key=f"acl-{league}"))
    return "".join(sections) if sections else "<p class='empty'>No ACL standings available.</p>"


def _format_minutes(value: int) -> str:
    hours, minutes = divmod(value, 60)
    if hours:
        return f"{hours}h {minutes:02d}m"
    return f"{minutes}m"


def _format_seconds(value: int) -> str:
    if value <= 0:
        return "0s"
    minutes, seconds = divmod(value, 60)
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def render_live_dashboard(state: dict[str, object]) -> str:
    season_year = int(state.get("season_year") or 1970)
    season_dir = Path(str(state.get("season_dir", ".")))
    groups = state["groups"]
    teams = state["teams"]
    team_names = _team_name_map(teams)
    team_names.update(state.get("acl_team_names", {}))
    debug = bool(state.get("debug", False))
    group_index = int(state["group_index"])
    current_group = groups[group_index] if group_index < len(groups) else None
    tick_seconds = int(state["tick_seconds"])

    if current_group is None:
        current_key = (0, "")
        current_matches: list[dict[str, object]] = []
    else:
        current_key, current_matches = current_group

    completed = _completed_matches(groups, state)
    current_label = f"W{current_key[0]} / {current_key[1]}" if current_key[0] else "Season complete"
    season_date_label = _season_date_label(season_year, current_key[0], current_key[1])
    future_groups = sorted(groups[group_index + 1 :], key=_group_sort_key)
    upcoming = [f"W{week} / {day}" for (week, day), _ in future_groups[:6]]
    cards = []
    for feed in current_matches:
        match_id = str(feed.get("match_id", ""))
        snapshot = _current_snapshot(feed, _match_progress(state, match_id))
        cards.append(_render_match_card(feed, snapshot, team_names, len(cards), debug=debug))
    if not cards:
        cards_html = "<p class='empty'>No active matches.</p>"
    else:
        cards_html = f'<div class="board"><div class="grid">{"".join(cards)}</div></div>'
    upcoming_html = "".join(f"<li>{item}</li>" for item in upcoming) or "<li>Season complete.</li>"
    league_matches = _match_filter(completed, competition="league")
    league_rows = _standings_rows_for_matches(teams, league_matches)
    standings_sections = [
        f'<div class="standings-main"><h3 class="subsection-title">리그 순위</h3>{_render_standings_from_rows(league_rows, team_names)}</div>'
    ]

    super_cup_html = _render_super_cup_live_standings(season_dir, teams, completed, team_names)
    if super_cup_html:
        standings_sections.append(
            _detail_block("슈퍼컵", super_cup_html, open=False, key="standings-super_cup")
        )

    local_cup_inner = _render_local_cup_sections(completed, teams, team_names, season_dir)
    if local_cup_inner:
        standings_sections.append(_detail_block("로컬컵", local_cup_inner, open=True, key="standings-local_cup"))

    acl_inner = _render_acl_sections(completed, teams, team_names, season_dir)
    if acl_inner:
        standings_sections.append(_detail_block("ACL", acl_inner, open=True, key="standings-acl"))

    championship_matches = _match_filter(completed, competition="championship")
    if championship_matches:
        championship_rows = _standings_rows_for_matches(teams, championship_matches)
        if championship_rows:
            standings_sections.append(
                _detail_block(
                    "챔피언십",
                    _render_standings_from_rows(championship_rows, team_names),
                    open=False,
                    key="standings-championship-live",
                )
            )
    standings_html = "".join(standings_sections)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="{tick_seconds}">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{season_year} Live Replay</title>
  <style>
    :root {{
      --bg: #0b1020;
      --panel: #121a33;
      --panel-2: #182041;
      --text: #eef2ff;
      --muted: #9aa7c7;
      --accent: #70c6ff;
      --accent-2: #8bffb0;
      --line: rgba(255,255,255,.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(112,198,255,.18), transparent 30%),
        radial-gradient(circle at 80% 0%, rgba(139,255,176,.10), transparent 25%),
        var(--bg);
      color: var(--text);
    }}
    header {{ padding: 24px 28px 12px; }}
    h1 {{ margin: 0; font-size: 28px; }}
    .sub {{ margin-top: 6px; color: var(--muted); font-size: 13px; }}
    main {{
      display: grid;
      grid-template-columns: minmax(0, 1.7fr) minmax(320px, .9fr);
      gap: 18px;
      padding: 18px 28px 28px;
    }}
    .panel {{
      background: linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02));
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 18px 50px rgba(0,0,0,.25);
    }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }}
    .kpi {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
    }}
    .kpi .label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .08em;
    }}
    .kpi .value {{
      margin-top: 6px;
      font-size: 22px;
      font-weight: 700;
    }}
    .section-title {{
      margin: 0 0 12px;
      font-size: 18px;
    }}
    .subsection-title {{
      margin: 0 0 10px;
      font-size: 14px;
      color: var(--muted);
    }}
    .matches {{
      display: block;
    }}
    .board {{
      font-family: ui-sans-serif, system-ui, AppleSDGothicNeo, "Apple Color Emoji", "Segoe UI Emoji";
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
    }}
    .card {{
      border: 1px solid #e5e7eb;
      border-radius: 14px;
      padding: 12px;
      box-shadow: 0 1px 6px rgba(0,0,0,.06);
      background: #fff;
      color: #111827;
    }}
    .header {{
      font-size: 12px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 6px;
      font-weight: 700;
    }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      color: #777777;
      background: #e5e7eb;
    }}
    .top {{ background: #e0f2fe; }}
    .bot {{ background: #fee2e2; }}
    .over {{ background: #dcfce7; }}
    .teams-row {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
      align-items: center;
      gap: 8px;
      margin: 8px 0 10px;
    }}
    .team-block {{
      display: flex;
      flex-direction: column;
      justify-content: center;
    }}
    .teams-row .team-block:first-child {{
      text-align: left;
      align-items: flex-start;
    }}
    .teams-row .team-block:last-child {{
      text-align: right;
      align-items: flex-end;
    }}
    .team-name {{
      display: inline-flex;
      align-items: center;
      white-space: nowrap;
      line-height: 1.15;
      letter-spacing: 0;
      font-size: 16px;
      font-weight: 800;
      color: #111827;
    }}
    .team-rank {{
      font-size: 12px;
      line-height: 1.2;
      font-weight: 700;
      color: #374151;
      margin-top: 2px;
    }}
    .score-center {{
      font-size: 18px;
      font-weight: 800;
      color: #111827;
      white-space: nowrap;
      align-self: center;
    }}
    .score-away, .score-home, .score-sep {{
      vertical-align: middle;
    }}
    .score-away, .score-home {{
      display: inline-block;
      min-width: 18px;
      text-align: center;
    }}
    .row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 6px;
    }}
    .meta {{
      font-size: 13px;
      color: #374151;
      font-weight: 500;
    }}
    .outs {{
      font-size: 13px;
      color: #b91c1c;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 3px;
    }}
    .outdot {{
      display: inline-block;
      width: 8px;
      height: 8px;
      background: #ef4444;
      border-radius: 999px;
    }}
    .diamond {{
      width: 68px;
      height: 68px;
      position: relative;
      margin: 6px auto;
    }}
    .base {{
      width: 14px;
      height: 14px;
      transform: rotate(45deg);
      border: 1.5px solid #333;
      position: absolute;
      background: #fff;
    }}
    .base.on {{
      background: #10b981;
    }}
    .b1 {{ left: 42px; top: 42px; }}
    .b2 {{ left: 26px; top: 26px; }}
    .b3 {{ left: 10px; top: 42px; }}
    .home {{ left: 26px; top: 58px; border-color: #999; }}
    .lastact {{
      font-size: 12px;
      color: #777777;
      margin-top: 6px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    table.compact {{
      font-size: 12px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 6px;
      text-align: right;
    }}
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{ text-align: left; }}
    th {{ color: var(--muted); font-weight: 600; }}
    .empty, .aside li {{ color: var(--muted); }}
    ul {{ margin: 0; padding-left: 18px; }}
    details.fold {{
      margin-top: 10px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(255,255,255,.03);
    }}
    details.fold > summary {{
      cursor: pointer;
      list-style: none;
      font-weight: 700;
      color: var(--text);
    }}
    details.fold > summary::-webkit-details-marker {{
      display: none;
    }}
    .standings-main {{
      margin-bottom: 14px;
    }}
    @media (max-width: 960px) {{
      .lastact {{ display: none !important; }}
      .card {{
        position: relative;
        padding: 8px 48px 8px 8px;
        border-radius: 10px;
        min-height: 64px;
      }}
      .header {{
        position: relative;
        font-size: 10px;
        margin-bottom: 4px;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }}
      .header .badge {{
        position: relative;
        z-index: 2;
        font-size: 9px;
        padding: 1px 6px;
        max-width: 96px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        margin-left: 8px;
        margin-right: -32px;
      }}
      .team-name {{
        font-size: 12px;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }}
      .team-rank {{ font-size: 10px; margin-top: 1px; color: #4b5563; }}
      .teams-row {{
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        grid-auto-rows: auto;
        gap: 4px 8px;
        margin: 6px 0 8px;
      }}
      .teams-row .team-block:first-child {{
        grid-column: 1;
        grid-row: 1;
        align-items: flex-start;
        text-align: left;
      }}
      .teams-row .team-block:last-child {{
        grid-column: 1;
        grid-row: 2;
        align-items: flex-start;
        text-align: left;
      }}
      .score-center {{
        grid-column: 2;
        grid-row: 1 / span 2;
        font-size: 16px;
      }}
      .row {{
        margin-top: 4px;
      }}
      .meta, .outs {{
        font-size: 11px;
      }}
      .diamond {{
        width: 56px;
        height: 56px;
        margin: 4px auto;
      }}
      .base {{
        width: 11px;
        height: 11px;
      }}
      .b1 {{ left: 35px; top: 35px; }}
      .b2 {{ left: 21px; top: 21px; }}
      .b3 {{ left: 8px; top: 35px; }}
      .home {{ left: 21px; top: 47px; }}
    }}
    @media (max-width: 1000px) {{
      main {{ grid-template-columns: 1fr; }}
      .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{season_year} Live Replay</h1>
    <div class="sub">Virtual date: {season_date_label} | Current day: {current_label}</div>
  </header>
  <main>
    <section class="panel">
      <h2 class="section-title">Matches This Day</h2>
      <div class="matches">{cards_html}</div>
    </section>
    <aside class="panel aside">
      <h2 class="section-title">Standings</h2>
      {standings_html}
      <h2 class="section-title" style="margin-top:18px;">Upcoming</h2>
      <ul>{upcoming_html}</ul>
    </aside>
  </main>
  <script>
    (() => {{
      const storageKey = 'live-fold:{season_year}:' + location.pathname;
      const readState = () => {{
        try {{
          const raw = localStorage.getItem(storageKey);
          return raw ? new Set(JSON.parse(raw)) : new Set();
        }} catch (err) {{
          return new Set();
        }}
      }};
      const writeState = () => {{
        const openKeys = Array.from(document.querySelectorAll('details[data-fold-key][open]'))
          .map((el) => el.dataset.foldKey)
          .filter(Boolean);
        try {{
          localStorage.setItem(storageKey, JSON.stringify(openKeys));
        }} catch (err) {{}}
      }};
      const restoreState = () => {{
        const openKeys = readState();
        document.querySelectorAll('details[data-fold-key]').forEach((el) => {{
          const key = el.dataset.foldKey;
          if (key && openKeys.has(key)) {{
            el.open = true;
          }}
        }});
      }};
      document.addEventListener('DOMContentLoaded', () => {{
        restoreState();
        document.querySelectorAll('details[data-fold-key]').forEach((el) => {{
          el.addEventListener('toggle', writeState);
        }});
        writeState();
      }});
      window.addEventListener('pagehide', writeState);
    }})();
  </script>
</body>
</html>
"""


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _load_state_checkpoint(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _save_state_checkpoint(path: Path, state: dict[str, object]) -> None:
    payload = {
        "season_year": state.get("season_year"),
        "group_index": state.get("group_index"),
        "tick_count": state.get("tick_count"),
        "tick_seconds": state.get("tick_seconds"),
        "virtual_day_minutes": state.get("virtual_day_minutes"),
        "progress_by_match": state.get("progress_by_match"),
        "started_at": state.get("started_at").isoformat() if isinstance(state.get("started_at"), datetime) else None,
    }
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))


class _LiveServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], RequestHandlerClass, state: dict[str, object]):
        super().__init__(server_address, RequestHandlerClass)
        self.state = state
        self.daemon_threads = True


class _LiveHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        state = self.server.state  # type: ignore[attr-defined]
        if self.path in {"/", "/index.html"}:
            html = render_live_dashboard(state)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/state.json":
            payload = {
                "season_year": state["season_year"],
                "group_index": state["group_index"],
                "tick_count": state["tick_count"],
                "tick_seconds": state["tick_seconds"],
                "virtual_day_minutes": state["virtual_day_minutes"],
            }
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def _advance_live_state(state: dict[str, object]) -> tuple[bool, bool]:
    groups = state["groups"]
    group_index = int(state["group_index"])
    progress_by_match = state["progress_by_match"]
    if group_index >= len(groups):
        return False, False

    _, current_group = groups[group_index]
    if not current_group:
        state["group_index"] = group_index + 1
        return False, True

    all_done = True
    advanced = False
    for feed in current_group:
        match_id = str(feed.get("match_id", ""))
        events = feed.get("events", [])
        if not isinstance(events, list):
            continue
        current = int(progress_by_match.get(match_id, 0))
        if current < len(events):
            progress_by_match[match_id] = current + 1
            all_done = False
            advanced = True
    if all_done:
        state["group_index"] = group_index + 1
        return False, True
    return advanced, False


def replay_season(
    season_dir: Path | str,
    *,
    tick_seconds: int = TICK_SECONDS,
    virtual_day_minutes: int = VIRTUAL_DAY_MINUTES,
    debug: bool = False,
    open_browser: bool = False,
) -> Path:
    season_path = Path(season_dir)
    teams = _load_teams(season_path)
    feeds = _load_live_feed(season_path)
    groups = _group_feed_by_day(feeds)
    if not groups:
        raise ValueError(f"No matches available in {season_path}")

    checkpoint_path = season_path / "live_state.json"
    saved_state = _load_state_checkpoint(checkpoint_path)
    progress_by_match = {str(feed.get("match_id", "")): 0 for feed in feeds}
    if isinstance(saved_state, dict):
        saved_progress = saved_state.get("progress_by_match")
        if isinstance(saved_progress, dict):
            for match_id, progress in saved_progress.items():
                if match_id in progress_by_match:
                    try:
                        progress_by_match[match_id] = max(0, int(progress))
                    except (TypeError, ValueError):
                        continue
    state: dict[str, object] = {
                        "season_year": int(season_path.name) if season_path.name.isdigit() else 1970,
        "season_dir": season_path,
        "groups": groups,
        "group_index": 0,
        "progress_by_match": progress_by_match,
        "started_at": datetime.now(),
        "tick_seconds": tick_seconds,
        "virtual_day_minutes": virtual_day_minutes,
        "debug": debug,
        "tick_count": 0,
        "teams": teams,
        "acl_team_names": _load_acl_team_names(season_path),
    }
    if isinstance(saved_state, dict):
        try:
            state["group_index"] = min(int(saved_state.get("group_index", 0)), len(groups))
        except (TypeError, ValueError):
            state["group_index"] = 0
        try:
            state["tick_count"] = max(0, int(saved_state.get("tick_count", 0)))
        except (TypeError, ValueError):
            state["tick_count"] = 0
    lock = threading.Lock()
    stop_event = threading.Event()
    state["stop_event"] = stop_event

    server = _LiveServer(("127.0.0.1", 0), _LiveHandler, state)
    host, port = server.server_address
    url = f"http://{host}:{port}/"

    def _run_server() -> None:
        server.serve_forever(poll_interval=0.2)

    def _run_clock() -> None:
        while not stop_event.is_set():
            with lock:
                if stop_event.is_set():
                    break
                if int(state["group_index"]) >= len(groups):
                    break
                advanced, switched = _advance_live_state(state)
                if advanced:
                    state["tick_count"] = int(state["tick_count"]) + 1
                    _save_state_checkpoint(checkpoint_path, state)
                    _atomic_write(season_path / "calendar.html", _render_live_calendar_html(state))
            if stop_event.wait(tick_seconds):
                break

    server_thread = threading.Thread(target=_run_server, daemon=True)
    clock_thread = threading.Thread(target=_run_clock, daemon=True)
    server_thread.start()
    clock_thread.start()
    _atomic_write(season_path / "calendar.html", _render_live_calendar_html(state))

    previous_sigint = signal.getsignal(signal.SIGINT)

    def _handle_sigint(signum, frame) -> None:  # noqa: ANN001
        stop_event.set()
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _handle_sigint)

    if open_browser:
        webbrowser.open(url)

    try:
        while clock_thread.is_alive() and not stop_event.wait(0.2):
            continue
        final_html = render_live_dashboard(state)
        _atomic_write(season_path / "live_dashboard.html", final_html)
        _atomic_write(season_path / "calendar.html", _render_live_calendar_html(state))
        _save_state_checkpoint(checkpoint_path, state)
        return season_path / "live_dashboard.html"
    except KeyboardInterrupt:
        stop_event.set()
        raise
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        stop_event.set()
        server.shutdown()
        server.server_close()
        clock_thread.join(timeout=1.0)
        server_thread.join(timeout=1.0)
