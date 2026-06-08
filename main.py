from __future__ import annotations

import os
import re
from datetime import UTC, datetime
from functools import lru_cache
from html import escape
from typing import Any

import google.auth
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from google.api_core.exceptions import GoogleAPIError
from google.auth.exceptions import DefaultCredentialsError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaInMemoryUpload
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local convenience
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

APP_STARTED_AT = datetime.now(UTC).isoformat()

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
DEFAULT_FILE_PREFIX = "note"
DEFAULT_FILE_LIMIT = 10
MAX_FILE_LIMIT = 50
GENERIC_DRIVE_ERROR = "Google Drive request failed."

app = FastAPI(title="Private Drive File App")
app.mount("/sangsangbae", StaticFiles(directory="docs", html=True), name="sangsangbae")


class CreateFileRequest(BaseModel):
    content: str = Field(default="", description="Text content to write into the Drive file")
    filename: str | None = Field(
        default=None,
        description="Optional file name. Defaults to note-YYYYMMDD-HHMMSS.txt",
    )


def get_drive_folder_id() -> str:
    folder_id = os.getenv("DRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        raise HTTPException(status_code=500, detail="Drive folder is not configured.")
    return folder_id


def raise_drive_http_error(detail: str, exc: Exception) -> None:
    # Keep runtime errors generic so credentials, folder IDs, and other secrets are not leaked.
    raise HTTPException(status_code=502, detail=detail) from exc


@lru_cache(maxsize=1)
def get_drive_service() -> Any:
    try:
        credentials, _ = google.auth.default(scopes=[DRIVE_SCOPE])
    except DefaultCredentialsError as exc:
        raise HTTPException(
            status_code=500,
            detail="Google Application Default Credentials are not available.",
        ) from exc

    try:
        return build("drive", "v3", credentials=credentials, cache_discovery=False)
    except Exception as exc:  # pragma: no cover - defensive wrapper
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize the Google Drive client.",
        ) from exc


def generate_default_filename() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"{DEFAULT_FILE_PREFIX}-{timestamp}.txt"


def sanitize_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename.strip())
    cleaned = cleaned.strip("._-")
    return cleaned


def normalize_filename(filename: str | None) -> str:
    if not filename:
        return generate_default_filename()

    cleaned = sanitize_filename(filename)
    if not cleaned:
        return generate_default_filename()

    if not cleaned.lower().endswith(".txt"):
        cleaned = f"{cleaned}.txt"

    return cleaned


def create_drive_text_file(filename: str, content: str) -> dict[str, Any]:
    folder_id = get_drive_folder_id()
    drive_service = get_drive_service()

    media = MediaInMemoryUpload(content.encode("utf-8"), mimetype="text/plain", resumable=False)
    metadata = {
        "name": filename,
        "mimeType": "text/plain",
        "parents": [folder_id],
    }

    try:
        created = (
            drive_service.files()
            .create(
                body=metadata,
                media_body=media,
                fields="id, name, mimeType, parents, webViewLink, createdTime, modifiedTime",
            )
            .execute()
        )
    except HttpError as exc:
        raise_drive_http_error("Google Drive file creation failed.", exc)
    except GoogleAPIError as exc:
        raise_drive_http_error(GENERIC_DRIVE_ERROR, exc)

    return created


def list_drive_files(limit: int) -> list[dict[str, Any]]:
    folder_id = get_drive_folder_id()
    drive_service = get_drive_service()

    try:
        response = (
            drive_service.files()
            .list(
                q=f"'{folder_id}' in parents and trashed=false",
                orderBy="modifiedTime desc",
                pageSize=limit,
                fields="files(id, name, mimeType, createdTime, modifiedTime, webViewLink, size)",
                includeItemsFromAllDrives=False,
                supportsAllDrives=False,
            )
            .execute()
        )
    except HttpError as exc:
        raise_drive_http_error("Google Drive file listing failed.", exc)
    except GoogleAPIError as exc:
        raise_drive_http_error(GENERIC_DRIVE_ERROR, exc)

    return response.get("files", [])


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    drive_status = "configured" if os.getenv("DRIVE_FOLDER_ID") else "not configured"
    now = datetime.now(UTC).isoformat()
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Private Drive File App</title>
    <style>
      body {{
        font-family: Arial, sans-serif;
        max-width: 720px;
        margin: 48px auto;
        padding: 0 20px;
        line-height: 1.6;
      }}
      code {{
        background: #f4f4f4;
        padding: 2px 6px;
        border-radius: 4px;
      }}
    </style>
  </head>
  <body>
    <h1>Private Drive File App</h1>
    <p>Status: running</p>
    <p>Drive folder: {escape(drive_status)}</p>
    <p>Time (UTC): {escape(now)}</p>
    <ul>
      <li><a href="/health">/health</a></li>
      <li><a href="/sangsangbae/">/sangsangbae</a></li>
      <li>POST <code>/create-file</code></li>
      <li><a href="/files">/files</a></li>
    </ul>
  </body>
</html>"""


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/replay-state")
def replay_state() -> dict[str, str]:
    return {"replay_started_at": APP_STARTED_AT}


@app.post("/create-file")
def create_file(payload: CreateFileRequest) -> dict[str, Any]:
    filename = normalize_filename(payload.filename)
    created = create_drive_text_file(filename=filename, content=payload.content)
    return {"message": "file created", "file": created}


@app.get("/files")
def files(limit: int = Query(default=DEFAULT_FILE_LIMIT, ge=1, le=MAX_FILE_LIMIT)) -> dict[str, Any]:
    items = list_drive_files(limit=limit)
    return {"count": len(items), "files": items}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
