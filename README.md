# Blind Voting System

A simple web application for conducting blind votes with 3 collaborators.

## Features

- **Blind Voting**: Voters can't see results until all 3 votes are submitted
- **Two Choices**: "Inclined" or "Not Inclined"
- **One Vote Per Person**: Each voter can only vote once per session
- **Admin Controls**: Reset votes to start a new voting session
- **Real-time Results**: Auto-refresh results page every 5 seconds

## Setup

1. Install Flask:
   ```bash
   pip3 install -r requirements.txt
   ```

2. Run the server:
   ```bash
   python3 app.py
   ```

3. The server will display URLs for:
   - **Voting page** - Share this with your 3 collaborators
   - **Results page** - Only you access this (results only show after all 3 votes are in)
   - **Admin page** - Reset votes to start a new session

## Usage

### For Voters
1. Open the voting URL
2. Enter your name
3. Click either "Inclined" or "Not Inclined"
4. You'll see a confirmation (but not the results)

### For You (Admin)
1. Open the **Results page** to view votes
   - If less than 3 votes: Shows "Waiting for X more votes"
   - After all 3 votes: Shows full breakdown
2. Open the **Admin page** to:
   - See voting status
   - Reset all votes for a new session

## Technical Details

- **Backend**: Python Flask
- **Storage**: JSON file (votes.json)
- **Frontend**: Vanilla HTML/CSS/JavaScript
- **Port**: 5001 (default)

## Network Access

The server runs on `0.0.0.0:5001`, making it accessible on your local network.
Your collaborators can access it via your local IP address (shown when server starts).
