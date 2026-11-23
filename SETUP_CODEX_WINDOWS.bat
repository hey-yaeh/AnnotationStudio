@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "AS_DEV_CALLER_NO_PAUSE=%AS_NO_PAUSE%"
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto failed
title Annotation Studio v0.5.4 - Developer setup
set "AS_NO_PAUSE=1"
echo Annotation Studio developer setup creates an isolated .venv.
echo Internet is required for dependencies. No administrator privileges are needed.
echo No neural model weights will be downloaded.
call "%~dp0INSTALL_WINDOWS.bat"
if errorlevel 1 goto failed
set "AS_DEV_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%AS_DEV_PY%" goto failed
"%AS_DEV_PY%" -m pip install -r "%~dp0requirements-dev.txt"
if errorlevel 1 goto failed
"%AS_DEV_PY%" -m pip check
if errorlevel 1 goto failed
"%AS_DEV_PY%" "%~dp0scripts\doctor.py"
if errorlevel 1 goto failed
echo.
echo Developer setup complete. Read README.md in this folder.
echo Use OPEN_IN_VSCODE.bat to open the project and RUN_TESTS_WINDOWS.bat to test.
if not "%AS_DEV_CALLER_NO_PAUSE%"=="1" pause
exit /b 0
:failed
echo.
echo DEVELOPER SETUP FAILED. Read the error above.
if not "%AS_DEV_CALLER_NO_PAUSE%"=="1" pause
exit /b 1
