@echo off
REM Batch file to start AEA JOE Automation Tool web server
REM Uses the correct Python version from Anaconda

echo Starting AEA JOE Web Server...
echo.

REM Change to project root directory (parent of scripts)
cd /d "%~dp0\.."

REM Use Anaconda Python
C:\ProgramData\anaconda3\python main.py --web

pause

