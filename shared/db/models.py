import enum
import uuid
from typing import Any
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Enum,
    ForeignKey,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class PRStatus(str, enum.Enum):
    pending = "pending"
    reviewing = "reviewing"
    completed = "completed"
    failed = "failed"


class SeverityLevel(str, enum.Enum):
    error = "error"
    warning = "warning"
    info = "info"
    suggestion = "suggestion"


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_full_name = Column(String, nullable=False)
    pr_number = Column(Integer, nullable=False)
    head_sha = Column(String(40), nullable=False)
    base_sha = Column(String(40), nullable=False)
    author = Column(String, nullable=False)
    installation_id = Column(Integer, nullable=True)
    status: Any = Column(Enum(PRStatus), default=PRStatus.pending, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    findings = relationship(
        "Finding", back_populates="pull_request", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("repo_full_name", "head_sha", name="uix_pr_repo_head_sha"),
    )


class Finding(Base):
    __tablename__ = "findings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pr_id = Column(UUID(as_uuid=True), ForeignKey("pull_requests.id"), nullable=False)
    agent = Column(
        String, nullable=False
    )  # "static", "security", "style", "architecture"
    file_path = Column(String, nullable=False)
    line_number = Column(Integer, nullable=True)
    severity: Any = Column(Enum(SeverityLevel), nullable=False)
    message = Column(Text, nullable=False)
    suggestion = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    pull_request = relationship("PullRequest", back_populates="findings")


class StylePattern(Base):
    __tablename__ = "style_patterns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    repo_full_name = Column(String, nullable=False)
    pattern_type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    frequency = Column(Integer, default=1, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "repo_full_name", "pattern_type", name="uix_style_pattern_repo_type"
        ),
    )
