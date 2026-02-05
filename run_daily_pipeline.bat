@echo off
REM ============================================================
REM Daily Market Intelligence - Auto Pipeline
REM 
REM Execution Order:
REM 1. Phase 6:  Generate Korean Daily Brief
REM 2. Phase 6-1: Send to Telegram
REM 3. Phase 7:  Generate English Global Brief
REM 4. Phase 7-1: Post to WordPress (English)
REM ============================================================

echo ========================================
echo Daily Market Intelligence Pipeline
echo ========================================
echo.

REM Phase 6: Korean Daily Brief
echo [1/4] Running Phase 6 - Korean Daily Brief...
python run_p6.py
if %errorlevel% neq 0 (
    echo ERROR: Phase 6 failed!
    exit /b 1
)
echo Phase 6 completed successfully.
echo.

REM Phase 6-1: Telegram Delivery
echo [2/4] Running Phase 6-1 - Telegram Delivery...
python run_p6_1.py
if %errorlevel% neq 0 (
    echo ERROR: Phase 6-1 failed!
    exit /b 1
)
echo Phase 6-1 completed successfully.
echo.

REM Phase 7: English Global Brief
echo [3/4] Running Phase 7 - English Global Brief...
python run_p7.py
if %errorlevel% neq 0 (
    echo ERROR: Phase 7 failed!
    exit /b 1
)
echo Phase 7 completed successfully.
echo.

REM Phase 7-1: WordPress Posting (English)
echo [4/4] Running Phase 7-1 - WordPress Posting...
python run_p7_1.py
if %errorlevel% neq 0 (
    echo ERROR: Phase 7-1 failed!
    exit /b 1
)
echo Phase 7-1 completed successfully.
echo.

echo ========================================
echo All phases completed successfully!
echo ========================================
pause
