# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Blind Voting System - A Flask web application for conducting anonymous interview feedback collection. Voters submit "Inclined" or "Not Inclined" decisions with feedback for candidates. Results are hidden until all voters complete their assessments.

## Development Workflow

**IMPORTANT: Always test changes locally before committing and pushing to the repository.**

### Local Testing Process
1. Make your code changes
2. Start the development server: `./start-dev.sh`
3. Test your changes in the browser at `http://localhost:5001`
4. Stop the development server: `./stop-dev.sh` (or Ctrl+C)
5. Only after confirming changes work correctly, commit and push

### Quick Commands
```bash
./start-dev.sh                      # Start dev server (installs deps, runs on port 5001)
./stop-dev.sh                       # Stop dev server
```

## Commands

### Development
```bash
pip3 install -r requirements.txt    # Install dependencies
python3 app.py                      # Run development server (port 5001)
./start-dev.sh                      # Easier: Start dev server with auto setup
./stop-dev.sh                       # Stop dev server
```

### Production (Render.com)
```bash
./build.sh                          # Build script for Render
gunicorn app:app                    # Start command for Render
```

### Database Migration
```bash
# Set DATABASE_URL first, then:
python3 migrate_json_to_db.py       # Migrate JSON data to PostgreSQL
```

## Architecture

### Storage Abstraction Layer
The system uses a **dual-storage architecture** that automatically switches between JSON files (local dev) and PostgreSQL (production):

- `storage.py` - Routing layer that imports from either `json_operations.py` or `db_operations.py` based on `DATABASE_URL` environment variable
- `database.py` - PostgreSQL connection management using SQLAlchemy
- `models.py` - SQLAlchemy ORM models (Role, Candidate, AllowedVoter, Vote, Config)

### Key Data Models
- **Role** - A voting session for a position with candidates and allowed voters
- **Vote** - Individual voter's choice and feedback for a candidate
- **Config** - Legacy single-role configuration (deprecated, kept for backwards compatibility)

### API Structure
All endpoints in `app.py`:
- `/api/roles` - CRUD for roles (multi-role system)
- `/api/vote` - Submit votes (supports both legacy config and role-based)
- `/api/results/<role_id>` - Get results when voting complete
- `/api/summarize` - AI-powered feedback summarization using Claude API
- `/api/aggregate-summary/<role_id>/<candidate_id>` - Aggregate all voter feedback for a candidate

### Frontend
Three HTML templates in `templates/`:
- `vote.html` - Voter interface for submitting decisions
- `results.html` - Admin view of voting results
- `admin.html` - Role management and configuration

## Environment Variables

- `DATABASE_URL` - PostgreSQL connection string (if unset, uses JSON files)
- `ANTHROPIC_API_KEY` - Required for AI feedback summarization features
- `RENDER` or `PORT=10000` - Triggers production mode (HTTPS redirect, security headers)

## Important Constraints

- Roles with existing votes cannot be deleted (must be marked as "expired")
- Candidates with votes cannot be removed from a role
- Maximum 5 voters per role
- Votes can be updated but not deleted
