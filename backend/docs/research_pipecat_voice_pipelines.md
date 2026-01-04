# Pipecat AI Voice Pipeline Research Summary

_Generated: 2026-01-02 | Sources: 15+ | Confidence: High_

## Executive Summary

<key-findings>
- Pipecat provides a modular pipeline architecture for real-time voice AI applications with STT, LLM, and TTS services
- Twilio integration uses `TwilioFrameSerializer` with `FastAPIWebsocketTransport` for mulaw 8kHz audio handling
- Function calling is implemented via `register_function()` on LLM services with async handlers receiving `FunctionCallParams`
- Latest stable version is 0.0.96+ with significant API restructuring for transports and services
</key-findings>

## Pipeline Architecture

<overview>

### Core Components

Pipecat pipelines are built from processors that handle frames flowing through the system:

```python
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
```

### Standard Voice Pipeline Structure

```python
pipeline = Pipeline([
    transport.input(),           # Audio input from transport
    stt,                         # Speech-to-Text service
    context_aggregator.user(),   # Aggregate user context
    llm,                         # Language Model
    tts,                         # Text-to-Speech service
    transport.output(),          # Audio output to transport
    context_aggregator.assistant()  # Aggregate assistant context
])
```

</overview>

## Implementation Guide

<implementation>

### 1. Basic Pipeline with Deepgram STT + OpenAI LLM + ElevenLabs TTS

```python
import os
from dotenv import load_dotenv
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair

# Service imports - note the new module paths in 0.0.96+
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.services.openai.llm import OpenAILLMService

load_dotenv()

async def create_voice_pipeline(transport):
    """Create a complete voice pipeline."""

    # Initialize services
    stt = DeepgramSTTService(
        api_key=os.getenv("DEEPGRAM_API_KEY"),
        # Optional: configure model, language, etc.
    )

    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-4o-mini",
    )

    tts = ElevenLabsTTSService(
        api_key=os.getenv("ELEVENLABS_API_KEY"),
        voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel voice
    )

    # Create context with system prompt
    messages = [
        {
            "role": "system",
            "content": "You are a helpful voice assistant. Keep responses brief and conversational."
        }
    ]

    context = LLMContext(messages)
    context_aggregator = LLMContextAggregatorPair(context)

    # Build pipeline
    pipeline = Pipeline([
        transport.input(),
        stt,
        context_aggregator.user(),
        llm,
        tts,
        transport.output(),
        context_aggregator.assistant()
    ])

    # Create task
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
        )
    )

    return task
```

### 2. Twilio Media Streams Integration

```python
import os
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams,
)
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams

async def create_twilio_transport(websocket, call_data: dict):
    """Create transport configured for Twilio Media Streams.

    Args:
        websocket: FastAPI WebSocket connection
        call_data: Dict with stream_sid, call_sid from Twilio start event
    """

    # Create Twilio serializer for mulaw 8kHz audio conversion
    serializer = TwilioFrameSerializer(
        stream_sid=call_data["stream_sid"],
        call_sid=call_data["call_sid"],
        account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
        auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
        # Optional: auto_hang_up=True (default) to end call on EndFrame
    )

    # Create FastAPI WebSocket transport
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,  # Important for telephony
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(stop_secs=0.8)
            ),
            vad_audio_passthrough=True,
            serializer=serializer,
        ),
    )

    return transport
```

### 3. Complete Twilio WebSocket Endpoint

```python
from fastapi import FastAPI, WebSocket
from pipecat.pipeline.runner import PipelineRunner
from pipecat.runner.utils import parse_telephony_websocket

app = FastAPI()

@app.websocket("/ws/twilio")
async def twilio_media_stream(websocket: WebSocket):
    """Handle incoming Twilio Media Stream WebSocket connection."""
    await websocket.accept()

    # Parse Twilio's initial messages to get stream/call IDs
    # parse_telephony_websocket handles the connected/start events
    transport_type, call_data = await parse_telephony_websocket(websocket)

    # call_data contains:
    # - stream_id: Twilio stream SID
    # - call_id: Twilio call SID

    # Create transport
    transport = await create_twilio_transport(websocket, {
        "stream_sid": call_data["stream_id"],
        "call_sid": call_data["call_id"],
    })

    # Create pipeline task
    task = await create_voice_pipeline(transport)

    # Run the pipeline
    runner = PipelineRunner()
    await runner.run(task)
```

