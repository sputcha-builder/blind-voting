"""
JSON file operations - the original storage method.
These functions work with JSON files: votes.json, roles.json, config.json
"""
import json
import os

VOTES_FILE = 'votes.json'
CONFIG_FILE = 'config.json'
ROLES_FILE = 'roles.json'


def load_votes():
    """Load votes from JSON file"""
    if os.path.exists(VOTES_FILE):
        with open(VOTES_FILE, 'r') as f:
            return json.load(f)
    return {'votes': []}


def save_votes(data):
    """Save votes to JSON file"""
    with open(VOTES_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def load_config():
    """Load configuration from JSON file"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Migrate old format to new format if needed
            if 'candidate_name' in config and 'candidates' not in config:
                # Old format - convert to new
                if config.get('candidate_name'):
                    config['candidates'] = [{'id': '1', 'name': config['candidate_name']}]
                else:
                    config['candidates'] = []
                del config['candidate_name']
            return config
    return {
        'position': '',
        'candidates': [],
        'allowed_emails': [],
        'is_configured': False
    }


def save_config(data):
    """Save configuration to JSON file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def load_roles():
    """Load roles from JSON file"""
    if os.path.exists(ROLES_FILE):
        with open(ROLES_FILE, 'r') as f:
            return json.load(f)
    return {'roles': []}


def save_roles(data):
    """Save roles to JSON file"""
    with open(ROLES_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_role_by_id(role_id):
    """Get a specific role by ID"""
    roles_data = load_roles()
    for role in roles_data['roles']:
        if role['id'] == role_id:
            return role
    return None
