@echo off
REM Batch file to process jobs with LLM
REM Uses the correct Python version from Anaconda

echo Processing jobs with LLM...
echo.

REM Change to project root directory (parent of scripts)
cd /d "%~dp0\.."

REM Check if limit argument provided
if "%1"=="" (
    echo Processing all unprocessed jobs...
    C:\ProgramData\anaconda3\python main.py --process
) else (
    echo Processing first %1 jobs...
    C:\ProgramData\anaconda3\python main.py --process --process-limit %1
)

echo.
echo Processing complete!
pause