### 4. Function Calling / Tool Use

```python
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.frames.frames import TTSSpeakFrame

# Define tools using OpenAI function calling format
tools = [
    {
        "type": "function",
        "name": "get_weather",
        "description": "Get the current weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "City and state, e.g. San Francisco, CA"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"],
                    "description": "Temperature unit"
                }
            },
            "required": ["location"]
        }
    },
    {
        "type": "function",
        "name": "book_appointment",
        "description": "Book an appointment for the caller",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Appointment date in YYYY-MM-DD format"
                },
                "time": {
                    "type": "string",
                    "description": "Appointment time in HH:MM format"
                },
                "service": {
                    "type": "string",
                    "description": "Type of service requested"
                }
            },
            "required": ["date", "time", "service"]
        }
    },
    {
        "type": "function",
        "name": "end_call",
        "description": "End the phone call when the conversation is complete",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for ending the call"
                }
            }
        }
    }
]

# Define async function handlers
async def get_weather(params: FunctionCallParams):
    """Handle weather lookup function call."""
    location = params.arguments.get("location", "Unknown")
    unit = params.arguments.get("unit", "fahrenheit")

    # Simulate weather API call
    weather_data = {
        "location": location,
        "temperature": 72 if unit == "fahrenheit" else 22,
        "unit": unit,
        "conditions": "sunny"
    }

    # Return result to LLM via callback
    await params.result_callback(weather_data)


async def book_appointment(params: FunctionCallParams):
    """Handle appointment booking function call."""
    date = params.arguments.get("date")
    time = params.arguments.get("time")
    service = params.arguments.get("service")

    # Your booking logic here
    confirmation = {
        "success": True,
        "confirmation_number": "APT-12345",
        "date": date,
        "time": time,
        "service": service
    }

    await params.result_callback(confirmation)


async def end_call(params: FunctionCallParams):
    """Handle call termination."""
    reason = params.arguments.get("reason", "Conversation completed")

    # Return action indicator for the transport to handle
    await params.result_callback({
        "action": "end_call",
        "reason": reason
    })


# Register functions with the LLM service
llm = OpenAILLMService(
    api_key=os.getenv("OPENAI_API_KEY"),
    model="gpt-4o-mini",
)

# Register individual function handlers
llm.register_function("get_weather", get_weather)
llm.register_function("book_appointment", book_appointment)
llm.register_function("end_call", end_call)

# Or register a single handler for all functions:
# llm.register_function(None, universal_handler)

# Include tools in context
context = LLMContext(messages, tools)
```

### 5. Event Handlers for Function Calls

```python
# You can also add event handlers for function call lifecycle
@llm.event_handler("on_function_calls_started")
async def on_function_calls_started(service, function_calls):
    """Called when function calls begin - useful for playing a wait message."""
    await tts.queue_frame(TTSSpeakFrame("Let me check on that for you."))


@llm.event_handler("on_function_calls_completed")
async def on_function_calls_completed(service, function_calls, results):
    """Called when all function calls complete."""
    pass
```

</implementation>

## Audio Format Handling

<audio-formats>

### Twilio Audio Specifications

| Parameter | Value |
|-----------|-------|
| Encoding | mu-law (PCMU) |
| Sample Rate | 8000 Hz (8kHz) |
| Channels | Mono |
| Bit Depth | 8-bit |

### TwilioFrameSerializer Audio Conversion

The serializer handles bidirectional conversion:

1. **Inbound (Twilio to Pipeline)**: mu-law 8kHz -> PCM at pipeline sample rate
2. **Outbound (Pipeline to Twilio)**: PCM at pipeline sample rate -> mu-law 8kHz

```python
from pipecat.serializers.twilio import TwilioFrameSerializer

class TwilioFrameSerializer:
    class InputParams(BaseModel):
        twilio_sample_rate: int = 8000  # Twilio's default
        sample_rate: int | None = None   # Override pipeline rate
        auto_hang_up: bool = True        # Auto-end call on EndFrame
```

