"""Add provider settings to agents

Revision ID: 015_add_provider_settings
Revises: 2aeb78a98185
Create Date: 2026-01-02

Add TTS, STT, and LLM provider configuration fields to agents table.
This allows per-agent customization of voice providers instead of
relying solely on pricing tier defaults.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "015_add_provider_settings"
down_revision: Union[str, Sequence[str], None] = "2aeb78a98185"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add provider settings columns to agents table."""
    # TTS Provider Settings
    op.add_column(
        "agents",
        sa.Column(
            "tts_provider",
            sa.String(50),
            nullable=False,
            server_default="elevenlabs",
            comment="TTS provider: elevenlabs, openai, google",
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "tts_model",
            sa.String(100),
            nullable=False,
            server_default="eleven_turbo_v2_5",
            comment="TTS model (e.g., eleven_turbo_v2_5, eleven_flash_v2_5)",
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "tts_voice_id",
            sa.String(100),
            nullable=True,
            comment="ElevenLabs voice ID for custom voices",
        ),
    )

    # STT Provider Settings
    op.add_column(
        "agents",
        sa.Column(
            "stt_provider",
            sa.String(50),
            nullable=False,
            server_default="deepgram",
            comment="STT provider: deepgram, openai, google",
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "stt_model",
            sa.String(100),
            nullable=False,
            server_default="nova-3",
            comment="STT model (e.g., nova-3, whisper-1)",
        ),
    )

    # LLM Provider Settings
    op.add_column(
        "agents",
        sa.Column(
            "llm_provider",
            sa.String(50),
            nullable=False,
            server_default="openai-realtime",
            comment="LLM provider: openai-realtime, openai, anthropic, google",
        ),
    )
    op.add_column(
        "agents",
        sa.Column(
            "llm_model",
            sa.String(100),
            nullable=False,
            server_default="gpt-realtime-2025-08-28",
            comment="LLM model (e.g., gpt-4o, claude-sonnet-4-5)",
        ),
    )


def downgrade() -> None:
    """Remove provider settings columns from agents table."""
    op.drop_column("agents", "llm_model")
    op.drop_column("agents", "llm_provider")
    op.drop_column("agents", "stt_model")
    op.drop_column("agents", "stt_provider")
    op.drop_column("agents", "tts_voice_id")
    op.drop_column("agents", "tts_model")
    op.drop_column("agents", "tts_provider")
