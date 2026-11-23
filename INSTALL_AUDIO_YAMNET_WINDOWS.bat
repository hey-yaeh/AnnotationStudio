@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto failed
title Annotation Studio - Optional YAMNet runtime
set "AS_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%AS_PY%" goto missing
"%AS_PY%" "%~dp0scripts\windows_preflight.py"
if errorlevel 1 goto failed
echo Installing optional YAMNet libraries into this project's .venv.
echo Native Windows uses the TensorFlow CPU runtime.
echo This step installs libraries; it does not download YAMNet model weights.
"%AS_PY%" -m pip install -r requirements-audio-yamnet.txt
if errorlevel 1 goto failed
"%AS_PY%" -m pip check
if errorlevel 1 goto failed
"%AS_PY%" -c "import tensorflow as tf, tensorflow_hub as hub; print('TensorFlow:', tf.__version__, 'Hub:', hub.__version__)"
if errorlevel 1 goto failed
echo.
echo Runtime installed. Restart Annotation Studio and select a local YAMNet
echo SavedModel directory, or explicitly select the model download option.
echo For setup details see docs\AUDIO_MODELS.md.
if not "%AS_NO_PAUSE%"=="1" pause
exit /b 0
:missing
echo Run INSTALL_WINDOWS.bat first.
:failed
echo Optional YAMNet runtime installation failed. Read the error above.
if not "%AS_NO_PAUSE%"=="1" pause
exit /b 1
