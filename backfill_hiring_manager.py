"""
Backfill script to add default hiring manager to existing roles.
This script updates all roles that don't have a hiring_manager set to use the default value.

Usage:
    python backfill_hiring_manager.py
"""
import os
import sys

# Default hiring manager email
DEFAULT_HIRING_MANAGER = "sputcha@starbucks.com"


def backfill_database():
    """Backfill hiring manager for PostgreSQL database."""
    from database import db_session
    from models import Role

    print("Backfilling hiring manager in PostgreSQL database...")

    with db_session() as session:
        # Find all roles without a hiring manager
        roles_without_hm = session.query(Role).filter(
            (Role.hiring_manager == None) | (Role.hiring_manager == '')
        ).all()

        if not roles_without_hm:
            print("✓ All roles already have a hiring manager assigned.")
            return

        print(f"Found {len(roles_without_hm)} roles without hiring manager:")
        for role in roles_without_hm:
            print(f"  - {role.position} (ID: {role.id})")

        # Update all roles
        for role in roles_without_hm:
            role.hiring_manager = DEFAULT_HIRING_MANAGER
            print(f"  ✓ Updated: {role.position}")

        print(f"\n✓ Successfully updated {len(roles_without_hm)} roles with hiring manager: {DEFAULT_HIRING_MANAGER}")


def backfill_json():
    """Backfill hiring manager for JSON files."""
    import json

    print("Backfilling hiring manager in JSON files...")

    roles_file = "roles.json"

    if not os.path.exists(roles_file):
        print(f"✓ {roles_file} does not exist. Nothing to backfill.")
        return

    with open(roles_file, 'r') as f:
        data = json.load(f)

    roles = data.get('roles', [])

    if not roles:
        print("✓ No roles found in roles.json")
        return

    # Find roles without hiring manager
    roles_updated = 0
    for role in roles:
        if not role.get('hiring_manager'):
            role['hiring_manager'] = DEFAULT_HIRING_MANAGER
            roles_updated += 1
            print(f"  ✓ Updated: {role.get('position', 'Unknown')}")

    if roles_updated == 0:
        print("✓ All roles already have a hiring manager assigned.")
        return

    # Save updated data
    with open(roles_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"\n✓ Successfully updated {roles_updated} roles in {roles_file} with hiring manager: {DEFAULT_HIRING_MANAGER}")


def main():
    """Main function to run the backfill script."""
    print("=" * 70)
    print("Hiring Manager Backfill Script")
    print("=" * 70)
    print(f"Default Hiring Manager: {DEFAULT_HIRING_MANAGER}\n")

    # Check if using database or JSON
    use_database = os.getenv('DATABASE_URL') is not None

    if use_database:
        print("Storage: PostgreSQL (DATABASE_URL is set)")
        try:
            backfill_database()
        except Exception as e:
            print(f"✗ Error during backfill: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("Storage: JSON files (DATABASE_URL not set)")
        try:
            backfill_json()
        except Exception as e:
            print(f"✗ Error during backfill: {e}", file=sys.stderr)
            sys.exit(1)

    print("\n" + "=" * 70)
    print("Backfill completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()
