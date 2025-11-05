"""
Database operations for PostgreSQL.
These functions mirror the JSON file operations but use the database instead.
All functions return the same data structures as the JSON equivalents for compatibility.
"""
from database import db_session, get_session
from models import Role, Candidate, AllowedVoter, Vote, Config
from datetime import datetime
import uuid


# ============= VOTES OPERATIONS =============

def load_votes():
    """
    Load all votes from the database.
    Returns: {'votes': [list of vote dicts]}
    """
    with db_session() as session:
        votes = session.query(Vote).all()
        return {
            'votes': [vote.to_dict() for vote in votes]
        }


def save_votes(data):
    """
    Save votes to the database.
    Note: This replaces all existing votes (for compatibility with JSON behavior).
    In practice, votes are added individually via save_vote().

    Args:
        data: {'votes': [list of vote dicts]}
    """
    with db_session() as session:
        # Clear existing votes
        session.query(Vote).delete()

        # Add new votes
        for vote_data in data.get('votes', []):
            vote = Vote(
                voter=vote_data['voter'],
                candidate_id=vote_data['candidate_id'],
                candidate_name=vote_data.get('candidate_name'),
                role_id=uuid.UUID(vote_data['role_id']) if vote_data.get('role_id') else None,
                role_position=vote_data.get('role_position'),
                choice=vote_data['choice'],
                feedback=vote_data.get('feedback'),
                timestamp=datetime.fromisoformat(vote_data['timestamp']) if vote_data.get('timestamp') else datetime.utcnow()
            )
            session.add(vote)


def save_vote(vote_data):
    """
    Save or update a single vote.
    Replaces existing vote if voter already voted for this candidate in this role.

    Args:
        vote_data: dict with voter, candidate_id, role_id, choice, feedback, etc.
    """
    with db_session() as session:
        # Check if vote already exists
        existing_vote = session.query(Vote).filter_by(
            voter=vote_data['voter'],
            candidate_id=vote_data['candidate_id'],
            role_id=uuid.UUID(vote_data['role_id']) if vote_data.get('role_id') else None
        ).first()

        if existing_vote:
            # Update existing vote
            existing_vote.choice = vote_data['choice']
            existing_vote.feedback = vote_data.get('feedback')
            existing_vote.timestamp = datetime.utcnow()
            existing_vote.candidate_name = vote_data.get('candidate_name')
            existing_vote.role_position = vote_data.get('role_position')
        else:
            # Create new vote
            vote = Vote(
                voter=vote_data['voter'],
                candidate_id=vote_data['candidate_id'],
                candidate_name=vote_data.get('candidate_name'),
                role_id=uuid.UUID(vote_data['role_id']) if vote_data.get('role_id') else None,
                role_position=vote_data.get('role_position'),
                choice=vote_data['choice'],
                feedback=vote_data.get('feedback'),
                timestamp=datetime.utcnow()
            )
            session.add(vote)


# ============= ROLES OPERATIONS =============

def load_roles():
    """
    Load all roles from the database.
    Returns: {'roles': [list of role dicts with candidates and allowed_emails]}
    """
    with db_session() as session:
        roles = session.query(Role).all()
        return {
            'roles': [role.to_dict() for role in roles]
        }


def save_roles(data):
    """
    Save roles to the database.
    Note: This replaces all existing roles (for compatibility with JSON behavior).
    Use save_role() for individual role operations.

    Args:
        data: {'roles': [list of role dicts]}
    """
    with db_session() as session:
        # Clear existing roles (cascades to candidates and allowed_voters)
        session.query(Role).delete()

        # Add new roles
        for role_data in data.get('roles', []):
            role = Role(
                id=uuid.UUID(role_data['id']) if 'id' in role_data else uuid.uuid4(),
                position=role_data['position'],
                status=role_data.get('status', 'active'),
                created_at=datetime.fromisoformat(role_data['created_at']) if role_data.get('created_at') else datetime.utcnow(),
                updated_at=datetime.fromisoformat(role_data['updated_at']) if role_data.get('updated_at') else None
            )

            # Add candidates
            for candidate_data in role_data.get('candidates', []):
                candidate = Candidate(
                    role=role,
                    candidate_id=candidate_data['id'],
                    name=candidate_data['name']
                )
                session.add(candidate)

            # Add allowed voters
            for email in role_data.get('allowed_emails', []):
                voter = AllowedVoter(
                    role=role,
                    email=email
                )
                session.add(voter)

            session.add(role)


