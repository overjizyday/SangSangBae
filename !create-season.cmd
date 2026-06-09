@echo off
setlocal EnableExtensions
set "ROOT=%~dp0"
pushd "%ROOT%"

echo [1/2] Creating next season...
python -u -m virtual_league.cli create-season --seasons-dir seasons
set "EXIT_CODE=%ERRORLEVEL%"

if "%EXIT_CODE%"=="0" (
  echo Done.
) else (
  echo Failed with exit code %EXIT_CODE%.
)
popd
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%
