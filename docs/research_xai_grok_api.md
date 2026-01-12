# xAI Grok API Research Summary

_Generated: 2026-01-06 | Sources: 15+ | Confidence: High_

## Executive Summary

<key-findings>

- **Grok API is fully OpenAI-compatible** - Drop-in replacement using `base_url="https://api.x.ai/v1"` with OpenAI SDK
- **Grok Voice Agent API launched December 2025** - Real-time WebSocket voice API at `wss://api.x.ai/v1/realtime`, pricing at $0.05/minute
- **Pipecat has native Grok support** - Both `GrokLLMService` (text) and `GrokRealtimeLLMService` (voice) available
- **Streaming fully supported** - SSE streaming for text, bidirectional WebSocket for voice
- **Best-in-class voice latency** - Average time-to-first-audio of 0.78 seconds, ranked #1 on Big Bench Audio

</key-findings>

---

## 1. Grok API Basics

<overview>

### Base URL & Authentication

```python
# Base URL
BASE_URL = "https://api.x.ai/v1"

# Authentication: Bearer token in header
headers = {
    "Authorization": "Bearer YOUR_XAI_API_KEY"
}
```

API keys are obtained from the [xAI Console](https://console.x.ai/) and typically start with `xai-`.

### Regional Endpoints

For lower latency, use regional endpoints:
- `https://us-west-1.api.x.ai/v1`

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | Chat completions (OpenAI-compatible) |
| `/v1/completions` | POST | Text completions |
| `/v1/responses` | POST | Responses API with server-side tools |
| `/v1/models` | GET | List available models |
| `/v1/images/generations` | POST | Image generation |
| `/v1/realtime` | WebSocket | Voice Agent API |
| `/v1/realtime/client_secrets` | POST | Ephemeral tokens for client auth |

</overview>

---

## 2. Available Models & Pricing

<models>

### Latest Models (December 2025)

| Model | Context | Input $/1M | Output $/1M | Best For |
|-------|---------|------------|-------------|----------|
| `grok-4` | 128K | $3.00 | $15.00 | Flagship reasoning, coding |
| `grok-4-1-fast-reasoning` | 2M | $0.20 | $0.50 | Agentic tool calling with reasoning |
| `grok-4-1-fast-non-reasoning` | 2M | $0.20 | $0.50 | Fast responses without reasoning |
| `grok-code-fast-1` | 256K | ~$0.20 | ~$0.50 | Agentic coding |
| `grok-3` | 128K | $3.00 | $15.00 | General purpose |
| `grok-3-mini` | 128K | Lower | Lower | Cost-effective |

### Large Context Pricing

For 2M context window models:
- Input: $6.00/1M tokens
- Output: $30.00/1M tokens

### Tool Invocation Pricing

| Tool | Price per 1,000 calls |
|------|----------------------|
| Web Search | $5.00 |
| X Search | $5.00 |
| Code Execution | $5.00 |
| Document Search | $5.00 |
| Collections Search | $2.50 |

### Rate Limits

- Up to 4M tokens per minute (varies by tier)
- 100 requests per minute (standard tier)
- Enterprise contracts available for higher limits
- Check your limits at [xAI Console Models Page](https://console.x.ai/)

**Note:** $25 monthly minimum commitment required.

</models>

---

## 3. Streaming Support

<streaming>

### Text Streaming (SSE)

All text-output models support Server-Sent Events streaming. Enable with `stream: true`.

**Python with xAI SDK:**

```python
import os
from xai_sdk import Client
from xai_sdk.chat import user, system

client = Client(api_key=os.getenv('XAI_API_KEY'))
chat = client.chat.create(model="grok-4")
chat.append(system("You are Grok, a helpful assistant."))
chat.append(user("What is the meaning of life?"))

for response, chunk in chat.stream():
    print(chunk.content, end="", flush=True)
```

**Python with OpenAI SDK:**

```python
from openai import OpenAI
import httpx

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
    timeout=httpx.Timeout(3600.0)  # Extended for reasoning models
)

stream = client.chat.completions.create(
    model="grok-4",
    messages=[
        {"role": "system", "content": "You are Grok."},
        {"role": "user", "content": "Hello!"}
    ],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

**JavaScript with OpenAI SDK:**

```javascript
import OpenAI from "openai";

const openai = new OpenAI({
    apiKey: process.env.XAI_API_KEY,
    baseURL: "https://api.x.ai/v1",
    timeout: 360000,
});

const stream = await openai.chat.completions.create({
    model: "grok-4",
    stream: true,
    messages: [
        { role: "system", content: "You are Grok." },
        { role: "user", content: "Hello!" }
    ]
});

for await (const chunk of stream) {
    process.stdout.write(chunk.choices[0].delta.content || "");
}
```

### SSE Format

```
data: {"id":"<id>","choices":[{"index":0,"delta":{"content":"text"}}],...}
data: [DONE]
```

</streaming>

---

## 4. OpenAI Compatibility

<compatibility>

### Drop-in Replacement

The xAI API is **fully compatible** with OpenAI and Anthropic SDKs. Migration requires only:

1. Generate an xAI API key from [console.x.ai](https://console.x.ai/)
2. Change the base URL to `https://api.x.ai/v1`
3. Update model names to Grok models

**Example Migration:**

```python
# Before (OpenAI)
from openai import OpenAI
client = OpenAI(api_key="sk-...")

# After (xAI Grok)
from openai import OpenAI
client = OpenAI(
    api_key="xai-...",
    base_url="https://api.x.ai/v1"
)
```

### Supported OpenAI Features

- Chat completions API
- Streaming responses
- Function/tool calling
- Vision (image understanding)
- System/user/assistant message roles (any order)
- Response format (JSON mode)

### SDK Recommendation

xAI recommends using the **OpenAI SDK** for better stability, though Anthropic SDK is also supported.

</compatibility>

---

## 5. Python SDK Options

<sdk>

### Option 1: Official xAI SDK (Recommended)

```bash
pip install xai-sdk
```

**Features:**
- gRPC-based for performance
- Sync and async clients
- Built-in agentic tool calling
- OpenTelemetry support

**Example:**

```python
import os
from xai_sdk import Client
from xai_sdk.chat import user, system

# Sync client
client = Client(api_key=os.getenv('XAI_API_KEY'))

# Async client
from xai_sdk import AsyncClient
async_client = AsyncClient(api_key=os.getenv('XAI_API_KEY'))

# Create chat
chat = client.chat.create(model="grok-4")
chat.append(system("You are a helpful assistant."))
chat.append(user("Hello!"))

# Non-streaming
response = chat.sample()
print(response.content)

# Streaming
for response, chunk in chat.stream():
    print(chunk.content, end="")
```

**Environment Variable:**
```bash
export XAI_API_KEY="xai-your-key-here"
```

### Option 2: OpenAI SDK (For Migration)

```bash
pip install openai
```

```python
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1"
)

response = client.chat.completions.create(
    model="grok-4",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Version Requirements

- `xai-sdk >= 1.3.1` required for agentic tool calling

</sdk>

---

## 6. Pipecat Integration

<pipecat>

### Installation

```bash
pip install "pipecat-ai[grok]"
```

### Environment Setup

```bash
export XAI_API_KEY="xai-your-key-here"
# or
export GROK_API_KEY="xai-your-key-here"
```

### GrokLLMService (Text LLM)

For standard text-based conversations with streaming:

```python
from pipecat.services.grok import GrokLLMService

llm = GrokLLMService(
    api_key=os.getenv("XAI_API_KEY"),
    model="grok-4"
)
```

**Features:**
- Inherits from `OpenAILLMService`
- Streaming responses
- Function calling
- Context management

### GrokRealtimeLLMService (Voice Agent)

For real-time voice conversations:

```python
from pipecat.services.grok.realtime.llm import GrokRealtimeLLMService
from pipecat.services.grok.realtime.events import (
    SessionProperties,
    TurnDetection,
    WebSearchTool,
    XSearchTool,
)

# Configure session
session_properties = SessionProperties(
    voice="Ara",  # Options: Ara, Rex, Sal, Eve, Leo
    instructions="You are a helpful voice assistant.",
    turn_detection=TurnDetection(type="server_vad"),
    tools=[
        WebSearchTool(),
        XSearchTool(),
    ],
)

# Create service
llm = GrokRealtimeLLMService(
    api_key=os.getenv("GROK_API_KEY"),
    session_properties=session_properties,
    start_audio_paused=False,
)
```

### Available Voices

| Voice | Description |
|-------|-------------|
| Ara | Warm, friendly female (default) |
| Rex | Confident male for professional contexts |
| Sal | Neutral, smooth for versatility |
| Eve | Energetic female for interactive experiences |
| Leo | Authoritative male for instructional content |

### Built-in Tools

- `WebSearchTool()` - Real-time web search
- `XSearchTool()` - X/Twitter search
- `file_search` - Document collections

### Example Pipeline

```python
# examples/foundational/51-grok-realtime.py
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.services.grok.realtime.llm import GrokRealtimeLLMService
from pipecat.services.grok.realtime.events import SessionProperties

async def main():
    session_properties = SessionProperties(
        voice="Ara",
        instructions="You are a helpful assistant.",
    )

    llm = GrokRealtimeLLMService(
        api_key=os.getenv("GROK_API_KEY"),
        session_properties=session_properties,
    )

    pipeline = Pipeline([
        transport.input(),
        llm,
        transport.output(),
    ])

    runner = PipelineRunner()
    await runner.run(pipeline)
```

### API Reference

- [GrokLLMService Reference](https://reference-server.pipecat.ai/en/latest/api/pipecat.services.grok.llm.html)
- [GrokRealtimeLLMService Reference](https://reference-server.pipecat.ai/en/latest/api/pipecat.services.grok.realtime.llm.html)
- [Example: Function Calling](https://github.com/pipecat-ai/pipecat/blob/main/examples/foundational/14g-function-calling-grok.py)
- [Example: Grok Realtime](https://github.com/pipecat-ai/pipecat/blob/main/examples/foundational/51-grok-realtime.py)

</pipecat>

---

## 7. Grok Voice Agent API (Realtime)

<realtime>

### Overview

Launched December 17, 2025, the Grok Voice Agent API provides:
- Real-time bidirectional audio over WebSocket
- Native-quality voices in 100+ languages
- Built-in tool calling (web search, X search, custom functions)
- Server-side VAD (Voice Activity Detection)
- OpenAI Realtime API compatibility

### Pricing

**$0.05 per minute** of connection time (~$3.00/hour)

This is approximately **half** the cost of OpenAI Realtime API.

### Performance

- Average time-to-first-audio: **0.78 seconds**
- Ranked #1 on Big Bench Audio benchmark
- Nearly 5x faster than closest competitor

### WebSocket Connection

```python
import websockets
import json
import base64

WS_URL = "wss://api.x.ai/v1/realtime"

async def connect_voice_agent():
    headers = {"Authorization": f"Bearer {API_KEY}"}

    async with websockets.connect(WS_URL, extra_headers=headers) as ws:
        # Configure session
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "voice": "Ara",
                "instructions": "You are a helpful assistant.",
                "turn_detection": {"type": "server_vad"},
                "audio": {
                    "input": {"format": {"type": "audio/pcm", "rate": 16000}},
                    "output": {"format": {"type": "audio/pcm", "rate": 16000}}
                },
                "tools": [{"type": "web_search"}]
            }
        }))

        # Handle messages
        async for message in ws:
            event = json.loads(message)
            if event["type"] == "response.output_audio.delta":
                audio_data = base64.b64decode(event["delta"])
                # Play audio_data
