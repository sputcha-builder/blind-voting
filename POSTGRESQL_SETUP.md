# PostgreSQL Setup Guide

This guide explains how to set up and use PostgreSQL with the Blind Voting System, both locally and on Render.com.

## Architecture Overview

The application uses a **storage abstraction layer** that automatically switches between JSON files and PostgreSQL based on the `DATABASE_URL` environment variable:

- **No `DATABASE_URL` set**: Uses JSON files (`roles.json`, `votes.json`) - Perfect for local development
- **`DATABASE_URL` set**: Uses PostgreSQL database - Required for production on Render.com

## Local Development (JSON Files)

By default, the application uses JSON files for storage. No setup required!

```bash
# Just run the app - it will automatically use JSON files
python3 app.py
```

You'll see: `Using JSON files for storage`

## Local PostgreSQL Testing (Optional)

If you want to test PostgreSQL locally before deploying to Render:

### 1. Install PostgreSQL

**macOS (using Homebrew):**
```bash
brew install postgresql@15
brew services start postgresql@15
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
```

**Windows:**
Download and install from [postgresql.org](https://www.postgresql.org/download/windows/)

### 2. Create a Database

```bash
# Switch to postgres user (Linux only)
sudo -u postgres psql

# Or on macOS, just run:
psql postgres

# Create database and user
CREATE DATABASE blind_voting;
CREATE USER voting_admin WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE blind_voting TO voting_admin;
\q
```

### 3. Set DATABASE_URL Environment Variable

```bash
# Format: postgresql://user:password@host:port/database
export DATABASE_URL='postgresql://voting_admin:your_secure_password@localhost:5432/blind_voting'
```

### 4. Run the Application

```bash
python3 app.py
```

You'll see: `Using PostgreSQL database for storage`

### 5. Migrate Existing JSON Data (Optional)

If you have existing data in JSON files that you want to migrate to PostgreSQL:

```bash
# Make sure DATABASE_URL is set
export DATABASE_URL='postgresql://voting_admin:your_secure_password@localhost:5432/blind_voting'

# Run migration script
python3 migrate_json_to_db.py
```

The migration script will:
- ✓ Read data from `roles.json` and `votes.json`
- ✓ Initialize PostgreSQL database tables
- ✓ Migrate all roles, candidates, and votes
- ✓ Verify data integrity
- ✓ Create backup files (`roles.json.backup_TIMESTAMP`, `votes.json.backup_TIMESTAMP`)

## Production Deployment on Render.com

### 1. Create PostgreSQL Database on Render

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New +" → "PostgreSQL"
3. Fill in the details:
   - **Name**: `blind-voting-db`
   - **Database**: `blind_voting`
   - **User**: `voting_admin`
   - **Region**: Choose closest to your users
   - **Plan**: **Free** (1GB storage, expires after 90 days)
4. Click "Create Database"
5. Copy the **Internal Database URL** (it will look like: `postgresql://user:pass@host:5432/dbname`)

### 2. Configure Your Web Service

1. Go to your Web Service on Render
2. Go to "Environment" tab
3. Add environment variables:
   - `DATABASE_URL`: Paste the Internal Database URL from step 1
   - `ANTHROPIC_API_KEY`: Your Claude API key (if using AI features)
4. Click "Save Changes"

Render will automatically redeploy your application.

### 3. Verify Database Connection

Check your deploy logs. You should see:
```
Using PostgreSQL database for storage
Successfully connected to database: ...
✓ Database initialized successfully
```

### 4. Migrate Data from Local Development

If you have existing roles and votes from local development:

**Option A: Use the web interface**
- Manually recreate roles through the admin interface
- Voters can submit their votes again

**Option B: Run migration on Render (Advanced)**

1. Connect to Render Shell:
   - Go to your Web Service
   - Click "Shell" tab
   - Run: `python3 migrate_json_to_db.py`

2. Upload JSON files first:
   ```bash
   # You'll need to upload roles.json and votes.json to Render
   # This can be done via git or manual file upload
   ```

## Database Schema

The PostgreSQL database has the following tables:

### `roles`
- `id` (UUID, Primary Key)
- `position` (String) - Job position name
- `status` (String) - active, fulfilled, or expired
- `created_at` (DateTime)
- `updated_at` (DateTime)

### `candidates`
- `id` (Integer, Primary Key)
- `role_id` (UUID, Foreign Key → roles)
- `candidate_id` (String) - Unique ID within role
- `name` (String) - Candidate name

### `allowed_voters`
- `id` (Integer, Primary Key)
- `role_id` (UUID, Foreign Key → roles)
- `email` (String) - Voter email address

### `votes`
- `id` (Integer, Primary Key)
- `voter` (String) - Voter email
- `candidate_id` (String)
- `candidate_name` (String) - Denormalized for performance
- `role_id` (UUID, Foreign Key → roles)
- `role_position` (String) - Denormalized for performance
- `choice` (String) - "Inclined" or "Not Inclined"
- `feedback` (Text)
- `timestamp` (DateTime)

### `config` (Legacy)
- `id` (Integer, Primary Key)
- `position` (String)
- `is_configured` (Boolean)

**Unique Constraint**: A voter can only vote once per candidate per role (voter + candidate_id + role_id)

## Storage Layer Functions

All functions have identical signatures whether using JSON or PostgreSQL:

### Roles
- `load_roles()` → `{'roles': [...]}`
- `save_roles(data)` - Save all roles
- `save_role(role_data)` - Save/update single role
- `get_role_by_id(role_id)` → role dict or None
- `delete_role(role_id)` → True/False

### Votes
- `load_votes()` → `{'votes': [...]}`
- `save_votes(data)` - Save all votes
- `save_vote(vote_data)` - Save/update single vote

### Config (Legacy)
- `load_config()` → config dict
- `save_config(data)` - Save config

### Initialization
- `init_db()` - Initialize database tables (no-op for JSON)

## Troubleshooting

### "DATABASE_URL environment variable is not set"
- **Solution**: Set the DATABASE_URL environment variable or unset it to use JSON files

### "Failed to connect to database"
- **Solution**: Check that:
  - PostgreSQL is running
  - Database exists
  - Credentials are correct
  - Host/port are correct

### "Error initializing database"
- **Solution**: Check that the database user has CREATE TABLE privileges

### Migration script fails
- **Solution**:
  - Ensure DATABASE_URL is set
  - Ensure JSON files exist
  - Check PostgreSQL connection
  - Verify database is empty or confirm data replacement

### Port 5000/5001 already in use
```bash
# Kill existing process
lsof -ti:5001 | xargs kill -9

# Then restart
python3 app.py
```

## File Structure

```
blind-voting/
├── app.py                    # Main Flask application
├── storage.py                # Storage abstraction layer
├── json_operations.py        # JSON file operations
├── db_operations.py          # PostgreSQL operations
├── database.py               # PostgreSQL connection management
├── models.py                 # SQLAlchemy ORM models
├── migrate_json_to_db.py     # Migration script
├── roles.json                # Local storage (when not using DB)
├── votes.json                # Local storage (when not using DB)
└── templates/                # HTML templates
    ├── vote.html
    ├── results.html
    └── admin.html
```

## Render Free Tier Limits

- **Storage**: 1GB
- **RAM**: 512MB
- **Duration**: Database expires after 90 days of inactivity
- **Connections**: Limited concurrent connections
- **Backup**: Not included (manual backups recommended)

**Important**: The free PostgreSQL instance will be deleted after 90 days. For long-term production use, consider upgrading to a paid plan.

## Best Practices

1. **Local Development**: Use JSON files (no DATABASE_URL)
2. **Testing**: Use local PostgreSQL before deploying
3. **Production**: Use Render PostgreSQL addon
4. **Backups**: Regularly export data using the migration script or admin interface
5. **Security**: Never commit DATABASE_URL to git
6. **Monitoring**: Check Render logs for database connection issues

## Support

For issues or questions:
- Check application logs
- Review this documentation
- Test locally before deploying
- Verify environment variables are set correctly
