"""Add is_active column to PromptGroupItem

Revision ID: add_is_active_to_item
Revises: 5970a2463784
Create Date: 2026-01-07
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_is_active_to_promptgroup_item'
down_revision = 'aaa_add_chain_page_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_active column to PromptGroupItem with default True
    op.add_column(
        'PromptGroupItem',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1', comment='Enable or disable this step in the chain')
    )


def downgrade() -> None:
    op.drop_column('PromptGroupItem', 'is_active')