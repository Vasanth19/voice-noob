"""Pipecat Pipeline Session for STT -> LLM -> TTS voice processing.

This module provides an alternative to OpenAI Realtime for voice agent calls,
using a traditional pipeline approach with separate STT, LLM, and TTS services.
"""

import asyncio
import json
import types
from typing import Any
from uuid import UUID

import structlog
from fastapi import WebSocket
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.google.stt import GoogleSTTService
from pipecat.services.google.tts import GoogleTTSService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.integrations import get_workspace_integrations
from app.core.auth import user_id_to_uuid
from app.models.user_settings import UserSettings
from app.services.tools.registry import ToolRegistry

logger = structlog.get_logger(__name__)


class PipecatPipelineSession:
    """Pipeline session using STT -> LLM -> TTS flow.

    This provides an alternative to GPTRealtimeSession for non-premium tiers,
    allowing use of ElevenLabs voices and Deepgram transcription.
    """

    def __init__(
        self,
        db: AsyncSession,
        user_id: int,
        agent_config: dict[str, Any],
        session_id: str,
        workspace_id: UUID | None = None,
    ):
        """Initialize pipeline session.

        Args:
            db: Database session for loading API keys
            user_id: User ID (integer)
            agent_config: Agent configuration dict with all settings
            session_id: Unique session ID for logging
            workspace_id: Optional workspace UUID for API key isolation
        """
        self.db = db
        self.user_id = user_id
        self.user_id_uuid = user_id_to_uuid(user_id)  # UUID for integrations lookup
        self.agent_config = agent_config
        self.session_id = session_id
        self.workspace_id = workspace_id
        self.api_keys: dict[str, str] = {}
        self.transcript: list[dict[str, Any]] = []
        self._pipeline_task: PipelineTask | None = None
        self._runner: PipelineRunner | None = None
        self.tool_registry: ToolRegistry | None = None

        self.logger = logger.bind(
            component="pipecat_pipeline",
            session_id=session_id,
            user_id=str(user_id),
            workspace_id=str(workspace_id) if workspace_id else None,
        )

    async def __aenter__(self) -> "PipecatPipelineSession":
        """Load API keys and initialize tool registry on context entry."""
        self.api_keys = await self._load_api_keys()

        # Load integrations for tool registry
        integrations: dict[str, Any] = {}
        if self.workspace_id:
            integrations = await get_workspace_integrations(
                self.user_id_uuid, self.workspace_id, self.db
            )

        # Initialize tool registry
        self.tool_registry = ToolRegistry(
            self.db,
            self.user_id,
            integrations=integrations,
            workspace_id=self.workspace_id,
        )

        self.logger.info(
            "pipeline_session_initialized",
            has_keys=list(self.api_keys.keys()),
            integrations=list(integrations.keys()),
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Cleanup on context exit."""
        if self._pipeline_task:
            await self._pipeline_task.cancel()
        if self.tool_registry:
            await self.tool_registry.close()
        self.logger.info(
            "pipeline_session_cleanup_completed",
            transcript_entries=len(self.transcript),
        )

    async def _load_api_keys(self) -> dict[str, str]:
        """Load API keys from user settings.

        Returns:
            Dict with api keys: openai, deepgram, elevenlabs, google
        """
        from app.core.auth import user_id_to_uuid

        user_uuid = user_id_to_uuid(self.user_id)

        # Build query conditions
        conditions = [UserSettings.user_id == user_uuid]
        if self.workspace_id:
            conditions.append(UserSettings.workspace_id == self.workspace_id)
        else:
            conditions.append(UserSettings.workspace_id.is_(None))

        result = await self.db.execute(select(UserSettings).where(*conditions))
        settings = result.scalar_one_or_none()

        if not settings:
            self.logger.warning("no_user_settings_found")
            return {}

        keys = {}
        if settings.openai_api_key:
            keys["openai"] = settings.openai_api_key
        if settings.deepgram_api_key:
            keys["deepgram"] = settings.deepgram_api_key
        if settings.elevenlabs_api_key:
            keys["elevenlabs"] = settings.elevenlabs_api_key
        # Google uses GOOGLE_APPLICATION_CREDENTIALS env var or similar
        # For now, we'll use openai key as fallback for google services

        return keys

    def _create_stt_service(self) -> DeepgramSTTService | GoogleSTTService:
        """Create STT service based on agent config.

        Returns:
            Configured STT service instance
        """
        provider = self.agent_config.get("stt_provider", "deepgram")
        model = self.agent_config.get("stt_model", "nova-3")
        language = self.agent_config.get("language", "en-US")

        self.logger.info("creating_stt_service", provider=provider, model=model)

        if provider == "deepgram":
            if "deepgram" not in self.api_keys:
                raise ValueError("Deepgram API key not configured")
            return DeepgramSTTService(
                api_key=self.api_keys["deepgram"],
                model=model,
                language=language,
            )
        if provider == "google":
            return GoogleSTTService(
                language_code=language,
            )
        raise ValueError(f"Unsupported STT provider: {provider}")

    def _create_tts_service(self) -> ElevenLabsTTSService | GoogleTTSService:
        """Create TTS service based on agent config.

        Returns:
            Configured TTS service instance
        """
        provider = self.agent_config.get("tts_provider", "elevenlabs")
        model = self.agent_config.get("tts_model", "eleven_turbo_v2_5")
        voice_id = self.agent_config.get("tts_voice_id", "21m00Tcm4TlvDq8ikWAM")  # Rachel

        self.logger.info("creating_tts_service", provider=provider, model=model, voice_id=voice_id)

        if provider == "elevenlabs":
            if "elevenlabs" not in self.api_keys:
                raise ValueError("ElevenLabs API key not configured")
            return ElevenLabsTTSService(
                api_key=self.api_keys["elevenlabs"],
                voice_id=voice_id,
                model=model,
            )
        if provider == "google":
            language = self.agent_config.get("language", "en-US")
            return GoogleTTSService(
                language_code=language,
            )
        raise ValueError(f"Unsupported TTS provider: {provider}")

    def _create_llm_service(self) -> OpenAILLMService | GoogleLLMService:
        """Create LLM service based on agent config.

        Returns:
            Configured LLM service instance
        """
        provider = self.agent_config.get("llm_provider", "openai")
        model = self.agent_config.get("llm_model", "gpt-4o")
        temperature = self.agent_config.get("temperature", 0.7)

        self.logger.info("creating_llm_service", provider=provider, model=model)

        if provider in ("openai", "openai-realtime"):
            # For pipeline mode, use standard OpenAI (not realtime)
            if "openai" not in self.api_keys:
                raise ValueError("OpenAI API key not configured")
            return OpenAILLMService(
                api_key=self.api_keys["openai"],
                model=model if "realtime" not in model else "gpt-4o",
                params=OpenAILLMService.InputParams(temperature=temperature),
            )
        if provider == "google":
            model_name = model if model != "built-in" else "gemini-2.0-flash-exp"
            # Google LLM uses GOOGLE_API_KEY env var if api_key not provided
            return GoogleLLMService(
                api_key=self.api_keys.get("google", ""),  # Falls back to env var
                model=model_name,
                params=GoogleLLMService.InputParams(temperature=temperature),
            )
        if provider == "cerebras":
            # Cerebras uses OpenAI-compatible API
            # TODO: Add Cerebras-specific implementation
            self.logger.warning("cerebras_fallback_to_openai")
            if "openai" not in self.api_keys:
                raise ValueError("OpenAI API key not configured (fallback from Cerebras)")
            return OpenAILLMService(
                api_key=self.api_keys["openai"],
                model="gpt-4o",
                params=OpenAILLMService.InputParams(temperature=temperature),
            )
        raise ValueError(f"Unsupported LLM provider: {provider}")

    async def _register_tools(
        self, llm: OpenAILLMService | GoogleLLMService
    ) -> list[dict[str, Any]]:
        """Register tool handlers with the LLM service.

        Args:
            llm: The LLM service to register tools with

        Returns:
            List of tool definitions for the LLM context
        """
        if not self.tool_registry:
            return []

        enabled_tools = self.agent_config.get("enabled_tools", [])
        if not enabled_tools:
            self.logger.info("no_tools_enabled")
            return []

        # Get tool definitions
        raw_tools = self.tool_registry.get_all_tool_definitions(enabled_tools)
        if not raw_tools:
            self.logger.info("no_tool_definitions_found")
            return []

        # Convert from GPT Realtime format (flat) to OpenAI Chat API format (nested)
        tools = []
        for tool in raw_tools:
            if "function" in tool:
                # Already in Chat API format
                tools.append(tool)
            elif "name" in tool and "parameters" in tool:
                # Convert from Realtime format to Chat API format
                tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool["name"],
                            "description": tool.get("description", ""),
                            "parameters": tool["parameters"],
                        },
                    }
                )
            else:
                self.logger.warning("skipping_invalid_tool", tool=tool)

        self.logger.info("registering_tools", count=len(tools))

        # Register a catch-all function handler for all tools
        async def handle_function_call(params: FunctionCallParams) -> None:
            """Handle function calls from the LLM."""
            function_name = params.function_name
            arguments = dict(params.arguments)

            self.logger.info(
                "function_call_received",
                function_name=function_name,
                arguments=arguments,
            )

            try:
                # Execute tool via registry
                if self.tool_registry:
                    result = await self.tool_registry.execute_tool(function_name, arguments)
                else:
                    result = {"success": False, "error": "Tool registry not initialized"}

                self.logger.info(
                    "function_call_completed",
                    function_name=function_name,
                    success=result.get("success", False),
                )

                # Return result to LLM
                await params.result_callback(json.dumps(result))

            except Exception as e:
                self.logger.exception(
                    "function_call_error", function_name=function_name, error=str(e)
                )
                await params.result_callback(json.dumps({"success": False, "error": str(e)}))

        # Register catch-all handler (None means handle all functions)
        llm.register_function(None, handle_function_call)

        return tools

    async def run(
        self,
        websocket: WebSocket,
        stream_sid: str,
        call_sid: str,
    ) -> None:
        """Run the pipeline for a call.

        Args:
            websocket: FastAPI WebSocket connection from Twilio
            stream_sid: Twilio Stream SID
            call_sid: Twilio Call SID
        """
        self.logger.info("pipeline_starting", stream_sid=stream_sid, call_sid=call_sid)

        try:
            # Create Twilio serializer for audio format conversion (mulaw 8kHz)
            # Disable auto_hang_up since we handle hangup separately
            serializer = TwilioFrameSerializer(
                stream_sid=stream_sid,
                params=TwilioFrameSerializer.InputParams(auto_hang_up=False),
            )

            # Create WebSocket transport with VAD for interruption detection
            transport = FastAPIWebsocketTransport(
                websocket=websocket,
                params=FastAPIWebsocketParams(
                    audio_in_enabled=True,
                    audio_out_enabled=True,
                    add_wav_header=False,
                    serializer=serializer,
                    vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.3)),
                ),
            )

            # Create services
            stt = self._create_stt_service()
            tts = self._create_tts_service()
            llm = self._create_llm_service()

            # Get tool definitions and register handlers
            tools = await self._register_tools(llm)

            # Create context with system prompt and tools
            system_prompt = self.agent_config.get(
                "system_prompt", "You are a helpful voice assistant."
            )
            messages = [{"role": "system", "content": system_prompt}]
            context = OpenAILLMContext(messages=messages, tools=tools if tools else None)
            context_aggregator = llm.create_context_aggregator(context)

            # Build pipeline: input -> STT -> context -> LLM -> TTS -> output
            pipeline = Pipeline(
                [
                    transport.input(),
                    stt,
                    context_aggregator.user(),
                    llm,
                    tts,
                    transport.output(),
                    context_aggregator.assistant(),
                ]
            )

            # Create task and runner
            self._pipeline_task = PipelineTask(
                pipeline,
                params=PipelineParams(
                    allow_interruptions=True,
                    enable_metrics=True,
                ),
            )
            self._runner = PipelineRunner()

            # Handle initial greeting if configured
            initial_greeting = self.agent_config.get("initial_greeting")
            if initial_greeting:
                self.logger.info("sending_initial_greeting", greeting=initial_greeting[:50])
                # Send greeting directly to TTS (bypassing LLM)
                await self._pipeline_task.queue_frame(TextFrame(text=initial_greeting))

            self.logger.info(
                "pipeline_running",
                stt_provider=self.agent_config.get("stt_provider"),
                tts_provider=self.agent_config.get("tts_provider"),
                llm_provider=self.agent_config.get("llm_provider"),
            )

            # Run the pipeline
            await self._runner.run(self._pipeline_task)

            # Extract transcript from context after pipeline ends
            self._capture_transcript_from_context(context)

        except Exception as e:
            self.logger.exception("pipeline_error", error=str(e))
            raise
        finally:
            self.logger.info("pipeline_stopped")

    def _capture_transcript_from_context(self, context: OpenAILLMContext) -> None:
        """Extract transcript entries from the LLM context.

        Args:
            context: The OpenAI LLM context containing conversation messages
        """
        try:
            messages = context.get_messages()
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")

                # Skip system messages and empty content
                if role == "system" or not content:
                    continue

                # Handle content that might be a string or list of parts
                text_content = ""
                if isinstance(content, str):
                    text_content = content
                elif isinstance(content, list):
                    # Extract text from content parts
                    for part in content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            text_content += part.get("text", "")
                        elif isinstance(part, str):
                            text_content += part

                # Map role to user/assistant
                if role in ("user", "assistant") and text_content:
                    self.add_transcript_entry(role, text_content)

            self.logger.info(
                "transcript_captured_from_context",
                entry_count=len(self.transcript),
            )
        except Exception as e:
            self.logger.warning("transcript_capture_failed", error=str(e))

    def get_transcript(self) -> str:
        """Get the full transcript as formatted text.

        Returns:
            Formatted transcript string (matching GPTRealtimeSession interface)
        """
        lines = []
        for entry in self.transcript:
            role_label = "User" if entry.get("role") == "user" else "Assistant"
            lines.append(f"[{role_label}]: {entry.get('content', '')}")
        return "\n\n".join(lines)

    def get_transcript_entries(self) -> list[dict[str, Any]]:
        """Get transcript entries as list of dicts.

        Returns:
            List of transcript entry dictionaries with role, content, timestamp
        """
        return self.transcript

    def add_transcript_entry(self, role: str, content: str) -> None:
        """Add an entry to the transcript.

        Args:
            role: 'user' or 'assistant'
            content: The text content
        """
        self.transcript.append(
            {
                "role": role,
                "content": content,
                "timestamp": asyncio.get_event_loop().time(),
            }
        )
