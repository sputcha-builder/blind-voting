#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Create initial data files if they don't exist
if [ ! -f votes.json ]; then
    echo '{"votes": []}' > votes.json
fi

if [ ! -f config.json ]; then
    echo '{"position": "", "candidates": [], "allowed_emails": [], "is_configured": false}' > config.json
fi

# Run database migrations (only applies when DATABASE_URL is set)
if [ -n "$DATABASE_URL" ]; then
    echo "Running database migrations..."
    python migrate_add_results_override.py
fi
