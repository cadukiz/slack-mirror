#!/bin/bash
# Adds a cron job to run the Slack mirror every 30 minutes

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CRON_CMD="*/30 * * * * cd $SCRIPT_DIR && $SCRIPT_DIR/venv/bin/python main.py >> /tmp/slack_mirror.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "slack_mirror"; then
    echo "Cron job already exists. Updating..."
    crontab -l 2>/dev/null | grep -v "slack_mirror" | crontab -
fi

# Add the cron job
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -

echo "Cron job installed: runs every 30 minutes"
echo "Logs at: /tmp/slack_mirror.log"
echo ""
echo "To remove: crontab -e and delete the slack_mirror line"
