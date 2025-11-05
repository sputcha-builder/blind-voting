"""
Storage abstraction layer.
Routes between JSON files (local) and PostgreSQL (production) based on environment variable.

Usage in app.py:
    from storage import load_votes, save_votes, load_roles, save_roles, etc.

Environment Variables:
    DATABASE_URL - If set, uses PostgreSQL. If not set, uses JSON files.
"""
import os

# Determine storage backend based on environment
USE_DATABASE = os.getenv('DATABASE_URL') is not None

if USE_DATABASE:
    print("Using PostgreSQL database for storage")
    # Import all functions from db_operations
    from db_operations import (
        load_votes,
        save_votes,
        load_config,
        save_config,
        load_roles,
        save_roles,
        get_role_by_id,
        save_role,
        save_vote,
        delete_role
    )
    # Also export database initialization function
    from database import init_db
else:
    print("Using JSON files for storage")
    # Import all functions from json_operations
    from json_operations import (
        load_votes,
        save_votes,
        load_config,
        save_config,
        load_roles,
        save_roles,
        get_role_by_id
    )

    # JSON doesn't have these functions, so create dummy implementations
    def save_role(role_data):
        """Save a single role - JSON version updates the entire roles file"""
        roles_data = load_roles()
        # Find and update or append
        role_id = role_data['id']
        found = False
        for i, role in enumerate(roles_data['roles']):
            if role['id'] == role_id:
                roles_data['roles'][i] = role_data
                found = True
                break
        if not found:
            roles_data['roles'].append(role_data)
        save_roles(roles_data)
        return role_data

    def save_vote(vote_data):
        """Save a single vote - JSON version updates the entire votes file"""
        votes_data = load_votes()
        # Find and update or append
        found = False
        for i, vote in enumerate(votes_data['votes']):
            if (vote['voter'].lower() == vote_data['voter'].lower() and
                vote['candidate_id'] == vote_data['candidate_id'] and
                vote.get('role_id') == vote_data.get('role_id')):
                votes_data['votes'][i] = vote_data
                found = True
                break
        if not found:
            votes_data['votes'].append(vote_data)
        save_votes(votes_data)

    def delete_role(role_id):
        """Delete a role - JSON version"""
        roles_data = load_roles()
        initial_length = len(roles_data['roles'])
        roles_data['roles'] = [r for r in roles_data['roles'] if r['id'] != role_id]
        save_roles(roles_data)
        return len(roles_data['roles']) < initial_length

    def init_db():
        """No-op for JSON storage"""
        pass


# Export all functions
__all__ = [
    'USE_DATABASE',
    'load_votes',
    'save_votes',
    'save_vote',
    'load_config',
    'save_config',
    'load_roles',
    'save_roles',
    'save_role',
    'get_role_by_id',
    'delete_role',
    'init_db'
]
