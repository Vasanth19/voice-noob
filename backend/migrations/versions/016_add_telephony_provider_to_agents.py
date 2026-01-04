"""Add telephony_provider to agents

Revision ID: 016_add_telephony_provider
Revises: 015_add_provider_settings
Create Date: 2026-01-02

Add telephony_provider field to agents table to persist the user's
choice between Telnyx and Twilio for phone calls.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "016_add_telephony_provider"
down_revision: Union[str, Sequence[str], None] = "015_add_provider_settings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add telephony_provider column to agents table."""
    op.add_column(
        "agents",
        sa.Column(
            "telephony_provider",
            sa.String(20),
            nullable=False,
            server_default="telnyx",
            comment="Telephony provider: telnyx or twilio",
        ),
    )


def downgrade() -> None:
    """Remove telephony_provider column from agents table."""
    op.drop_column("agents", "telephony_provider")
