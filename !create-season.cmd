@echo off
setlocal
set "ROOT=%~dp0"
pushd "%ROOT%"

python -m virtual_league.cli create-season --seasons-dir seasons
set "EXIT_CODE=%ERRORLEVEL%"

popd
if not "%EXIT_CODE%"=="0" pause
exit /b %EXIT_CODE%
