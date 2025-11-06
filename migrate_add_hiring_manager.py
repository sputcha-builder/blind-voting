"""
Database migration script to add hiring_manager column to roles table.
This script is safe to run multiple times - it checks if the column exists first.

Usage:
    python migrate_add_hiring_manager.py

Requirements:
    - DATABASE_URL environment variable must be set
    - This is for PostgreSQL databases only
"""
import os
import sys
from sqlalchemy import create_engine, text, inspect

DEFAULT_HIRING_MANAGER = "sputcha@starbucks.com"


def check_column_exists(engine, table_name, column_name):
    """Check if a column exists in a table"""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate_database(verbose=True):
    """
    Add hiring_manager column to roles table if it doesn't exist.

    Args:
        verbose: If True, print detailed output. If False, only print errors.

    Returns:
        True if migration succeeded or not needed, False if failed
    """

    # Get database URL
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        if verbose:
            print("✗ ERROR: DATABASE_URL environment variable is not set")
            print("  This script is only needed for PostgreSQL databases.")
            print("  For JSON storage, use backfill_hiring_manager.py instead.")
        return False

    if verbose:
        print("=" * 70)
        print("DATABASE MIGRATION: Add hiring_manager Column")
        print("=" * 70)
        print(f"Database: {database_url.split('@')[-1]}")  # Don't log credentials
        print(f"Default value: {DEFAULT_HIRING_MANAGER}\n")

    try:
        # Create engine
        engine = create_engine(database_url)

        # Test connection
        with engine.connect() as conn:
            if verbose:
                print("✓ Connected to database successfully\n")

            # Check if roles table exists
            inspector = inspect(engine)
            tables = inspector.get_table_names()

            if 'roles' not in tables:
                if verbose:
                    print("✗ ERROR: 'roles' table does not exist in the database")
                    print("  Run the application first to create tables.")
                return False

            if verbose:
                print("✓ Found 'roles' table")

            # Check if hiring_manager column already exists
            if check_column_exists(engine, 'roles', 'hiring_manager'):
                if verbose:
                    print("✓ Column 'hiring_manager' already exists")
                    print("\nMigration not needed - database is already up to date!")

                    # Show current state
                    result = conn.execute(text("SELECT position, hiring_manager FROM roles"))
                    rows = result.fetchall()

                    if rows:
                        print(f"\nCurrent roles ({len(rows)} found):")
                        for row in rows:
                            position = row[0]
                            hm = row[1] or '(NULL)'
                            print(f"  - {position}: HM = {hm}")

                return True

            if verbose:
                print("⚠ Column 'hiring_manager' does NOT exist - migration needed\n")

            # Count existing roles before migration
            result = conn.execute(text("SELECT COUNT(*) FROM roles"))
            role_count = result.scalar()

            if verbose:
                print(f"Found {role_count} existing role(s) in database")

                if role_count > 0:
                    result = conn.execute(text("SELECT id, position FROM roles"))
                    rows = result.fetchall()
                    print("\nExisting roles:")
                    for row in rows:
                        print(f"  - {row[1]} (ID: {row[0]})")

                print("\n" + "=" * 70)
                print("STARTING MIGRATION")
                print("=" * 70)

            # Step 1: Add column (nullable)
            if verbose:
                print("\n[1/3] Adding 'hiring_manager' column...")

            conn.execute(text("""
                ALTER TABLE roles
                ADD COLUMN hiring_manager VARCHAR(255)
            """))
            conn.commit()

            if verbose:
                print("  ✓ Column added successfully")

            # Step 2: Set default value for existing rows
            if role_count > 0:
                if verbose:
                    print(f"\n[2/3] Setting default hiring manager for {role_count} existing role(s)...")

                result = conn.execute(text("""
                    UPDATE roles
                    SET hiring_manager = :default_hm
                    WHERE hiring_manager IS NULL
                """), {"default_hm": DEFAULT_HIRING_MANAGER})
                conn.commit()
                updated_count = result.rowcount

                if verbose:
                    print(f"  ✓ Updated {updated_count} role(s) with default hiring manager")
            else:
                if verbose:
                    print("\n[2/3] No existing roles to update")

            # Step 3: Verify migration
            if verbose:
                print("\n[3/3] Verifying migration...")

            result = conn.execute(text("SELECT position, hiring_manager FROM roles"))
            rows = result.fetchall()

            all_have_hm = all(row[1] is not None for row in rows)

            if verbose:
                if all_have_hm or len(rows) == 0:
                    print("  ✓ All roles have hiring manager assigned")
                else:
                    print("  ⚠ Warning: Some roles still have NULL hiring manager")

                print("\n" + "=" * 70)
                print("MIGRATION COMPLETED SUCCESSFULLY!")
                print("=" * 70)

                if rows:
                    print(f"\nFinal state ({len(rows)} roles):")
                    for row in rows:
                        position = row[0]
                        hm = row[1] or '(NULL)'
                        print(f"  - {position}: HM = {hm}")

                print("\n✓ Your production database is now up to date")
                print("✓ The admin page should now load correctly")
                print("✓ All existing role data has been preserved")

            return True

    except Exception as e:
        print(f"\n✗ MIGRATION FAILED: {e}")
        if verbose:
            print(f"\nError details: {str(e)}")
            import traceback
            traceback.print_exc()
        return False
    finally:
        engine.dispose()


if __name__ == "__main__":
    success = migrate_database(verbose=True)
    sys.exit(0 if success else 1)
