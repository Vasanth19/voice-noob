"""add user_integrations table

Revision ID: e665adac48b0
Revises: 91acf3ffe096
Create Date: 2025-11-28 03:52:03.966199

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e665adac48b0'
down_revision: Union[str, Sequence[str], None] = '91acf3ffe096'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - skipped (table already created in a7176cbf6e3a)."""
    pass


def downgrade() -> None:
    """Downgrade schema - skipped (table managed by a7176cbf6e3a)."""
    pass
