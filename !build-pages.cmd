@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
pushd "%ROOT%"

echo [1/5] Locating latest season...
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$latest = Get-ChildItem -Directory seasons | Where-Object { $_.Name -match '^\d+$' } | Sort-Object { [int]$_.Name } | Select-Object -Last 1; if ($latest) { $latest.FullName } else { exit 1 }"`) do set "LATEST_SEASON=%%I"

if not defined LATEST_SEASON (
  echo No season folders found under seasons.
  popd
  pause
  exit /b 1
)

echo [2/5] Latest season: %LATEST_SEASON%
echo [3/5] Building docs...
python -u -m virtual_league.cli build-pages --seasons-dir seasons --output docs --season-dir "%LATEST_SEASON%"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" goto :done

echo [4/5] Staging Pages output...
git add docs
git diff --cached --quiet
if "%ERRORLEVEL%"=="0" (
  echo No Pages file changes. Creating an empty publish commit to trigger GitHub Pages.
  git commit --allow-empty -m "Publish GitHub Pages"
) else (
  git commit -m "Publish GitHub Pages"
)
if not "%ERRORLEVEL%"=="0" goto :done

echo [5/5] Pushing to GitHub...
git push origin HEAD:main
set "EXIT_CODE=%ERRORLEVEL%"

:done
if "%EXIT_CODE%"=="0" (
  echo Done.
) else (
  echo Failed with exit code %EXIT_CODE%.
)
popd
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%
