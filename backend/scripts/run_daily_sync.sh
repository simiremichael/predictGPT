#!/bin/bash
# Daily sync cron job setup
# Add to crontab: 0 3 * * * /path/to/predictGPT/backend/scripts/run_daily_sync.sh

set -e

cd "$(dirname "$0")/.."

# Activate virtual environment if exists
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
fi

# Set PYTHONPATH
export PYTHONPATH=app

# Run daily sync
echo "Starting daily sync at $(date)"
python scripts/daily_sync.py
echo "Daily sync completed at $(date)"