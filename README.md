# SangSangBae

Static replay site and season generator for the SangSangBae virtual league.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Generate A Season

```powershell
python -m virtual_league.cli create-season --seasons-dir seasons
```

## Build The Static Site

```powershell
python -m virtual_league.cli build-pages --seasons-dir seasons --output docs
```

The generated `docs/` directory is designed to work on GitHub Pages as a static site.
Replay state is stored in JSON files:

- `replay_manifest.json`
- `replay_schedule.json`
- `replay_completion_order.json`
- `replay_ticks/replay_ticks_*.json`

## Local Server

```powershell
python main.py
```

Open:

- `http://127.0.0.1:8080/`
- `http://127.0.0.1:8080/sangsangbae/`

## Typical Workflow

```powershell
python -m virtual_league.cli create-season --seasons-dir seasons
python -m virtual_league.cli build-pages --seasons-dir seasons --output docs
python main.py
```
