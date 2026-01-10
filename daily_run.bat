@echo off
setlocal

:: Set Project Directory
set PROJECT_DIR=d:\Dev\Developing\News_Agent
cd /d %PROJECT_DIR%

:: Check if virtual environment exists and activate
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [INFO] No virtual environment found in .venv, using system python
)

:: Run the python runner script
python daily_runner.py

:: Pause if running manually to see output (remove 'pause' for fully automated background run)
:: pause

endlocal
