@echo off
REM Batch file to scrape and update job listings
REM Uses the correct Python version from Anaconda

echo Scraping AEA JOE job listings...
echo.

REM Change to project root directory (parent of scripts)
cd /d "%~dp0\.."

REM Use Anaconda Python
C:\ProgramData\anaconda3\python main.py --update

echo.
echo Scraping complete!
pause

