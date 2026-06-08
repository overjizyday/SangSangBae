from __future__ import annotations

import argparse
from pathlib import Path

from .live_view import replay_season
from .pages_site import write_pages_site
from .season import create_season
from .team_registry import VALID_REGIONS, add_team, ensure_team_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Virtual league season generator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-season", help="Generate the next season")
    create.add_argument("--seasons-dir", default="seasons", help="Root directory for season outputs")
    create.add_argument("--teams-file", default=None, help="Editable team registry JSON")
    create.add_argument("--seed", type=int, default=None, help="Random seed")
    create.add_argument("--live", action="store_true", help="Replay the generated season graphically")
    create.add_argument("--tick-seconds", type=int, default=2, help="Replay tick interval in seconds")
    create.add_argument("--virtual-day-minutes", type=int, default=5, help="Virtual minutes advanced per day")
    create.add_argument("--debug", action="store_true", help="Show replay debug labels in the live dashboard")
    create.add_argument("--open-browser", action="store_true", help="Open the replay dashboard in a browser")

    init_teams = subparsers.add_parser("init-teams", help="Create or validate teams.json")
    init_teams.add_argument("--teams-file", default="teams.json", help="Editable team registry JSON")

    add = subparsers.add_parser("add-team", help="Add a team to teams.json")
    add.add_argument("name", help="Team name")
    add.add_argument("--region", required=True, choices=VALID_REGIONS, help="Team region")
    add.add_argument("--id", default=None, help="Optional team id")
    add.add_argument("--amateur", action="store_true", help="Mark the team as amateur")
    add.add_argument("--teams-file", default="teams.json", help="Editable team registry JSON")

    replay = subparsers.add_parser("replay-season", help="Replay an existing season graphically")
    replay.add_argument("season_dir", nargs="?", default="seasons/1970", help="Season directory")
    replay.add_argument("--tick-seconds", type=int, default=2, help="Replay tick interval in seconds")
    replay.add_argument("--virtual-day-minutes", type=int, default=5, help="Virtual minutes advanced per day")
    replay.add_argument("--debug", action="store_true", help="Show replay debug labels in the live dashboard")
    replay.add_argument("--open-browser", action="store_true", help="Open the replay dashboard in a browser")

    pages = subparsers.add_parser("build-pages", help="Build a static GitHub Pages site for the latest season")
    pages.add_argument("--seasons-dir", default="seasons", help="Root directory containing season folders")
    pages.add_argument("--output", default="docs", help="Output directory for the static site")
    pages.add_argument("--season-dir", default=None, help="Optional season directory to publish instead of latest")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "create-season":
        season_dir = create_season(Path(args.seasons_dir), seed=args.seed, teams_file=args.teams_file)
        print(f"Season generated: {season_dir}")
        if args.live:
            dashboard = replay_season(
                season_dir,
                tick_seconds=args.tick_seconds,
                virtual_day_minutes=args.virtual_day_minutes,
                debug=args.debug,
                open_browser=args.open_browser,
            )
            print(f"Live replay written: {dashboard}")
        return 0

    if args.command == "init-teams":
        teams = ensure_team_file(Path(args.teams_file))
        print(f"Teams registry ready: {args.teams_file} ({len(teams)} teams)")
        return 0

    if args.command == "add-team":
        team = add_team(
            Path(args.teams_file),
            name=args.name,
            region=args.region,
            professional=not args.amateur,
            team_id=args.id,
        )
        print(f"Team added: {team.id} {team.name} ({team.region})")
        return 0

    if args.command == "replay-season":
        dashboard = replay_season(
            Path(args.season_dir),
            tick_seconds=args.tick_seconds,
            virtual_day_minutes=args.virtual_day_minutes,
            debug=args.debug,
            open_browser=args.open_browser,
        )
        print(f"Live replay written: {dashboard}")
        return 0

    if args.command == "build-pages":
        seasons_root = Path(args.seasons_dir)
        season_dir = Path(args.season_dir) if args.season_dir else None
        output_dir = Path(args.output)
        pages_dir = write_pages_site(seasons_root, output_dir, season_dir=season_dir)
        print(f"Static Pages site written: {pages_dir}")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
