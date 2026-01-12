"""add_xai_api_key_to_user_settings

Revision ID: 748f7a86fa54
Revises: 016_add_telephony_provider
Create Date: 2026-01-07 10:44:42.072541

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '748f7a86fa54'
down_revision: Union[str, Sequence[str], None] = '016_add_telephony_provider'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add xai_api_key column to user_settings table
    op.add_column(
        'user_settings',
        sa.Column('xai_api_key', sa.Text(), nullable=True, comment='xAI API key for Grok Realtime')
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove xai_api_key column from user_settings table
    op.drop_column('user_settings', 'xai_api_key')
