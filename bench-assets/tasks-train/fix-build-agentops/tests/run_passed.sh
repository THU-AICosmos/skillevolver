#!/bin/bash
set -e
cd /home/github/build/passed/StatCalc-AI/statcalc
pip install -e . 2>/dev/null || true
python -m pytest tests/ -v --tb=short
