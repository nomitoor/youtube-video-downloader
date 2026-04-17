#!/bin/bash
# Run this via cron to auto-delete downloads older than 30 minutes
# Add to crontab: */10 * * * * /bin/bash /app/cleanup.sh

DOWNLOADS_DIR="/app/downloads"
MAX_AGE_MINUTES=30

find "$DOWNLOADS_DIR" -mindepth 1 -maxdepth 1 -type d -mmin +$MAX_AGE_MINUTES -exec rm -rf {} +

echo "[$(date)] Cleanup done"
