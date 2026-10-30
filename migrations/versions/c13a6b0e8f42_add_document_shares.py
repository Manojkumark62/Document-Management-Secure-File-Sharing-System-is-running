"""add document shares

Revision ID: c13a6b0e8f42
Revises: 5badb0dc91ee
Create Date: 2026-10-27 11:42:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c13a6b0e8f42"
down_revision: Union[str, Sequence[str], None] = "5badb0dc91ee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_shares",
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("shared_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shared_by"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id", "user_id"),
    )
    op.create_index("ix_document_shares_user_id", "document_shares", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_document_shares_user_id", table_name="document_shares")
    op.drop_table("document_shares")
