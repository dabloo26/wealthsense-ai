#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export DYLD_LIBRARY_PATH="/opt/homebrew/opt/expat/lib:${DYLD_LIBRARY_PATH:-}"
export PYTHONPATH="$SCRIPT_DIR/src"

echo "Installing WealthSense dependencies..."
python3 -m pip install --user --break-system-packages -r requirements.txt

echo "Training all models and generating artifacts..."
python3 -m wealthsense_ai.train

echo "Launching Streamlit dashboard..."
python3 -m streamlit run src/wealthsense_ai/app.py
