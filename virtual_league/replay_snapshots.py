from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .models import Match, Team
from .standings import calculate_standings


TICK_SECONDS = 2
REST_SECONDS_AFTER_DAY = 60
TICKS_PER_CHUNK = 500
DAY_ORDER = ["월", "화", "수", "목", "금", "토", "일"]
WEEKDAY_ORDER = {day: index for index, day in enumerate(DAY_ORDER)}
COMPETITION_ORDER = {
    "acl": 0,
    "local_cup": 1,
    "championship": 2,
    "fa_cup": 3,
    "super_cup": 4,
    "league": 5,
}


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _load_teams(season_dir: Path) -> list[Team]:
    rows = _read_json(season_dir / "teams.json", [])
    if not isinstance(rows, list):
        return []
    teams: list[Team] = []
    for row in rows:
        if isinstance(row, dict):
            teams.append(
                Team(
                    id=str(row.get("id", "")),
                    name=str(row.get("name", row.get("id", ""))),
                    region=row.get("region"),
                    professional=bool(row.get("professional", True)),
                )
            )
    return [team for team in teams if team.id]


def _load_feeds(season_dir: Path) -> list[dict[str, Any]]:
    rows = _read_json(season_dir / "live_feed.json", [])
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _day_sort_key(feed: dict[str, Any]) -> tuple[int, int, int, str]:
    day = str(feed.get("day") or "")
    return (
        int(feed.get("week") or 0),
        WEEKDAY_ORDER.get(day, 99),
        COMPETITION_ORDER.get(str(feed.get("competition") or ""), 99),
        str(feed.get("match_id") or ""),
    )


def _group_feeds(feeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[int, str], dict[str, Any]] = {}
    order: list[tuple[int, str]] = []
    for feed in sorted(feeds, key=_day_sort_key):
        key = (int(feed.get("week") or 0), str(feed.get("day") or ""))
        if key not in groups:
            groups[key] = {"week": key[0], "day": key[1], "matches": []}
            order.append(key)
        groups[key]["matches"].append(feed)
    return [groups[key] for key in order]


def _event_count(feed: dict[str, Any]) -> int:
    events = feed.get("events", [])
    return len(events) if isinstance(events, list) else 0


def _group_duration(group: dict[str, Any]) -> int:
    return max([_event_count(feed) for feed in group["matches"]] or [0]) + 1


def _progress_by_match(groups: list[dict[str, Any]], tick: int) -> tuple[int, int, dict[str, int]]:
    progress = {
        str(feed.get("match_id") or ""): 0
        for group in groups
        for feed in group["matches"]
    }
    if tick <= 0:
        return -1, 0, progress

    remaining = tick
    group_index = len(groups)
    tick_in_group = 0
    for index, group in enumerate(groups):
        duration = _group_duration(group)
        if remaining < duration:
            group_index = index
            tick_in_group = remaining
            break
        for feed in group["matches"]:
            progress[str(feed.get("match_id") or "")] = _event_count(feed)
        remaining -= duration

    if group_index < len(groups):
        for feed in groups[group_index]["matches"]:
            match_id = str(feed.get("match_id") or "")
            progress[match_id] = min(tick_in_group, _event_count(feed))

    return group_index, tick_in_group, progress


def _fallback_event_code(event_name: str) -> int | None:
    return {
        "out": 21,
        "walk": 51,
        "single": 12,
        "double": 14,
        "triple": 17,
        "home_run": 69,
        "coinflip_run": 69,
    }.get(event_name)


