#!/bin/bash
set -eu

# Entry point for the non-pedestrian transit-log task.
# Class-based pipeline lives in transit_log.py beside this script.

HERE="$(cd "$(dirname "$0")" && pwd)"
exec python3 "${HERE}/transit_log.py"
