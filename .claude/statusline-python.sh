#!/bin/bash

# Claude Code Python-based Status Line
# Wrapper script that calls the Python analyzer

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Make scripts executable
chmod +x "$SCRIPT_DIR/statusline-python.sh" 2>/dev/null
chmod +x "$SCRIPT_DIR/statusline_analyzer.py" 2>/dev/null

# Read Claude Code JSON input and pass to Python script
input=$(cat)

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    # Fallback to simple status if Python not available
    echo "[Claude] Status: Ready"
    exit 0
fi

# Call Python script with the input using the project-level script
# Remove the stderr redirect to see any issues during development
echo "$input" | python3 "$SCRIPT_DIR/statusline_analyzer.py" || echo "[Claude] Status: Ready"