def _snapshot_for_feed(feed: dict[str, Any], progress: int) -> dict[str, Any]:
    events = feed.get("events", [])
    events = events if isinstance(events, list) else []
    if not events:
        return {
            "inning": 1,
            "half": "top",
            "outs": 0,
            "bases": "empty",
            "last_event": "pregame",
            "plate_appearance": None,
            "event_code": None,
            "score_away": int(feed.get("away_score") or 0),
            "score_home": int(feed.get("home_score") or 0),
            "done": True,
        }
    if progress <= 0:
        first = events[0] if isinstance(events[0], dict) else {}
        return {
            "inning": int(first.get("inning") or 1),
            "half": str(first.get("half") or "top"),
            "outs": 0,
            "bases": "empty",
            "last_event": "pregame",
            "plate_appearance": None,
            "event_code": None,
            "score_away": int(first.get("score_away_before") or 0),
            "score_home": int(first.get("score_home_before") or 0),
            "done": False,
        }

    last = events[min(progress, len(events)) - 1]
    last = last if isinstance(last, dict) else {}
    done = progress >= len(events)
    if not done and int(last.get("outs_after") or 0) >= 3:
        inning = int(last.get("inning") or 1)
        half = str(last.get("half") or "top")
        return {
            "inning": inning + 1 if half == "bottom" else inning,
            "half": "top" if half == "bottom" else "bottom",
            "outs": 0,
            "bases": "empty",
            "last_event": str(last.get("event") or "play"),
            "plate_appearance": last.get("plate_appearance"),
            "event_code": last.get("event_code") or _fallback_event_code(str(last.get("event") or "")),
            "score_away": int(last.get("score_away_after") or 0),
            "score_home": int(last.get("score_home_after") or 0),
            "done": False,
        }
    return {
        "inning": int(last.get("inning") or 1),
        "half": str(last.get("half") or "top"),
        "outs": int(last.get("outs_after") or 0),
        "bases": str(last.get("bases_after") or "empty"),
        "last_event": str(last.get("event") or "play"),
        "plate_appearance": last.get("plate_appearance"),
        "event_code": last.get("event_code") or _fallback_event_code(str(last.get("event") or "")),
        "score_away": int(last.get("score_away_after") or 0),
        "score_home": int(last.get("score_home_after") or 0),
        "done": done,
    }


def _completed_matches(feeds: list[dict[str, Any]], progress: dict[str, int]) -> list[Match]:
    matches: list[Match] = []
    for feed in feeds:
        match_id = str(feed.get("match_id") or "")
        if progress.get(match_id, 0) < _event_count(feed):
            continue
        matches.append(
            Match(
                id=match_id,
                competition=str(feed.get("competition") or ""),
                stage=str(feed.get("stage") or ""),
                round=feed.get("round", ""),
                week=int(feed.get("week") or 0),
                day=str(feed.get("day") or ""),
                home_team_id=str(feed.get("home_team_id") or ""),
                away_team_id=str(feed.get("away_team_id") or ""),
                home_score=int(feed.get("home_score") or 0),
                away_score=int(feed.get("away_score") or 0),
            )
        )
    return matches


def _schedule_rows(feeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for feed in sorted(feeds, key=_day_sort_key):
        match_id = str(feed.get("match_id") or "")
        row = {
            "match_id": match_id,
            "competition": str(feed.get("competition") or ""),
            "stage": str(feed.get("stage") or ""),
            "round": feed.get("round"),
            "week": int(feed.get("week") or 0),
            "day": str(feed.get("day") or ""),
            "home_team_id": str(feed.get("home_team_id") or ""),
            "away_team_id": str(feed.get("away_team_id") or ""),
            "home_score": int(feed.get("home_score") or 0),
            "away_score": int(feed.get("away_score") or 0),
        }
        rows.append(row)
    return rows


def build_replay_ticks(
    season_dir: Path,
    *,
    replay_started_at: str | None = None,
    tick_seconds: int = TICK_SECONDS,
    rest_seconds_after_day: int = REST_SECONDS_AFTER_DAY,
) -> dict[str, Any]:
    teams = _load_teams(season_dir)
    feeds = _load_feeds(season_dir)
    groups = _group_feeds(feeds)
    total_ticks = sum(_group_duration(group) for group in groups)
    started_at = (
        datetime.fromisoformat(replay_started_at)
        if replay_started_at
        else datetime.now(UTC)
    )
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)

    ticks: list[dict[str, Any]] = []
    completion_order: list[str] = []
    completed_seen: set[str] = set()
    group_start_offsets: list[int] = []
    offset_seconds = 0
    for group_index, group in enumerate(groups):
        group_start_offsets.append(offset_seconds)
        offset_seconds += _group_duration(group) * tick_seconds
        if group_index < len(groups) - 1:
            offset_seconds += rest_seconds_after_day

    for tick in range(total_ticks + 1):
        group_index, tick_in_group, progress = _progress_by_match(groups, tick)
        current_group = groups[group_index] if 0 <= group_index < len(groups) else None
        if tick <= 0:
            run_offset_seconds = 0
        elif current_group is not None:
            run_offset_seconds = group_start_offsets[group_index] + tick_in_group * tick_seconds
        else:
            run_offset_seconds = offset_seconds
        completed = _completed_matches(feeds, progress)
        league_matches = [match for match in completed if match.competition == "league"]
        active_matches = []
        if current_group is not None:
            for feed in current_group["matches"]:
                match_id = str(feed.get("match_id") or "")
                active_matches.append(
                    {
                        "match_id": match_id,
                        "competition": str(feed.get("competition") or ""),
                        "stage": str(feed.get("stage") or ""),
                        "round": feed.get("round"),
                        "week": int(feed.get("week") or 0),
                        "day": str(feed.get("day") or ""),
                        "home_team_id": str(feed.get("home_team_id") or ""),
                        "away_team_id": str(feed.get("away_team_id") or ""),
                        "snapshot": _snapshot_for_feed(feed, progress.get(match_id, 0)),
                    }
                )

        completed_ids = [match.id for match in completed]
        for match_id in completed_ids:
            if match_id not in completed_seen:
                completed_seen.add(match_id)
                completion_order.append(match_id)
        ticks.append(
            {
                "tick": tick,
                "run_at": (started_at + timedelta(seconds=run_offset_seconds)).isoformat(),
                "group_index": group_index,
                "tick_in_group": tick_in_group,
                "week": current_group["week"] if current_group else None,
                "day": current_group["day"] if current_group else None,
                "active_matches": active_matches,
                "completed_count": len(completed_ids),
                "standings": {
                    "league": [asdict(row) for row in calculate_standings(teams, league_matches)]
                },
            }
        )

    return {
        "version": 1,
        "tick_seconds": tick_seconds,
        "rest_seconds_after_day": rest_seconds_after_day,
        "replay_started_at": started_at.isoformat(),
        "total_ticks": total_ticks,
        "total_duration_seconds": offset_seconds,
        "generated_at": datetime.now(UTC).isoformat(),
        "schedule": _schedule_rows(feeds),
        "completion_order": completion_order,
        "ticks": ticks,
    }