```

### Authentication for Client-Side

Use ephemeral tokens to avoid exposing API keys:

```python
import requests

# Get ephemeral token (server-side)
response = requests.post(
    "https://api.x.ai/v1/realtime/client_secrets",
    headers={"Authorization": f"Bearer {API_KEY}"},
    json={"expires_in": 300}  # 5 minutes
)
ephemeral_token = response.json()["token"]

# Client connects with ephemeral token
ws = websocket.connect(
    "wss://api.x.ai/v1/realtime",
    subprotocols=[
        "realtime",
        f"openai-insecure-api-key.{ephemeral_token}",
        "openai-beta.realtime-v1"
    ]
)
```

### Audio Formats

| Format | Sample Rate | Use Case |
|--------|-------------|----------|
| `audio/pcm` (Linear16) | 8-48 kHz (default 24kHz) | General use |
| `audio/pcmu` (G.711 u-law) | 8 kHz | US telephony |
| `audio/pcma` (G.711 A-law) | 8 kHz | International telephony |

### Message Types

**Client -> Server:**
- `session.update` - Configure voice, instructions, tools
- `input_audio_buffer.append` - Stream audio chunks
- `input_audio_buffer.commit` - Finalize turn (manual mode)
- `conversation.item.create` - Add text/function results
- `response.create` - Request response

**Server -> Client:**
- `session.updated` - Config acknowledged
- `response.output_audio.delta` - Audio chunk
- `response.output_audio_transcript.delta` - Transcript chunk
- `response.function_call_arguments.done` - Function call request
- `response.done` - Response complete

### Custom Function Calling

```python
# Define function in session
session_config = {
    "tools": [{
        "type": "function",
        "name": "get_weather",
        "description": "Get weather for a location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string"}
            },
            "required": ["location"]
        }
    }]
}

