@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
if errorlevel 1 goto missing
title Annotation Studio v0.5.4
set "AS_PY=%~dp0.venv\Scripts\python.exe"
if not exist "%AS_PY%" goto missing
if "%~1"=="" goto default
set "AS_FIRST=%~1"
if "%AS_FIRST:~0,2%"=="--" goto flags
"%AS_PY%" -m annotationstudio --project %*
goto result
:flags
"%AS_PY%" -m annotationstudio %*
goto result
:default
if not exist "examples\S004_I02_manual.studio.json" goto empty
if not exist "examples\S004_I02_R01_BVH.bvh" goto empty
if not exist "examples\S004_I02_R02_BVH.bvh" goto empty
goto example
:empty
"%AS_PY%" -m annotationstudio
goto result
:example
"%AS_PY%" -m annotationstudio --manual-example
:result
set "AS_RESULT=%ERRORLEVEL%"
if "%AS_RESULT%"=="0" exit /b 0
echo.
echo Annotation Studio exited with error code %AS_RESULT%. See details above.
if not "%AS_NO_PAUSE%"=="1" pause
exit /b %AS_RESULT%
:missing
echo A local Python environment was not found. Run INSTALL_WINDOWS.bat first.
if not "%AS_NO_PAUSE%"=="1" pause
exit /b 1
