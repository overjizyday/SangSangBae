from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .replay_snapshots import write_replay_bundle


DATA_FILES = [
    "season.json",
    "teams.json",
    "schedule.json",
    "standings.json",
    "results.csv",
    "live_feed.json",
    "standings.csv",
    "standings.html",
    "calendar.html",
    "acl.json",
    "acl_participants.html",
    "local_cup.json",
    "championship.json",
    "fa_cup.json",
    "super_cup.json",
]


def _latest_season_dir(seasons_root: Path) -> Path:
    season_dirs = [path for path in seasons_root.iterdir() if path.is_dir() and path.name.isdigit()]
    if not season_dirs:
        raise FileNotFoundError(f"No season directories found in {seasons_root}")
    return max(season_dirs, key=lambda path: int(path.name))


def _copy_if_exists(source: Path, destination: Path) -> None:
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _stamp_replay_start(season_path: Path) -> str | None:
    if not season_path.exists():
        return None
    try:
        payload = json.loads(season_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    replay_started_at = datetime.now(UTC).isoformat()
    payload["replay_started_at"] = replay_started_at
    season_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return replay_started_at


def _ensure_spoiler_guard(page: Path) -> None:
    if not page.exists():
        return
    html = page.read_text(encoding="utf-8")
    script = '<script src="./spoiler_guard.js?v=cup-views-3" defer></script>'
    if "spoiler_guard.js" in html:
        html = re.sub(r'<script src="\./spoiler_guard\.js\?v=[^"]+" defer></script>', script, html)
        page.write_text(html, encoding="utf-8")
        return
    html = html.replace("</body>", f"  {script}\n</body>")
    page.write_text(html, encoding="utf-8")


def _strip_calendar_scores(page: Path) -> None:
    if not page.exists():
        return
    html = page.read_text(encoding="utf-8")
    html = re.sub(r'<div class="score">.*?</div>', '<div class="score">예정</div>', html)
    html = re.sub(r'<div class="match ', '<div hidden class="match ', html)
    html = re.sub(r'<details class="fold"', '<details hidden class="fold"', html)
    page.write_text(html, encoding="utf-8")


def _strip_standings_tables(page: Path) -> None:
    if not page.exists():
        return
    html = page.read_text(encoding="utf-8")
    html = re.sub(
        r"<tbody>.*?</tbody>",
        '<tbody><tr><td colspan="10">진행 상황 불러오는 중</td></tr></tbody>',
        html,
        flags=re.DOTALL,
    )
    page.write_text(html, encoding="utf-8")


def _strip_standings_script(page: Path) -> None:
    if not page.exists():
        return
    html = page.read_text(encoding="utf-8")
    html = re.sub(r'\s*<script src="\./spoiler_guard\.js\?v=[^"]+" defer></script>', "", html)
    page.write_text(html, encoding="utf-8")


def _build_index_html(season_year: int) -> str:
    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{season_year} Season Replay</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0b1020;
      --panel: #121a33;
      --panel-2: #182041;
      --text: #eef2ff;
      --muted: #9aa7c7;
      --accent: #70c6ff;
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
    .shell {{
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}
    header {{
      padding: 18px 20px 12px;
      display: flex;
      gap: 12px;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
    }}
    .sub {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 4px;
    }}
    .controls {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    button, a.link {{
      appearance: none;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255,255,255,.04);
      color: var(--text);
      padding: 8px 12px;
      text-decoration: none;
      font: inherit;
      cursor: pointer;
    }}
    main {{
      flex: 1;
      display: grid;
      grid-template-columns: minmax(0, 1.7fr) minmax(320px, .9fr);
      gap: 18px;
      padding: 0 20px 20px;
    }}
    .panel {{
      background: linear-gradient(180deg, rgba(255,255,255,.04), rgba(255,255,255,.02));
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 18px 50px rgba(0,0,0,.25);
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
    .empty, .aside li {{
      color: var(--muted);
    }}
    ul {{
      margin: 0;
      padding-left: 18px;
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
      color: #777;
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
      color: #777;
      margin-top: 6px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    table.compact {{
      font-size: 12px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px 6px;
      text-align: right;
    }}
    th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{
      text-align: left;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
    }}
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
    @media (max-width: 1000px) {{
      main {{
        grid-template-columns: 1fr;
      }}
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
        font-size: 10px;
        margin-bottom: 4px;
      }}
      .header .badge {{
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
      }}
      .team-rank {{
        font-size: 10px;
        margin-top: 1px;
        color: #4b5563;
      }}
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
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div>
        <h1>{season_year} Season Replay</h1>
        <div class="sub" id="subtitle">Loading replay data...</div>
      </div>
      <div class="controls">
        <button id="togglePlay">Pause</button>
        <button id="resetReplay">Reset</button>
        <a class="link" href="./calendar.html">Calendar</a>
        <a class="link" href="./standings.html">Standings</a>
      </div>
    </header>
    <main id="app">
      <section class="panel">
        <h2 class="section-title">Loading...</h2>
      </section>
    </main>
  </div>
  <script src="./app.js?v=tick-chunks-3" defer></script>
</body>
</html>
"""


def write_pages_site(seasons_root: Path, output_dir: Path, season_dir: Path | None = None) -> Path:
    seasons_root = Path(seasons_root)
    output_dir = Path(output_dir)
    season_dir = Path(season_dir) if season_dir is not None else _latest_season_dir(seasons_root)
    if not season_dir.exists():
        raise FileNotFoundError(f"Season directory not found: {season_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")

    for filename in DATA_FILES:
        _copy_if_exists(season_dir / filename, output_dir / filename)
    replay_started_at = _stamp_replay_start(output_dir / "season.json")
    write_replay_bundle(output_dir, output_dir, replay_started_at=replay_started_at)

    source_app = Path(__file__).resolve().parent / "pages_app.js"
    _copy_if_exists(source_app, output_dir / "app.js")
    source_spoiler_guard = Path(__file__).resolve().parent / "spoiler_guard.js"
    _copy_if_exists(source_spoiler_guard, output_dir / "spoiler_guard.js")
    _ensure_spoiler_guard(output_dir / "calendar.html")
    _strip_calendar_scores(output_dir / "calendar.html")
    _strip_standings_script(output_dir / "standings.html")

    season_json_path = season_dir / "season.json"
    season_year = int(season_dir.name) if season_dir.name.isdigit() else 0
    if season_json_path.exists():
        try:
            season_payload = json.loads(season_json_path.read_text(encoding="utf-8"))
            season_year = int(season_payload.get("year", season_year))
        except Exception:
            pass

    (output_dir / "index.html").write_text(_build_index_html(season_year), encoding="utf-8")
    return output_dir