# Handle function call
if event["type"] == "response.function_call_arguments.done":
    function_name = event["name"]
    args = json.loads(event["arguments"])

    # Execute function
    result = get_weather(args["location"])

    # Send result back
    await ws.send(json.dumps({
        "type": "conversation.item.create",
        "item": {
            "type": "function_call_output",
            "call_id": event["call_id"],
            "output": json.dumps(result)
        }
    }))

    # Continue response
    await ws.send(json.dumps({"type": "response.create"}))
```

### Turn Detection Modes

1. **Server VAD** (default): Automatic speech detection
   ```json
   {"turn_detection": {"type": "server_vad"}}
   ```

2. **Manual**: Client controls turn boundaries
   ```json
   {"turn_detection": {"type": null}}
   ```
   Then use `input_audio_buffer.commit` to end turn.

</realtime>

---

## 8. Integration Recommendations for Voice-Noob

<recommendations>

### For Text LLM (Chat/Agent)

Use `GrokLLMService` via Pipecat for seamless integration:

```python
# backend/app/services/llm/grok_service.py
from pipecat.services.grok import GrokLLMService

class GrokProvider:
    def __init__(self, api_key: str, model: str = "grok-4"):
        self.llm = GrokLLMService(
            api_key=api_key,
            model=model
        )
