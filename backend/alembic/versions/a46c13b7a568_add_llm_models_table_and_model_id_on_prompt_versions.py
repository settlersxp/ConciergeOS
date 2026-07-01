"""add LLM models table and model_id on PromptVersions

Revision ID: a46c13b7a568
Revises: cf767223d567
Create Date: 2026-01-07 11:18:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'a46c13b7a568'
down_revision = 'cf767223d567'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create LLMModels table (new table, no batch needed)
    op.create_table(
        'LLMModels',
        sa.Column('model_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(200), nullable=False, unique=True),
        sa.Column('endpoint', sa.String(500), nullable=False),
        sa.Column('models_endpoint', sa.String(500), server_default='', nullable=False),
        sa.Column('model_name', sa.String(200), nullable=False),
        sa.Column('model_type', sa.String(20), nullable=True),
        sa.Column('vllm_version', sa.String(50), nullable=True),
        sa.Column('thinking_enabled', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('model_id', name='pk_llm_models'),
    )

    # Use batch mode for PromptVersions because SQLite requires table
    # recreation when adding columns with foreign key constraints
    with op.batch_alter_table('PromptVersions', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('model_id', sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_prompt_versions_model_id',
            'LLMModels',
            ['model_id'],
            ['model_id'],
            ondelete='SET NULL'
        )


def downgrade() -> None:
    with op.batch_alter_table('PromptVersions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_prompt_versions_model_id', type_='foreignkey')
        batch_op.drop_column('model_id')

    op.drop_table('LLMModels')
