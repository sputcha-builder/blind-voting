#!/bin/bash

# Blind Voting System - Development Server Start Script

echo "Starting Blind Voting System Development Server..."
echo "=================================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "Installing dependencies..."
pip3 install -q -r requirements.txt

# Start the development server
echo ""
echo "Starting Flask development server on http://localhost:5001"
echo "Press Ctrl+C to stop the server, or run ./stop-dev.sh"
echo ""

# Run the app (this will block until stopped)
python3 app.py
