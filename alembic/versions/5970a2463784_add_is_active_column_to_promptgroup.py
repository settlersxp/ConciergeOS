"""add is_active column to PromptGroup

Revision ID: 5970a2463784
Revises: a782e25476e4
Create Date: 2026-06-28 17:31:04.414507

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5970a2463784'
down_revision: Union[str, None] = 'a782e25476e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_active column to PromptGroup table (idempotent for SQLite)."""
    # SQLite does not support conditional DDL, so we check if column exists
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = [col['name'] for col in inspector.get_columns('PromptGroup')]
    if 'is_active' not in columns:
        op.add_column(
            'PromptGroup',
            sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'),
        )
        op.execute("UPDATE PromptGroup SET is_active = 1 WHERE is_active IS NULL")


def downgrade() -> None:
    """Remove is_active column from PromptGroup table."""
    op.drop_column('PromptGroup', 'is_active')
