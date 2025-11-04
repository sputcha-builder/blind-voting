#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Create initial data files if they don't exist
if [ ! -f votes.json ]; then
    echo '{"votes": [], "voters": []}' > votes.json
fi

if [ ! -f config.json ]; then
    echo '{"candidate_name": "", "position": "", "allowed_emails": [], "is_configured": false}' > config.json
fi
