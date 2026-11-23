@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto missing
set "AS_TEST_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%AS_TEST_PY%" goto missing
set "PYTHONUTF8=1"
set "QT_QPA_PLATFORM=offscreen"
echo Running tests with the local .venv interpreter and Qt offscreen.
echo This is not a replacement for Windows desktop media verification.
"%AS_TEST_PY%" -m pytest tests -q %*
set "AS_TEST_RESULT=%ERRORLEVEL%"
echo.
echo Test process exit code: %AS_TEST_RESULT%
if not "%AS_NO_PAUSE%"=="1" pause
exit /b %AS_TEST_RESULT%
:missing
echo A local .venv Python was not found. Run SETUP_CODEX_WINDOWS.bat first.
if not "%AS_NO_PAUSE%"=="1" pause
exit /b 1
