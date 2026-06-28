"""add_schedule_type_to_promptgroupschedule

Revision ID: 64e9fa0ce73b
Revises: 5970a2463784
Create Date: 2026-06-28 18:17:05.865672

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64e9fa0ce73b'
down_revision: Union[str, None] = '5970a2463784'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add schedule_type column to PromptGroupSchedule."""
    op.add_column(
        "PromptGroupSchedule",
        sa.Column("schedule_type", sa.String(20), nullable=True, server_default="daily"),
    )
    # Set default for existing records
    op.execute("UPDATE PromptGroupSchedule SET schedule_type = 'daily' WHERE schedule_type IS NULL")


def downgrade() -> None:
    """Remove schedule_type column from PromptGroupSchedule."""
    op.drop_column("PromptGroupSchedule", "schedule_type")
