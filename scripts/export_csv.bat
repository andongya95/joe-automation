@echo off
REM Batch file to export jobs to CSV
REM Uses the correct Python version from Anaconda

echo Exporting jobs to CSV...
echo.

REM Change to project root directory (parent of scripts)
cd /d "%~dp0\.."

REM Check if output file argument provided
if "%1"=="" (
    echo Exporting to data/exports/job_matches.csv...
    C:\ProgramData\anaconda3\python main.py --export
) else (
    echo Exporting to %1...
    C:\ProgramData\anaconda3\python main.py --export --output %1
)

echo.
echo Export complete!
pause

