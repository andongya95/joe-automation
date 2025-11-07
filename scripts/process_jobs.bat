@echo off
REM Batch file to process jobs with LLM
REM Auto-detects an available Python interpreter (honors optional PYTHON_BIN)

setlocal

echo Processing jobs with LLM...
echo.

REM Change to project root directory (parent of scripts)
cd /d "%~dp0\.."

call :ensure_python
if errorlevel 1 goto :end

echo Using Python interpreter: %PYTHON_BIN%
echo.

REM Check if limit argument provided
if "%~1"=="" (
    echo Processing all unprocessed jobs...
    %PYTHON_BIN% main.py --process
) else (
    echo Processing first %1 jobs...
    %PYTHON_BIN% main.py --process --process-limit %1
)

echo.
echo Processing complete!

:end
pause
exit /b

:ensure_python
if defined PYTHON_BIN (
    "%PYTHON_BIN%" --version >nul 2>&1
    if not errorlevel 1 exit /b 0
    echo Provided PYTHON_BIN "%PYTHON_BIN%" is not a working interpreter.
    set "PYTHON_BIN="
)

py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_BIN=py -3"
    exit /b 0
)

py -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_BIN=py"
    exit /b 0
)

python -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_BIN=python"
    exit /b 0
)

python3 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_BIN=python3"
    exit /b 0
)

echo Unable to locate a Python interpreter. Set PYTHON_BIN and rerun this script.
exit /b 1
