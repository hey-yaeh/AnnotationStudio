@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto failed
title Annotation Studio - Optional Silero VAD
set "AS_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%AS_PY%" goto missing
"%AS_PY%" "%~dp0scripts\windows_preflight.py"
if errorlevel 1 goto failed
echo Installing optional local Silero VAD into this project's .venv.
echo CPU PyTorch is downloaded from its official CPU wheel index.
"%AS_PY%" -c "import torch; v=tuple(map(int, torch.__version__.split('+')[0].split('.')[:2])); raise SystemExit(0 if torch.version.cuda is None and v >= (2,2) else 1)" >nul 2>&1
if not errorlevel 1 goto silero
"%AS_PY%" -m pip install --upgrade --force-reinstall "torch>=2.2,<3" --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto failed
:silero
"%AS_PY%" -m pip install -r requirements-audio-silero.txt
if errorlevel 1 goto failed
"%AS_PY%" -m pip check
if errorlevel 1 goto failed
"%AS_PY%" -c "import torch; from silero_vad import load_silero_vad; load_silero_vad(onnx=False); print('Silero model loaded. PyTorch:', torch.__version__)"
if errorlevel 1 goto failed
echo.
echo Silero is installed and its bundled model loaded successfully.
echo Restart Annotation Studio. No diarization or Listener inference is included.
if not "%AS_NO_PAUSE%"=="1" pause
exit /b 0
:missing
echo Run INSTALL_WINDOWS.bat first.
:failed
echo Optional Silero installation failed. Read the error above.
if not "%AS_NO_PAUSE%"=="1" pause
exit /b 1
