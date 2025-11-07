#!/usr/bin/env bash
# Shell script to start the AEA JOE Automation Tool web server on Unix-like systems
# Usage: ./scripts/start_web.sh

set -euo pipefail

# Change to project root (parent directory of this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

# Start the web server using the default python available in PATH
# Override by setting PYTHON_BIN (e.g., PYTHON_BIN=/opt/miniconda/bin/python)
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "Starting AEA JOE Web Server with ${PYTHON_BIN}..."
${PYTHON_BIN} main.py --web
