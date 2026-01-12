"""Grok Realtime API service for Grok-Realtime tier voice agents."""

import json
import types
import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.integrations import get_workspace_integrations
from app.api.settings import get_user_api_keys
from app.core.auth import user_id_to_uuid
from app.services.gpt_realtime import LANGUAGE_NAMES, TranscriptEntry, build_instructions_with_language
from app.services.tools.registry import ToolRegistry

logger = structlog.get_logger()

# Voice mapping: OpenAI voice names → Grok voice names
VOICE_MAPPING = {
    "marin": "Ara",  # Professional & clear → Warm, friendly female
    "cedar": "Rex",  # Natural & conversational → Confident male
    "shimmer": "Eve",  # Energetic → Energetic female
    "alloy": "Sal",  # Neutral → Neutral, smooth
    "onyx": "Rex",  # Deep & authoritative → Confident male
    "echo": "Ara",  # Warm & engaging → Warm, friendly
    "nova": "Eve",  # Friendly & upbeat → Energetic female
    "fable": "Leo",  # Expressive → Authoritative
    "ash": "Sal",  # Clear & precise → Neutral, smooth
    "ballad": "Ara",  # Melodic → Warm
    "coral": "Ara",  # Warm & friendly → Warm, friendly
    "sage": "Sal",  # Calm & thoughtful → Neutral, smooth
    "verse": "Leo",  # Versatile → Authoritative
}


