"""add_prompt_group_tables

Revision ID: a782e25476e4
Revises: d3f04a295bc8
Create Date: 2026-06-28 16:14:59.018736

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a782e25476e4'
down_revision: Union[str, None] = 'd3f04a295bc8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create PromptGroup, PromptGroupItem, PromptGroupSchedule, PromptGroupResult tables."""

    op.create_table(
        "PromptGroup",
        sa.Column("group_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "PromptGroupItem",
        sa.Column("item_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("group_id", sa.Integer, sa.ForeignKey("PromptGroup.group_id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("prompt_id", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.Integer, nullable=False),
    )

    op.create_table(
        "PromptGroupSchedule",
        sa.Column("schedule_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("group_id", sa.Integer, sa.ForeignKey("PromptGroup.group_id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_at", sa.DateTime, nullable=False),
        sa.Column("active", sa.Boolean, server_default="1"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "PromptGroupResult",
        sa.Column("result_id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("group_id", sa.Integer, sa.ForeignKey("PromptGroup.group_id", ondelete="CASCADE"), nullable=False),
        sa.Column("executed_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("scheduled", sa.Boolean, server_default="0"),
        sa.Column("result_file", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("error_message", sa.Text, nullable=True),
    )


def downgrade() -> None:
    """Drop PromptGroup tables."""
    op.drop_table("PromptGroupResult")
    op.drop_table("PromptGroupSchedule")
    op.drop_table("PromptGroupItem")
    op.drop_table("PromptGroup")