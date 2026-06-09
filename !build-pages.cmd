@echo off
setlocal
set "ROOT=%~dp0"
pushd "%ROOT%"

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$latest = Get-ChildItem -Directory seasons | Where-Object { $_.Name -match '^\d+$' } | Sort-Object { [int]$_.Name } | Select-Object -Last 1; if ($latest) { $latest.FullName } else { exit 1 }"`) do set "LATEST_SEASON=%%I"

if not defined LATEST_SEASON (
  echo No season folders found under seasons.
  popd
  pause
  exit /b 1
)

python -m virtual_league.cli build-pages --seasons-dir seasons --output docs --season-dir "%LATEST_SEASON%"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" goto :done

git add docs
git diff --cached --quiet
if "%ERRORLEVEL%"=="0" (
  echo No Pages changes to commit.
) else (
  git commit -m "Publish GitHub Pages"
  if not "%ERRORLEVEL%"=="0" goto :done
  git push
  set "EXIT_CODE=%ERRORLEVEL%"
)

:done
popd
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%
