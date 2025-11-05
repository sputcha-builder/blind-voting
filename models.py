"""
SQLAlchemy ORM models for the blind voting system.
Maps the JSON data structures to PostgreSQL tables.
"""
from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Integer, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

Base = declarative_base()


class Role(Base):
    """
    Represents a voting role/position.
    Maps to roles.json root objects.
    """
    __tablename__ = 'roles'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    position = Column(String(255), nullable=False)
    status = Column(String(50), default='active')  # active, fulfilled, expired
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    candidates = relationship('Candidate', back_populates='role', cascade='all, delete-orphan')
    allowed_voters = relationship('AllowedVoter', back_populates='role', cascade='all, delete-orphan')
    votes = relationship('Vote', back_populates='role')

    def to_dict(self):
        """Convert to JSON-compatible dictionary"""
        return {
            'id': str(self.id),
            'position': self.position,
            'candidates': [c.to_dict() for c in self.candidates],
            'allowed_emails': [v.email for v in self.allowed_voters],
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Candidate(Base):
    """
    Represents a candidate for a role.
    Maps to roles.json -> candidates array.
    """
    __tablename__ = 'candidates'

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey('roles.id', ondelete='CASCADE'), nullable=False)
    candidate_id = Column(String(50), nullable=False)  # "1", "2", "3" from JSON
    name = Column(String(255), nullable=False)

    # Relationship
    role = relationship('Role', back_populates='candidates')

    __table_args__ = (
        UniqueConstraint('role_id', 'candidate_id', name='uq_role_candidate'),
    )

    def to_dict(self):
        """Convert to JSON-compatible dictionary"""
        return {
            'id': self.candidate_id,
            'name': self.name
        }


class AllowedVoter(Base):
    """
    Represents an allowed voter for a role.
    Maps to roles.json -> allowed_emails array.
    """
    __tablename__ = 'allowed_voters'

    id = Column(Integer, primary_key=True, autoincrement=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey('roles.id', ondelete='CASCADE'), nullable=False)
    email = Column(String(255), nullable=False)

    # Relationship
    role = relationship('Role', back_populates='allowed_voters')

    __table_args__ = (
        UniqueConstraint('role_id', 'email', name='uq_role_email'),
    )


class Vote(Base):
    """
    Represents a vote cast by a voter for a candidate.
    Maps to votes.json exactly (1:1 mapping).
    """
    __tablename__ = 'votes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    voter = Column(String(255), nullable=False)
    candidate_id = Column(String(50), nullable=False)
    candidate_name = Column(String(255))  # denormalized for performance
    role_id = Column(UUID(as_uuid=True), ForeignKey('roles.id', ondelete='RESTRICT'), nullable=False)
    role_position = Column(String(255))  # denormalized for performance
    choice = Column(String(50), nullable=False)  # "Inclined" or "Not Inclined"
    feedback = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    role = relationship('Role', back_populates='votes')

    __table_args__ = (
        UniqueConstraint('voter', 'candidate_id', 'role_id', name='uq_voter_candidate_role'),
    )

    def to_dict(self):
        """Convert to JSON-compatible dictionary"""
        return {
            'voter': self.voter,
            'candidate_id': self.candidate_id,
            'candidate_name': self.candidate_name,
            'role_id': str(self.role_id) if self.role_id else None,
            'role_position': self.role_position,
            'choice': self.choice,
            'feedback': self.feedback,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


class Config(Base):
    """
    Legacy config table for backward compatibility.
    Maps to config.json (single-row table).
    """
    __tablename__ = 'config'

    id = Column(Integer, primary_key=True, default=1)
    position = Column(String(255))
    is_configured = Column(Boolean, default=False)

    __table_args__ = (
        CheckConstraint('id = 1', name='single_row_check'),
    )

    def to_dict(self):
        """Convert to JSON-compatible dictionary"""
        return {
            'position': self.position,
            'is_configured': self.is_configured,
            'candidates': [],  # Legacy - now in candidates table
            'allowed_emails': []  # Legacy - now in allowed_voters table
        }