### Telnyx Audio Specifications

| Parameter | Value |
|-----------|-------|
| Encoding | PCMU (mu-law) |
| Sample Rate | 8000 Hz |
| Channels | Mono |

</audio-formats>

## Critical Considerations

<considerations>

### Module Path Changes (v0.0.96+)

The latest Pipecat version has restructured module paths:

```python
# OLD paths (pre-0.0.96)
from pipecat.services.deepgram import DeepgramSTTService
from pipecat.services.elevenlabs import ElevenLabsTTSService
from pipecat.transports.network.fastapi_websocket import FastAPIWebsocketTransport

# NEW paths (0.0.96+)
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport
```

### VAD Configuration

Voice Activity Detection is crucial for natural conversations:

```python
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams

vad = SileroVADAnalyzer(
    params=VADParams(
        stop_secs=0.8,      # Silence duration to trigger end of speech
        min_volume=0.6,     # Minimum volume threshold
        start_secs=0.2,     # Minimum speech duration to start
    )
)
```

### Turn-Taking Strategies

Pipecat provides advanced turn-taking for natural conversations:

```python
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies

# Configure when assistant should stop speaking
turn_strategy = UserTurnStrategies(
    strategies=[TurnAnalyzerUserTurnStopStrategy()]
)
```

### Error Handling

Always handle WebSocket disconnections and pipeline errors:

```python
from pipecat.frames.frames import EndFrame, CancelFrame

# Pipeline will send EndFrame on graceful shutdown
# CancelFrame on errors or interruptions

@transport.event_handler("on_client_disconnected")
async def on_client_disconnected(transport, client):
    await task.cancel()
```

### Performance Best Practices

1. **Use streaming TTS**: Prefer WebSocket-based TTS services for lower latency
2. **Enable interruptions**: Set `allow_interruptions=True` for natural conversation flow
3. **Buffer audio**: Use `AudioBufferProcessor` for recording capabilities
4. **Limit context**: Keep LLM context reasonable to reduce latency

</considerations>

## Alternative Services

<alternatives>

| Service Type | Provider | Import Path | Notes |
|--------------|----------|-------------|-------|
| STT | Deepgram | `pipecat.services.deepgram.stt` | Best for real-time, supports Nova-2 |
| STT | ElevenLabs | `pipecat.services.elevenlabs.stt` | Lower latency |
| STT | Cartesia | `pipecat.services.cartesia.stt` | Alternative option |
| LLM | OpenAI | `pipecat.services.openai.llm` | GPT-4o, GPT-4o-mini |
| LLM | OpenAI Realtime | `pipecat.services.openai.realtime.llm` | Voice-to-voice, lowest latency |
| LLM | Anthropic | `pipecat.services.anthropic.llm` | Claude models |
| LLM | Google | `pipecat.services.google.llm` | Gemini models |
| TTS | ElevenLabs | `pipecat.services.elevenlabs.tts` | Highest quality voices |
| TTS | Cartesia | `pipecat.services.cartesia.tts` | Fast, good quality |
| TTS | Deepgram | `pipecat.services.deepgram.tts` | Aura voices |

</alternatives>

## Resources

<references>

- [Pipecat GitHub Repository](https://github.com/pipecat-ai/pipecat) - Source code and examples
- [Pipecat Examples](https://github.com/pipecat-ai/pipecat-examples) - Complete example applications
- [Pipecat Documentation](https://docs.pipecat.ai) - Official documentation
- [Twilio Media Streams](https://www.twilio.com/docs/voice/media-streams) - Twilio audio streaming docs
- [Twilio Chatbot Example](https://github.com/pipecat-ai/pipecat-examples/tree/main/twilio-chatbot) - Complete Twilio integration

</references>

## Research Metadata

<meta>
research-date: 2026-01-02
confidence-level: high
sources-validated: 15+
version-current: 0.0.96+
project-version: 0.0.67 (voice-noob currently uses)
upgrade-path: Review module path changes, check breaking changes in changelog
</meta>
