"""
Database migration script to add allow_results_override column to roles table.
This script is safe to run multiple times - it checks if the column exists first.

Usage:
    python migrate_add_results_override.py

Requirements:
    - DATABASE_URL environment variable must be set
    - This is for PostgreSQL databases only
"""
import os
import sys
from sqlalchemy import create_engine, text, inspect


def check_column_exists(engine, table_name, column_name):
    """Check if a column exists in a table"""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def migrate_database(verbose=True):
    """
    Add allow_results_override column to roles table if it doesn't exist.

    Args:
        verbose: If True, print detailed output. If False, only print errors.

    Returns:
        True if migration succeeded or not needed, False if failed
    """

    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        if verbose:
            print("✗ ERROR: DATABASE_URL environment variable is not set")
            print("  This script is only needed for PostgreSQL databases.")
        return False

    if verbose:
        print("=" * 70)
        print("DATABASE MIGRATION: Add allow_results_override Column")
        print("=" * 70)
        print(f"Database: {database_url.split('@')[-1]}")  # Don't log credentials

    try:
        engine = create_engine(database_url)

        with engine.connect() as conn:
            if verbose:
                print("✓ Connected to database successfully\n")

            inspector = inspect(engine)
            tables = inspector.get_table_names()

            if 'roles' not in tables:
                if verbose:
                    print("✗ ERROR: 'roles' table does not exist in the database")
                    print("  Run the application first to create tables.")
                return False

            if verbose:
                print("✓ Found 'roles' table")

            if check_column_exists(engine, 'roles', 'allow_results_override'):
                if verbose:
                    print("✓ Column 'allow_results_override' already exists")
                    print("\nMigration not needed - database is already up to date!")
                return True

            if verbose:
                print("⚠ Column 'allow_results_override' does NOT exist - migration needed\n")

            if verbose:
                print("\n[1/2] Adding 'allow_results_override' column...")

            conn.execute(text("""
                ALTER TABLE roles
                ADD COLUMN allow_results_override BOOLEAN DEFAULT FALSE
            """))
            conn.commit()

            if verbose:
                print("  ✓ Column added successfully")

            if verbose:
                print("\n[2/2] Backfilling existing rows...")

            conn.execute(text("""
                UPDATE roles
                SET allow_results_override = FALSE
                WHERE allow_results_override IS NULL
            """))
            conn.commit()

            if verbose:
                print("  ✓ Existing rows updated")
                print("\n" + "=" * 70)
                print("MIGRATION COMPLETED SUCCESSFULLY!")
                print("=" * 70)

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