def write_replay_bundle(
    season_dir: Path,
    output_dir: Path,
    *,
    replay_started_at: str | None = None,
    tick_seconds: int = TICK_SECONDS,
    rest_seconds_after_day: int = REST_SECONDS_AFTER_DAY,
    ticks_per_chunk: int = TICKS_PER_CHUNK,
) -> Path:
    payload = build_replay_ticks(
        season_dir,
        replay_started_at=replay_started_at,
        tick_seconds=tick_seconds,
        rest_seconds_after_day=rest_seconds_after_day,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir = output_dir / "replay_ticks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    for stale_chunk in chunks_dir.glob("replay_ticks_*.json"):
        stale_chunk.unlink()

    ticks = payload.pop("ticks")
    schedule = payload.pop("schedule")
    completion_order = payload.pop("completion_order")
    chunks: list[dict[str, Any]] = []
    for index in range(0, len(ticks), ticks_per_chunk):
        chunk_ticks = ticks[index : index + ticks_per_chunk]
        chunk_no = index // ticks_per_chunk
        filename = f"replay_ticks_{chunk_no:03d}.json"
        chunk_path = chunks_dir / filename
        chunk_payload = {
            "chunk": chunk_no,
            "start_tick": chunk_ticks[0]["tick"] if chunk_ticks else 0,
            "end_tick": chunk_ticks[-1]["tick"] if chunk_ticks else 0,
            "ticks": chunk_ticks,
        }
        chunk_path.write_text(
            json.dumps(chunk_payload, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        chunks.append(
            {
                "chunk": chunk_no,
                "path": f"replay_ticks/{filename}",
                "start_tick": chunk_payload["start_tick"],
                "end_tick": chunk_payload["end_tick"],
                "start_run_at": chunk_ticks[0]["run_at"] if chunk_ticks else None,
                "end_run_at": chunk_ticks[-1]["run_at"] if chunk_ticks else None,
                "count": len(chunk_ticks),
            }
        )

    (output_dir / "replay_schedule.json").write_text(
        json.dumps(schedule, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    (output_dir / "replay_completion_order.json").write_text(
        json.dumps(completion_order, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    manifest = {
        **payload,
        "ticks_per_chunk": ticks_per_chunk,
        "chunks": chunks,
        "schedule_path": "replay_schedule.json",
        "completion_order_path": "replay_completion_order.json",
    }
    (output_dir / "replay_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    legacy_path = output_dir / "replay_ticks.json"
    if legacy_path.exists():
        legacy_path.unlink()
    return output_dir


def write_replay_ticks(
    season_dir: Path,
    output_path: Path,
    *,
    replay_started_at: str | None = None,
    tick_seconds: int = TICK_SECONDS,
    rest_seconds_after_day: int = REST_SECONDS_AFTER_DAY,
) -> Path:
    payload = build_replay_ticks(
        season_dir,
        replay_started_at=replay_started_at,
        tick_seconds=tick_seconds,
        rest_seconds_after_day=rest_seconds_after_day,
    )
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return output_path
