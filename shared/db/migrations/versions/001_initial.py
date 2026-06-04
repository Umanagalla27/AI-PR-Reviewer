"""Initial migration — create pull_requests, findings, style_patterns tables.

Revision ID: 001_initial
Revises: None
Create Date: 2024-01-01 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Enums ────────────────────────────────────────────────────────────────
    from sqlalchemy.dialects.postgresql import ENUM

    pr_status_enum = ENUM(
        "pending",
        "reviewing",
        "completed",
        "failed",
        name="pr_status",
        create_type=False,
    )
    severity_enum = ENUM(
        "error",
        "warning",
        "info",
        "suggestion",
        name="finding_severity",
        create_type=False,
    )

    pr_status_enum.create(op.get_bind(), checkfirst=True)
    severity_enum.create(op.get_bind(), checkfirst=True)

    # ── pull_requests ────────────────────────────────────────────────────────
    op.create_table(
        "pull_requests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("repo_full_name", sa.String(255), nullable=False),
        sa.Column("pr_number", sa.Integer, nullable=False),
        sa.Column("head_sha", sa.String(40), nullable=False),
        sa.Column("base_sha", sa.String(40), nullable=False),
        sa.Column("author", sa.String(255), nullable=False),
        sa.Column("installation_id", sa.Integer, nullable=True),
        sa.Column(
            "status",
            pr_status_enum,
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_pull_requests_repo_full_name",
        "pull_requests",
        ["repo_full_name"],
    )
    op.create_unique_constraint(
        "uq_repo_head_sha",
        "pull_requests",
        ["repo_full_name", "head_sha"],
    )

    # ── findings ─────────────────────────────────────────────────────────────
    op.create_table(
        "findings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "pr_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pull_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent", sa.String(50), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("line_number", sa.Integer, nullable=True),
        sa.Column("severity", severity_enum, nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("suggestion", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_finding_pr_file_line",
        "findings",
        ["pr_id", "file_path", "line_number"],
    )

    # ── style_patterns ───────────────────────────────────────────────────────
    op.create_table(
        "style_patterns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("repo_full_name", sa.String(255), nullable=False),
        sa.Column("pattern_type", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("frequency", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "last_seen",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    op.create_unique_constraint(
        "uq_repo_pattern_type",
        "style_patterns",
        ["repo_full_name", "pattern_type"],
    )


def downgrade() -> None:
    op.drop_table("style_patterns")
    op.drop_table("findings")
    op.drop_table("pull_requests")

    sa.Enum(name="finding_severity").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="pr_status").drop(op.get_bind(), checkfirst=True)
