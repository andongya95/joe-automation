#!/usr/bin/env bash
# Shell script to start the AEA JOE Automation Tool web server on a custom port
# Usage: ./scripts/start_web_port.sh 8080

set -euo pipefail

if [[ $# -gt 1 ]]; then
  echo "Usage: $0 [PORT]"
  exit 1
fi

PORT="${1:-5000}"

# Change to project root (parent directory of this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "Starting AEA JOE Web Server on port ${PORT} with ${PYTHON_BIN}..."
${PYTHON_BIN} main.py --web --port "${PORT}"