class GrokRealtimeSession:
    """Manages a Grok Realtime API session for a voice call.

    Handles:
    - WebSocket connection to xAI Grok Realtime API
    - Internal tool integration
    - Audio streaming
    - Tool call routing to internal tool handlers
    - Transcript accumulation
    """

    def __init__(
        self,
        db: AsyncSession,
        user_id: int,
        agent_config: dict[str, Any],
        session_id: str | None = None,
        workspace_id: uuid.UUID | None = None,
    ) -> None:
        """Initialize Grok Realtime session.

        Args:
            db: Database session
            user_id: User ID (int, from users.id)
            agent_config: Agent configuration (system prompt, enabled integrations, etc.)
            session_id: Optional session ID
            workspace_id: Workspace UUID (required for API key isolation)
        """
        self.db = db
        self.user_id = user_id  # int for ToolRegistry (Contact queries)
        self.user_id_uuid = user_id_to_uuid(user_id)  # UUID for UserSettings queries
        self.workspace_id = workspace_id  # For workspace-isolated API key lookup
        self.agent_config = agent_config
        self.session_id = session_id or str(uuid.uuid4())
        self.connection: Any = None
        self.tool_registry: ToolRegistry | None = None
        self.llm_service: Any = None  # GrokRealtimeLLMService from Pipecat
        # Transcript accumulation
        self._transcript_entries: list[TranscriptEntry] = []
        self._current_assistant_text: str = ""
        # Initial greeting (triggered after event loop starts to avoid race condition)
        self._pending_initial_greeting: str | None = None
        self._greeting_triggered: bool = False
        self.logger = logger.bind(
            component="grok_realtime",
            session_id=self.session_id,
            user_id=str(user_id),
            workspace_id=str(workspace_id) if workspace_id else None,
        )

    async def initialize(self) -> None:
        """Initialize the Grok Realtime session with internal tools."""
        self.logger.info("grok_realtime_session_initializing")

        # Get user's API keys from settings (uses UUID)
        # Workspace isolation: only use workspace-specific API keys, no fallback
        user_settings = await get_user_api_keys(
            self.user_id_uuid, self.db, workspace_id=self.workspace_id
        )

        # Strictly use workspace API key - no fallback to global key for billing isolation
        if not user_settings or not user_settings.xai_api_key:
            self.logger.warning("workspace_missing_xai_key", workspace_id=str(self.workspace_id))
            raise ValueError(
                "xAI API key not configured for this workspace. "
                "Please add it in Settings > Workspace API Keys."
            )
        api_key = user_settings.xai_api_key
        self.logger.info("using_workspace_xai_key")

        # Get integration credentials for the workspace
        integrations: dict[str, Any] = {}
        if self.workspace_id:
            integrations = await get_workspace_integrations(
                self.user_id_uuid, self.workspace_id, self.db
            )

        # Initialize tool registry with enabled tools and workspace context
        self.tool_registry = ToolRegistry(
            self.db, self.user_id, integrations=integrations, workspace_id=self.workspace_id
        )

        # Connect to xAI Grok Realtime API
        await self._connect_realtime_api(api_key)

        self.logger.info("grok_realtime_session_initialized")

    async def _connect_realtime_api(self, api_key: str) -> None:
        """Establish connection to xAI Grok Realtime API using Pipecat."""
        try:
            from pipecat.services.grok.realtime.events import SessionProperties, TurnDetection
            from pipecat.services.grok.realtime.llm import GrokRealtimeLLMService
        except ImportError as e:
            self.logger.error(
                "pipecat_grok_import_failed",
                error=str(e),
                hint="Install with: pip install 'pipecat-ai[grok]'",
            )
            raise ValueError(
                "Grok Realtime support not available. Please install pipecat-ai with Grok support."
            ) from e

        self.logger.info("connecting_to_grok_realtime", model="grok-2-realtime")

        try:
            # Get tool definitions from registry
            enabled_tools = self.agent_config.get("enabled_tools", [])
            chat_tools = self.tool_registry.get_all_tool_definitions(enabled_tools) if self.tool_registry else []

            # Convert Chat Completions format to Grok Realtime API format
            # (Same conversion as GPT Realtime)
            tools = []
            for tool in chat_tools:
                if tool.get("type") == "function" and "function" in tool:
                    func = tool["function"]
                    tools.append(
                        {
                            "type": "function",
                            "name": func.get("name"),
                            "description": func.get("description", ""),
                            "parameters": func.get("parameters", {"type": "object", "properties": {}}),
                        }
                    )
                else:
                    # Already in correct format or unknown format
                    tools.append(tool)

            # Get workspace timezone if available
            workspace_timezone = "UTC"
            if self.workspace_id:
                from app.models.workspace import Workspace

                result = await self.db.execute(
                    select(Workspace).where(Workspace.id == self.workspace_id)
                )
                workspace = result.scalar_one_or_none()
                if workspace and workspace.settings:
                    workspace_timezone = workspace.settings.get("timezone", "UTC")

            # Build instructions with language directive and timezone
            system_prompt = self.agent_config.get("system_prompt", "You are a helpful voice assistant.")
            language = self.agent_config.get("language", "en-US")

            # Map OpenAI voice to Grok voice
            openai_voice = self.agent_config.get("voice", "marin")
            grok_voice = self._map_voice(openai_voice)

            temperature = self.agent_config.get("temperature", 0.6)

            # Include initial greeting in instructions so AI knows what to say
            initial_greeting = self.agent_config.get("initial_greeting")
            if initial_greeting:
                system_prompt = (
                    f"{system_prompt}\n\n"
                    f"IMPORTANT - Initial Greeting: When the call first connects, "
                    f'you MUST say exactly this greeting: "{initial_greeting}"'
                )

            instructions = build_instructions_with_language(
                system_prompt, language, timezone=workspace_timezone
            )

            # Get VAD settings from agent config (same as GPT Realtime)
            turn_detection_threshold = self.agent_config.get("turn_detection_threshold", 0.7)
            turn_detection_prefix_padding_ms = self.agent_config.get(
                "turn_detection_prefix_padding_ms", 200
            )
            turn_detection_silence_duration_ms = self.agent_config.get(
                "turn_detection_silence_duration_ms", 600
            )

            # Configure session properties for Grok
            session_properties = SessionProperties(
                voice=grok_voice,
                instructions=instructions,
                turn_detection=TurnDetection(
                    type="server_vad",
                    threshold=turn_detection_threshold,
                    prefix_padding_ms=turn_detection_prefix_padding_ms,
                    silence_duration_ms=turn_detection_silence_duration_ms,
                ),
                tools=tools,
                temperature=temperature,
                # Grok uses same audio formats as OpenAI for telephony compatibility
                input_audio_format="g711_ulaw",  # 8kHz mulaw for Twilio/Telnyx
                output_audio_format="g711_ulaw",
            )

            # Create Grok Realtime service using Pipecat
            self.llm_service = GrokRealtimeLLMService(
                api_key=api_key,
                session_properties=session_properties,
                start_audio_paused=False,
            )

            self.logger.info(
                "connected_to_grok_realtime",
                tool_count=len(tools),
                voice=grok_voice,
                mapped_from=openai_voice,
            )

            # Store initial greeting for later
            if initial_greeting:
                self._pending_initial_greeting = initial_greeting
                self.logger.info(
                    "initial_greeting_pending",
                    greeting=initial_greeting[:50],
                )

        except Exception as e:
            self.logger.exception(
                "grok_realtime_connection_failed", error=str(e), error_type=type(e).__name__
            )
            raise

    def _map_voice(self, voice: str) -> str:
        """Map OpenAI voice names to Grok voice names.

        Args:
            voice: OpenAI voice name (e.g., "marin", "cedar")

        Returns:
            Grok voice name (e.g., "Ara", "Rex")
        """
        grok_voice = VOICE_MAPPING.get(voice.lower(), "Ara")
        self.logger.debug("voice_mapped", openai_voice=voice, grok_voice=grok_voice)
        return grok_voice

    async def handle_tool_call(self, tool_call: dict[str, Any]) -> dict[str, Any]:
        """Handle tool call from Grok Realtime by routing to internal tools.

        Args:
            tool_call: Tool call from Grok Realtime

        Returns:
            Tool result
        """
        if not self.tool_registry:
            return {"success": False, "error": "Tool registry not initialized"}

        tool_name = tool_call.get("name", "")
        arguments = tool_call.get("arguments", {})

        self.logger.info(
            "handling_tool_call",
            tool_name=tool_name,
            arguments=arguments,
        )

        # Execute tool via internal tool registry
        result = await self.tool_registry.execute_tool(tool_name, arguments)

        return result

    async def send_audio(self, audio_data: bytes) -> None:
        """Send audio input to Grok Realtime.

        Args:
            audio_data: PCM16 audio data (raw bytes)
        """
        if not self.llm_service:
            self.logger.error("send_audio_failed_no_connection")
            return

        try:
            # Forward audio to Pipecat's GrokRealtimeLLMService
            # The service handles the base64 encoding and WebSocket transmission
            await self.llm_service.push_audio(audio_data)
            self.logger.debug(
                "audio_sent_to_grok_realtime",
                size_bytes=len(audio_data),
            )
        except Exception as e:
            self.logger.exception("send_audio_error", error=str(e), error_type=type(e).__name__)

    def add_user_transcript(self, text: str) -> None:
        """Add a user transcript entry.

        Args:
            text: Transcribed user speech
        """
        if text.strip():
            self._transcript_entries.append(TranscriptEntry(role="user", content=text.strip()))
            self.logger.debug("user_transcript_added", text_length=len(text))

    def add_assistant_transcript(self, text: str) -> None:
        """Add an assistant transcript entry.

        Args:
            text: Assistant response text
        """
        if text.strip():
            self._transcript_entries.append(TranscriptEntry(role="assistant", content=text.strip()))
            self.logger.debug("assistant_transcript_added", text_length=len(text))

    def accumulate_assistant_text(self, delta: str) -> None:
        """Accumulate assistant text delta for transcript.

        Args:
            delta: Text delta from response event
        """
        self._current_assistant_text += delta

    def flush_assistant_text(self) -> None:
        """Flush accumulated assistant text to transcript."""
        if self._current_assistant_text.strip():
            self.add_assistant_transcript(self._current_assistant_text)
        self._current_assistant_text = ""

    def get_transcript(self) -> str:
        """Get the full transcript as formatted text.

        Returns:
            Formatted transcript string
        """
        lines = []
        for entry in self._transcript_entries:
            role_label = "User" if entry.role == "user" else "Assistant"
            lines.append(f"[{role_label}]: {entry.content}")
        return "\n\n".join(lines)

    def get_transcript_entries(self) -> list[dict[str, str]]:
        """Get transcript entries as list of dicts.

        Returns:
            List of transcript entry dictionaries
        """
        return [entry.to_dict() for entry in self._transcript_entries]

    async def cleanup(self) -> None:
        """Cleanup resources."""
        self.logger.info("grok_realtime_session_cleanup_started")

        # Flush any remaining assistant text
        self.flush_assistant_text()

        # Close Grok Realtime connection
        if self.llm_service:
            try:
                # Pipecat services may have cleanup methods
                if hasattr(self.llm_service, "cleanup"):
                    await self.llm_service.cleanup()
                elif hasattr(self.llm_service, "close"):
                    await self.llm_service.close()
                self.logger.info("grok_realtime_connection_closed")
            except Exception as e:
                self.logger.warning("connection_close_failed", error=str(e))

        # Cleanup tool registry
        if self.tool_registry:
            # No cleanup needed for internal tools
            pass

        self.logger.info(
            "grok_realtime_session_cleanup_completed",
            transcript_entries=len(self._transcript_entries),
        )

    async def __aenter__(self) -> "GrokRealtimeSession":
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        await self.cleanup()
