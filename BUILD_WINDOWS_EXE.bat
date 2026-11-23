@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto failed
title Annotation Studio v0.5.4 - Windows build
set "AS_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%AS_PY%" goto missing
"%AS_PY%" "%~dp0scripts\windows_preflight.py"
if errorlevel 1 goto failed
set "AS_AUDIO_FLAGS=--exclude-module torch --exclude-module silero_vad --exclude-module tensorflow --exclude-module tensorflow_hub"
set "AS_BUILD_NAME=AnnotationStudio"
set AS_EXAMPLE_DATA=--add-data "examples;examples"
set AS_DOC_DATA=--add-data "docs;docs"
if "%~1"=="--with-silero" goto with_silero
if "%~1"=="--with-audio" goto with_audio
if not "%~1"=="" goto usage
echo Building the core editor, BVH tools and energy detector.
echo Neural audio runtimes are excluded from the default EXE build.
goto build
:with_silero
"%AS_PY%" -c "import torch, silero_vad; from silero_vad import load_silero_vad; load_silero_vad(onnx=False)"
if errorlevel 1 goto missing_silero
set "AS_AUDIO_FLAGS=--exclude-module tensorflow --exclude-module tensorflow_hub --hidden-import torch --hidden-import silero_vad --collect-data silero_vad --copy-metadata silero-vad"
echo Building the editor plus the installed Silero VAD runtime and bundled model.
goto build
:with_audio
"%AS_PY%" -c "from annotationstudio.audio_models import model_status; models = {m['id']: m for m in model_status()}; raise SystemExit(0 if models['silero']['available'] and models['yamnet']['available'] and models['yamnet']['bundled_model_path'] else 1)"
if errorlevel 1 goto missing_audio
set "AS_BUILD_NAME=AnnotationStudio-Audio"
set "AS_EXAMPLE_DATA="
rem Keep the audio distribution to guides and catalog files at the top of docs.
set AS_DOC_DATA=--add-data "docs\*.md;docs" --add-data "docs\*.csv;docs" --add-data "docs\*.json;docs" --add-data "docs\*.xlsx;docs"
set AS_AUDIO_FLAGS=--exclude-module tensorflow_hub --hidden-import torch --hidden-import silero_vad --hidden-import tensorflow --collect-data silero_vad --copy-metadata silero-vad --copy-metadata torch --copy-metadata tensorflow --add-data "models\yamnet;models\yamnet"
echo Building Annotation Studio with local Silero VAD and YAMNet models.
:build
"%AS_PY%" -m PyInstaller --version >nul 2>&1
if not errorlevel 1 goto freeze
"%AS_PY%" -m pip install "pyinstaller>=6.16,<7"
if errorlevel 1 goto failed
:freeze
rem QtMultimedia hooks collect the Qt multimedia backend and its runtime DLLs.
rem The application resolves examples relative to sys._MEIPASS when frozen.
"%AS_PY%" -m PyInstaller --noconfirm --clean --onedir --windowed --name "%AS_BUILD_NAME%" --hidden-import PySide6.QtMultimedia --hidden-import PySide6.QtMultimediaWidgets --hidden-import soundfile --collect-binaries _soundfile_data %AS_EXAMPLE_DATA% %AS_DOC_DATA% --add-data "START_HERE.txt;." --paths . %AS_AUDIO_FLAGS% run_app.py
if errorlevel 1 goto failed
if not exist "dist\%AS_BUILD_NAME%\%AS_BUILD_NAME%.exe" goto failed
echo.
echo Build output: dist\%AS_BUILD_NAME%\%AS_BUILD_NAME%.exe
echo Distribute the ENTIRE dist\%AS_BUILD_NAME% folder, not only the EXE.
echo Test launch, video codecs, playback and saving on the target Windows machine.
echo This script builds on Windows; the supplied ZIP itself is a source package.
echo Startup errors are logged under %%LOCALAPPDATA%%\AnnotationStudio\logs.
if not "%AS_NO_PAUSE%"=="1" pause
exit /b 0
:usage
echo Usage: BUILD_WINDOWS_EXE.bat [--with-silero ^| --with-audio]
goto failed
:missing_silero
echo Run INSTALL_AUDIO_SILERO_WINDOWS.bat before using --with-silero.
goto failed
:missing_audio
echo Install Silero and TensorFlow and place the official YAMNet SavedModel in models\yamnet.
echo See docs\AUDIO_MODELS.md for the offline audio build.
goto failed
:missing
echo Run INSTALL_WINDOWS.bat first.
:failed
echo BUILD FAILED. Read the console error above.
if not "%AS_NO_PAUSE%"=="1" pause
exit /b 1
