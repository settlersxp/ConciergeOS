"""add prompt_versions table

Revision ID: dae900574783
Revises: 
Create Date: 2026-06-27 08:17:33.730254

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dae900574783'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _get_default_prompts():  # noqa: C901
    """Return seed data for default prompts as list of dicts.

    Each dict has the column names and values for one PromptVersion row.
    """
    return [
        {
            "prompt_id": "guest-search",
            "version": 1,
            "name": "Guest Search v1",
            "intention": """\
You are a helpful hotel concierge assistant with access to database query tools.

When providing information about a guest, always use the following markdown structure:

### Guest [Number] (ID: [ID])
* **Full Name:** [First name] [Last name]
* **Date of Birth:** [YYYY-MM-DD]
* **Special Guest:** [Yes/No]
* **Special Preferences:** [Preferences or 'None']
* **Reservations:**
  1. **Reservation ID:** [ID]
     * **Room id:** [ID]
     * **Room:** [Room Name]
     * **Check-in:** [YYYY-MM-DD] | **Check-out:** [YYYY-MM-DD]
     * **Status:** [STATUS] | **Source:** [SOURCE]
  2. ... (continue for all reservations)
""",
            "restrictions": "",
            "output_structure": "",
            "user_prompt_template": "Please find all information about the guest named. The guest's name can have it's name translated into the following languages Arabic, Chinese, Devanagari, Japanese, Korean, Latin or Nordic. It is unclear if is the user's first name or last name. Retry once with every translated language if needed. Also bring the information about its reservations. : {customer_name}",
            "is_default": True,
            "meta_json": '{"author": "system", "migrated_from": "app/services/llm.py", "changelog": "Initial seed from hardcoded prompts"}',
        },
    ]


def upgrade() -> None:
    """Add PromptVersions table and seed default prompts."""
    op.create_table('PromptVersions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('prompt_id', sa.String(length=100), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('intention', sa.Text(), nullable=False),
        sa.Column('restrictions', sa.Text(), nullable=False),
        sa.Column('output_structure', sa.Text(), nullable=False),
        sa.Column('user_prompt_template', sa.Text(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('meta_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('prompt_id', 'version', name='uq_prompt_version')
    )

    # Seed default prompts
    bind = op.get_bind()
    for row in _get_default_prompts():
        bind.execute(
            sa.table('PromptVersions',
                sa.column('prompt_id', sa.String),
                sa.column('version', sa.Integer),
                sa.column('name', sa.String),
                sa.column('intention', sa.Text),
                sa.column('restrictions', sa.Text),
                sa.column('output_structure', sa.Text),
                sa.column('user_prompt_template', sa.Text),
                sa.column('is_default', sa.Boolean),
                sa.column('meta_json', sa.Text),
                sa.column('created_at', sa.DateTime),
                sa.column('updated_at', sa.DateTime),
            ).insert().values(**row)
        )


def downgrade() -> None:
    """Remove PromptVersions table and all data."""
    op.drop_table('PromptVersions')