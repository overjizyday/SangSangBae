$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$LogDir = Join-Path $ProjectRoot "logs"
$Python = "C:\Users\endy0\AppData\Local\Programs\Python\Python311\python.exe"

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

Set-Location $ProjectRoot

$env:PYTHONUNBUFFERED = "1"

& $Python "main.py" >> (Join-Path $LogDir "private_drive_app.log") 2>&1
