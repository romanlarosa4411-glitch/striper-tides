#!/bin/bash
# First-time setup + run for striper_tides
# Run this once: bash setup_and_run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Striper Tide Calendar Setup ==="

# Check for Python 3
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install it from https://python.org"
    exit 1
fi

# Create a virtual environment if it doesn't exist
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$SCRIPT_DIR/.venv"
fi

# Activate and install deps
source "$SCRIPT_DIR/.venv/bin/activate"
echo "Installing dependencies..."
pip install -q -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "=== Generating tide calendar (next 90 days) ==="
python3 "$SCRIPT_DIR/striper_tides.py" "$@"
