@echo off
REM Batch file to calculate fit scores for jobs
REM Uses the correct Python version from Anaconda

echo Calculating fit scores...
echo.

REM Change to project root directory (parent of scripts)
cd /d "%~dp0\.."

REM Use Anaconda Python
C:\ProgramData\anaconda3\python main.py --match

echo.
echo Matching complete!
pause

