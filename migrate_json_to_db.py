"""
Migration script to move data from JSON files to PostgreSQL database.

Usage:
    1. Set DATABASE_URL environment variable to your PostgreSQL connection string
    2. Run: python3 migrate_json_to_db.py

The script will:
- Read data from roles.json and votes.json
- Initialize the PostgreSQL database
- Migrate all roles, candidates, allowed voters, and votes
- Verify data integrity
- Create backups of JSON files

Requirements:
- DATABASE_URL must be set
- JSON files (roles.json, votes.json) must exist
"""

import os
import sys
import json
import shutil
from datetime import datetime

def main():
    """Main migration function"""
    print("="*60)
    print("JSON to PostgreSQL Migration Script")
    print("="*60)

    # Check if DATABASE_URL is set
    if not os.getenv('DATABASE_URL'):
        print("\n❌ ERROR: DATABASE_URL environment variable is not set")
        print("\nPlease set DATABASE_URL to your PostgreSQL connection string:")
        print("  export DATABASE_URL='postgresql://user:password@host:port/database'")
        print("\nFor Render.com, this is provided automatically as an environment variable.")
        sys.exit(1)

    print(f"\n✓ DATABASE_URL is set: {os.getenv('DATABASE_URL').split('@')[-1]}")

    # Check if JSON files exist
    roles_file = 'roles.json'
    votes_file = 'votes.json'

    if not os.path.exists(roles_file):
        print(f"\n❌ ERROR: {roles_file} not found")
        print("Nothing to migrate.")
        sys.exit(1)

    if not os.path.exists(votes_file):
        print(f"\n❌ ERROR: {votes_file} not found")
        print("Nothing to migrate.")
        sys.exit(1)

    print(f"✓ Found {roles_file}")
    print(f"✓ Found {votes_file}")

    # Load JSON data
    print("\nReading JSON files...")
    try:
        with open(roles_file, 'r') as f:
            roles_data = json.load(f)
        print(f"  ✓ Loaded {len(roles_data.get('roles', []))} roles")

        with open(votes_file, 'r') as f:
            votes_data = json.load(f)
        print(f"  ✓ Loaded {len(votes_data.get('votes', []))} votes")
    except Exception as e:
        print(f"\n❌ ERROR reading JSON files: {e}")
        sys.exit(1)

    # Import database modules (will fail if DATABASE_URL not set)
    print("\nConnecting to PostgreSQL database...")
    try:
        from database import init_db
        from db_operations import save_roles, save_votes, load_roles, load_votes
        print("  ✓ Database modules loaded")
    except Exception as e:
        print(f"\n❌ ERROR loading database modules: {e}")
        sys.exit(1)

    # Initialize database tables
    print("\nInitializing database tables...")
    try:
        init_db()
        print("  ✓ Database tables initialized")
    except Exception as e:
        print(f"\n❌ ERROR initializing database: {e}")
        sys.exit(1)

    # Check if database already has data
    existing_roles = load_roles()
    existing_votes = load_votes()

    if len(existing_roles.get('roles', [])) > 0 or len(existing_votes.get('votes', [])) > 0:
        print(f"\n⚠️  WARNING: Database already contains data:")
        print(f"    - {len(existing_roles.get('roles', []))} roles")
        print(f"    - {len(existing_votes.get('votes', []))} votes")

        response = input("\nDo you want to REPLACE all existing data? (yes/no): ")
        if response.lower() != 'yes':
            print("\n❌ Migration cancelled by user")
            sys.exit(0)
        print("  ✓ User confirmed data replacement")

    # Migrate roles
    print("\nMigrating roles to database...")
    try:
        save_roles(roles_data)
        print(f"  ✓ Migrated {len(roles_data.get('roles', []))} roles")
    except Exception as e:
        print(f"\n❌ ERROR migrating roles: {e}")
        sys.exit(1)

    # Migrate votes
    print("\nMigrating votes to database...")
    try:
        save_votes(votes_data)
        print(f"  ✓ Migrated {len(votes_data.get('votes', []))} votes")
    except Exception as e:
        print(f"\n❌ ERROR migrating votes: {e}")
        sys.exit(1)

    # Verify data integrity
    print("\nVerifying data integrity...")
    try:
        db_roles = load_roles()
        db_votes = load_votes()

        json_role_count = len(roles_data.get('roles', []))
        db_role_count = len(db_roles.get('roles', []))

        json_vote_count = len(votes_data.get('votes', []))
        db_vote_count = len(db_votes.get('votes', []))

        if json_role_count != db_role_count:
            print(f"  ❌ Role count mismatch: JSON={json_role_count}, DB={db_role_count}")
            sys.exit(1)

        if json_vote_count != db_vote_count:
            print(f"  ❌ Vote count mismatch: JSON={json_vote_count}, DB={db_vote_count}")
            sys.exit(1)

        print(f"  ✓ Role count matches: {db_role_count}")
        print(f"  ✓ Vote count matches: {db_vote_count}")

        # Verify candidate counts
        total_json_candidates = sum(len(r.get('candidates', [])) for r in roles_data.get('roles', []))
        total_db_candidates = sum(len(r.get('candidates', [])) for r in db_roles.get('roles', []))

        if total_json_candidates != total_db_candidates:
            print(f"  ❌ Candidate count mismatch: JSON={total_json_candidates}, DB={total_db_candidates}")
            sys.exit(1)

        print(f"  ✓ Candidate count matches: {total_db_candidates}")

    except Exception as e:
        print(f"\n❌ ERROR verifying data: {e}")
        sys.exit(1)

    # Create backups
    print("\nCreating JSON file backups...")
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        roles_backup = f'roles.json.backup_{timestamp}'
        votes_backup = f'votes.json.backup_{timestamp}'

        shutil.copy2(roles_file, roles_backup)
        print(f"  ✓ Created {roles_backup}")

        shutil.copy2(votes_file, votes_backup)
        print(f"  ✓ Created {votes_backup}")
    except Exception as e:
        print(f"\n⚠️  WARNING: Could not create backups: {e}")
        print("  (Migration was successful, but backups failed)")

    # Summary
    print("\n" + "="*60)
    print("✅ MIGRATION COMPLETED SUCCESSFULLY")
    print("="*60)
    print(f"\nMigrated to PostgreSQL:")
    print(f"  - {db_role_count} roles")
    print(f"  - {total_db_candidates} candidates")
    print(f"  - {db_vote_count} votes")
    print(f"\nBackup files created:")
    print(f"  - {roles_backup}")
    print(f"  - {votes_backup}")
    print("\nYour application will now use PostgreSQL for storage.")
    print("The JSON files can be safely archived or deleted.")
    print("="*60)

if __name__ == '__main__':
    main()
