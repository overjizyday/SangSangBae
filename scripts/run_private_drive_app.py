from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "private_drive_app.log"

    os.chdir(project_root)
    sys.path.insert(0, str(project_root))
    os.environ["PYTHONUNBUFFERED"] = "1"

    with log_file.open("a", encoding="utf-8", buffering=1) as stream:
        sys.stdout = stream
        sys.stderr = stream
        uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=False)


if __name__ == "__main__":
    main()
