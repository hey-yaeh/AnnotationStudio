@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto failed
title Annotation Studio v0.5.4 - Setup
echo ==========================================================
echo  Annotation Studio v0.5.4 - First-time setup
echo ==========================================================
echo Creates an isolated .venv in this folder. Internet required.
echo Use a short extraction folder such as D:\AS. Setup checks the path before installing.
echo.
set "AS_PY=%~dp0.venv\Scripts\python.exe"
if exist "%AS_PY%" goto install
where py >nul 2>&1
if errorlevel 1 goto try_python
py -3.11 -c "import struct; raise SystemExit(0 if struct.calcsize('P') == 8 else 1)" >nul 2>&1
if not errorlevel 1 goto create311
py -3.12 -c "import struct; raise SystemExit(0 if struct.calcsize('P') == 8 else 1)" >nul 2>&1
if not errorlevel 1 goto create312
:try_python
python -c "import sys, struct; raise SystemExit(0 if sys.version_info[:2] in ((3,11),(3,12)) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
if errorlevel 1 goto no_python
python "%~dp0scripts\windows_preflight.py"
if errorlevel 1 goto failed
python -m venv ".venv"
if errorlevel 1 goto failed
goto install
:create311
py -3.11 "%~dp0scripts\windows_preflight.py"
if errorlevel 1 goto failed
py -3.11 -m venv ".venv"
if errorlevel 1 goto failed
goto install
:create312
py -3.12 "%~dp0scripts\windows_preflight.py"
if errorlevel 1 goto failed
py -3.12 -m venv ".venv"
if errorlevel 1 goto failed
:install
if not exist "%AS_PY%" goto failed
"%AS_PY%" -c "import sys, struct; raise SystemExit(0 if sys.version_info[:2] in ((3,11),(3,12)) and struct.calcsize('P') == 8 else 1)"
if errorlevel 1 goto wrong_venv
"%AS_PY%" "%~dp0scripts\windows_preflight.py"
if errorlevel 1 goto failed
"%AS_PY%" -m pip --version
if errorlevel 1 goto missing_pip
"%AS_PY%" -m pip install --upgrade "pip>=24"
if errorlevel 1 goto failed
"%AS_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto failed
"%AS_PY%" -m pip check
if errorlevel 1 goto failed
"%AS_PY%" -c "from PySide6 import QtCore, QtWidgets, QtMultimedia, QtMultimediaWidgets; import numpy, scipy, soundfile; print('Core dependencies imported successfully.')"
if errorlevel 1 goto failed
echo.
echo Installed. Double-click RUN_WINDOWS.bat to launch.
echo Optional audio models have separate INSTALL_AUDIO_* scripts.
echo This is a source runtime package, not a precompiled Windows EXE.
if not "%AS_NO_PAUSE%"=="1" pause
exit /b 0
:no_python
echo ERROR: Install 64-bit Python 3.11 or 3.12 with pip and venv.
echo Enable the Python launcher or add Python to PATH, then retry.
goto failed
:wrong_venv
echo ERROR: The existing .venv is not 64-bit Python 3.11/3.12.
echo Rename that .venv folder and rerun this installer to create a compatible one.
goto failed
:missing_pip
echo ERROR: pip is unavailable in the existing .venv.
echo Keep this folder for diagnosis and use a fresh short extraction for a clean setup.
goto failed
:failed
echo.
echo SETUP FAILED. Read the error above. No model weights were downloaded.
echo For a PySide6 long-path error, extract a fresh copy to D:\AS and rerun.
echo Do not carry a moved or partially installed .venv into the new folder.
echo Recovery help: docs\WINDOWS_SETUP_CN.md
if not "%AS_NO_PAUSE%"=="1" pause
exit /b 1
