#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate

# Clear old log and create file
> battle_log.txt

# Tail the log in background
tail -f battle_log.txt &
TAIL_PID=$!

# Run game (blocks until quit)
python src/main.py

# Kill tail when game exits
kill $TAIL_PID 2>/dev/null
