@echo off
REM Batch file to start AEA JOE Automation Tool web server on custom port
REM Uses the correct Python version from Anaconda

echo Starting AEA JOE Web Server...
echo.

REM Change to project root directory (parent of scripts)
cd /d "%~dp0\.."

REM Check if port argument provided
if "%1"=="" (
    echo Usage: start_web_port.bat [PORT]
    echo Example: start_web_port.bat 8080
    echo Default port: 5000
    echo.
    set PORT=5000
) else (
    set PORT=%1
)

echo Starting on port %PORT%...
echo.

REM Use Anaconda Python
C:\ProgramData\anaconda3\python main.py --web --port %PORT%

pause