def save_role(role_data):
    """
    Save or update a single role.

    Args:
        role_data: dict with id, position, candidates, allowed_emails, status, etc.
    Returns:
        The saved role as a dict
    """
    with db_session() as session:
        role_id = uuid.UUID(role_data['id']) if 'id' in role_data else uuid.uuid4()

        # Check if role exists
        existing_role = session.query(Role).filter_by(id=role_id).first()

        if existing_role:
            # Update existing role
            existing_role.position = role_data['position']
            existing_role.status = role_data.get('status', 'active')
            existing_role.updated_at = datetime.utcnow()

            # Update candidates (delete old, add new)
            session.query(Candidate).filter_by(role_id=role_id).delete()
            for candidate_data in role_data.get('candidates', []):
                candidate = Candidate(
                    role=existing_role,
                    candidate_id=candidate_data['id'],
                    name=candidate_data['name']
                )
                session.add(candidate)

            # Update allowed voters (delete old, add new)
            session.query(AllowedVoter).filter_by(role_id=role_id).delete()
            for email in role_data.get('allowed_emails', []):
                voter = AllowedVoter(
                    role=existing_role,
                    email=email
                )
                session.add(voter)

            role = existing_role
        else:
            # Create new role
            role = Role(
                id=role_id,
                position=role_data['position'],
                status=role_data.get('status', 'active'),
                created_at=datetime.utcnow()
            )

            # Add candidates
            for candidate_data in role_data.get('candidates', []):
                candidate = Candidate(
                    role=role,
                    candidate_id=candidate_data['id'],
                    name=candidate_data['name']
                )
                session.add(candidate)

            # Add allowed voters
            for email in role_data.get('allowed_emails', []):
                voter = AllowedVoter(
                    role=role,
                    email=email
                )
                session.add(voter)

            session.add(role)

        session.flush()  # Ensure relationships are loaded
        return role.to_dict()


def get_role_by_id(role_id):
    """
    Get a specific role by ID.

    Args:
        role_id: UUID string or UUID object
    Returns:
        Role dict or None if not found
    """
    with db_session() as session:
        if isinstance(role_id, str):
            role_id = uuid.UUID(role_id)

        role = session.query(Role).filter_by(id=role_id).first()
        return role.to_dict() if role else None


def delete_role(role_id):
    """
    Delete a role by ID.
    Only allowed if the role has no votes (enforced by database constraint).

    Args:
        role_id: UUID string
    Returns:
        True if deleted, False if not found
    """
    with db_session() as session:
        if isinstance(role_id, str):
            role_id = uuid.UUID(role_id)

        role = session.query(Role).filter_by(id=role_id).first()
        if role:
            session.delete(role)
            return True
        return False


# ============= CONFIG OPERATIONS (Legacy) =============

def load_config():
    """
    Load configuration from the database.
    Returns: dict with position, candidates, allowed_emails, is_configured

    Note: This is legacy support. New apps should use roles instead.
    """
    with db_session() as session:
        config = session.query(Config).first()

        if not config:
            return {
                'position': '',
                'candidates': [],
                'allowed_emails': [],
                'is_configured': False
            }

        # Get first role's data if it exists (for backward compatibility)
        first_role = session.query(Role).first()

        if first_role:
            return {
                'position': first_role.position,
                'candidates': [c.to_dict() for c in first_role.candidates],
                'allowed_emails': [v.email for v in first_role.allowed_voters],
                'is_configured': config.is_configured
            }

        return config.to_dict()


def save_config(config_data):
    """
    Save configuration to the database.

    Args:
        config_data: dict with position, candidates, allowed_emails, is_configured
    """
    with db_session() as session:
        config = session.query(Config).first()

        if not config:
            config = Config(
                id=1,
                position=config_data.get('position', ''),
                is_configured=config_data.get('is_configured', False)
            )
            session.add(config)
        else:
            config.position = config_data.get('position', '')
            config.is_configured = config_data.get('is_configured', False)
