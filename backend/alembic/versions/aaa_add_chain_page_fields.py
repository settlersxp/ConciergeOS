"""Add chain page fields to PromptGroup and PromptGroupItem

Revision ID: aaa_add_chain_page_fields
Revises: a46c13b7a568
Create Date: 2026-07-01 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'aaa_add_chain_page_fields'
down_revision = 'a46c13b7a568'
branch_labels = None
depends_on = None


def upgrade():
    # Add alias column to PromptGroupItem
    op.add_column("PromptGroupItem",
        sa.Column("alias", sa.String(50), nullable=True,
                  comment="Human-readable alias for cross-step referencing"))

    # Add is_input_step column to PromptGroupItem
    op.add_column("PromptGroupItem",
        sa.Column("is_input_step", sa.Boolean, nullable=False, server_default="0",
                  comment="Mark this step as the user-input entry point for page mode"))

    # Add is_chain_page column to PromptGroup
    op.add_column("PromptGroup",
        sa.Column("is_chain_page", sa.Boolean, nullable=False, server_default="0",
                  comment="If True, this group renders as a full page"))

    # Add page_route column to PromptGroup
    op.add_column("PromptGroup",
        sa.Column("page_route", sa.String(200), nullable=True,
                  comment="URL route for chain page (e.g., /guest-intel)"))


def downgrade():
    op.drop_column("PromptGroup", "page_route")
    op.drop_column("PromptGroup", "is_chain_page")
    op.drop_column("PromptGroupItem", "is_input_step")
    op.drop_column("PromptGroupItem", "alias")