#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python src/placement_tool.py
