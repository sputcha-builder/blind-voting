#!/bin/bash

# Blind Voting System - Development Server Stop Script

echo "Stopping Blind Voting System Development Server..."

# Find Flask development server process on port 5001
PID=$(lsof -ti:5001)

if [ -z "$PID" ]; then
    echo "No development server found running on port 5001"
    exit 0
fi

# Kill the process
echo "Stopping server (PID: $PID)..."
kill $PID

# Wait a moment and check if it's stopped
sleep 1

if lsof -ti:5001 > /dev/null 2>&1; then
    echo "Process didn't stop gracefully, force killing..."
    kill -9 $PID
    sleep 1
fi

# Verify it's stopped
if ! lsof -ti:5001 > /dev/null 2>&1; then
    echo "Development server stopped successfully"
else
    echo "Warning: Server may still be running"
    exit 1
fi
