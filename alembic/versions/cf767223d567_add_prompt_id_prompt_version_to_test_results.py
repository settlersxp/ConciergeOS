"""add_prompt_id_prompt_version_to_test_results

Revision ID: cf767223d567
Revises: 64e9fa0ce73b
Create Date: 2026-06-30 09:09:07.123456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cf767223d567'
down_revision: Union[str, None] = '64e9fa0ce73b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add prompt_id column to test_results table
    op.add_column('test_results', sa.Column('prompt_id', sa.String(), nullable=True))
    # Add prompt_version column to test_results table
    op.add_column('test_results', sa.Column('prompt_version', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('test_results', 'prompt_version')
    op.drop_column('test_results', 'prompt_id')