```

### For Voice Agent (Realtime)

Use `GrokRealtimeLLMService` for voice-to-voice:

```python
# backend/app/services/voice/grok_realtime.py
from pipecat.services.grok.realtime.llm import GrokRealtimeLLMService
from pipecat.services.grok.realtime.events import SessionProperties

class GrokVoiceProvider:
    def __init__(self, api_key: str):
        self.session_properties = SessionProperties(
            voice="Ara",
            turn_detection=TurnDetection(type="server_vad"),
        )
        self.llm = GrokRealtimeLLMService(
            api_key=api_key,
            session_properties=self.session_properties,
        )
```

### Cost Comparison (Voice)

| Provider | Pricing Model | Estimated Cost/Hour |
|----------|---------------|---------------------|
| **Grok Voice Agent** | $0.05/min connection | **$3.00** |
| OpenAI Realtime | Token-based | ~$6-10 |
| Deepgram + ElevenLabs + GPT-4o | Per-service | ~$5-8 |

### Recommended Configuration

```python
# .env additions
XAI_API_KEY=xai-your-key-here
GROK_MODEL=grok-4-1-fast-reasoning  # Best for agentic use
GROK_VOICE=Ara  # Default voice
```

</recommendations>

---

## 9. Resources

<references>

### Official Documentation
- [xAI API Overview](https://docs.x.ai/docs/overview)
- [xAI REST API Reference](https://docs.x.ai/docs/api-reference)
- [Grok Voice Agent API](https://docs.x.ai/docs/guides/voice)
- [Streaming Response Guide](https://docs.x.ai/docs/guides/streaming-response)
- [Models and Pricing](https://docs.x.ai/docs/models)
- [Migration from OpenAI](https://docs.x.ai/docs/guides/migration)

### SDKs & Tools
- [Official xAI Python SDK](https://github.com/xai-org/xai-sdk-python)
- [xAI Cookbook (Examples)](https://github.com/xai-org/xai-cookbook)
- [Pipecat Grok Integration](https://docs.pipecat.ai/server/services/llm/grok)
- [LiveKit xAI Plugin](https://docs.livekit.io/agents/models/realtime/plugins/xai/)

### Announcements
- [Grok Voice Agent API Launch](https://x.ai/news/grok-voice-agent-api)
- [Grok 4.1 Fast Release](https://x.ai/news/grok-4-1-fast)

### Console
- [xAI Console](https://console.x.ai/) - API keys, usage, rate limits

</references>

---

## Research Metadata

<meta>

| Field | Value |
|-------|-------|
| research-date | 2026-01-06 |
| confidence-level | high |
| sources-validated | 15+ |
| version-current | Grok 4.1 Fast (December 2025) |
| voice-api-version | December 17, 2025 release |
| pipecat-support | Native (GrokLLMService, GrokRealtimeLLMService) |

</meta>
