# LiveKit Research Summary

_Generated: 2026-01-06 | Sources: 15+ | Confidence: High_

## Executive Summary

<key-findings>

- **LiveKit is a complete voice AI platform** - Open-source WebRTC infrastructure with an Agents framework specifically designed for building realtime voice assistants. It handles the full stack: transport, STT, LLM, TTS, telephony.
- **Direct competitor to Pipecat** - Both are open-source orchestration frameworks for voice AI, but LiveKit offers tighter integration with its own WebRTC infrastructure while Pipecat is more transport-agnostic.
- **Production-ready with $45M Series B** - LiveKit Agents 1.0 released April 2025, powering over 3 billion calls annually for 100,000+ developers including ChatGPT Voice Mode.
- **Native telephony support** - Built-in SIP integration with Telnyx, Twilio, and other providers. Phone calls are bridged into LiveKit rooms as special participant types.

</key-findings>

## Overview

<overview>

LiveKit is an open-source platform for building realtime audio, video, and AI applications. The platform consists of:

1. **LiveKit Server** - WebRTC SFU (Selective Forwarding Unit) written in Go using Pion WebRTC
2. **LiveKit Agents** - Python/Node.js framework for building AI voice agents
3. **LiveKit Cloud** - Managed hosting with global distribution
4. **LiveKit Telephony** - SIP integration for phone calls

The Agents framework specifically targets the voice AI use case with built-in:
- Voice Activity Detection (VAD)
- Speech-to-Text (STT)
- Large Language Model (LLM) integration
- Text-to-Speech (TTS)
- Semantic turn detection
- Interruption handling

</overview>

## Architecture

<architecture>

### System Components

```
                    +------------------+
                    |   End User       |
                    | (Browser/Phone)  |
                    +--------+---------+
                             |
                             | WebRTC / SIP
                             v
                    +------------------+
                    |  LiveKit Server  |
                    |  (SFU - Go)      |
                    +--------+---------+
                             |
                             | Internal Protocol
                             v
                    +------------------+
                    |  Agent Worker    |
                    |  (Python/Node)   |
                    +--------+---------+
                             |
            +----------------+----------------+
            |                |                |
            v                v                v
        +-------+       +-------+        +-------+
        |  STT  |       |  LLM  |        |  TTS  |
        +-------+       +-------+        +-------+
```

### Voice Pipeline Flow

```
User Audio -> VAD -> STT -> LLM -> TTS -> User Audio
                     ^              |
                     |              v
              Turn Detection   Interruption
                               Handling
```

### Core Concepts

| Concept | Description |
|---------|-------------|
| **Agent** | LLM application with defined instructions and tools |
| **AgentSession** | Container managing end-user interactions |
| **Entrypoint** | Session starting point (like web request handlers) |
| **Worker** | Main process coordinating scheduling and agent launches |
| **Room** | Virtual space where participants (users + agents) interact |

</architecture>

## Implementation Guide

<implementation>

### Installation

```bash
# Core + common plugins
pip install "livekit-agents[openai,silero,deepgram,cartesia,turn-detector]~=1.0"

# Or minimal
pip install livekit-agents~=1.0

# Individual plugins
pip install livekit-plugins-deepgram
pip install livekit-plugins-elevenlabs
pip install livekit-plugins-openai
```

**Requirements:**
- Python 3.10 - 3.13
- LiveKit Cloud account or self-hosted server

### Minimal Voice Agent

```python
# agent.py
import logging
from dotenv import load_dotenv
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.plugins import silero

load_dotenv()
logger = logging.getLogger("voice-agent")

class MyAssistant(Agent):
    def __init__(self):
        super().__init__(
            instructions="""You are a helpful voice assistant.
            Be concise and friendly in your responses."""
        )

async def entrypoint(ctx: JobContext):
    await ctx.connect()

    session = AgentSession(
        vad=silero.VAD.load(),                    # Voice Activity Detection
        stt="deepgram/nova-3",                    # Speech-to-Text
        llm="openai/gpt-4o-mini",                 # Language Model
        tts="cartesia/sonic-2:voice-id-here",    # Text-to-Speech
    )

    await session.start(
        agent=MyAssistant(),
        room=ctx.room,
    )

    # Generate initial greeting
    await session.generate_reply(
        instructions="Greet the user warmly and ask how you can help."
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

### Environment Configuration

```bash
# .env.local
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# Provider keys (if using plugins directly instead of LiveKit Inference)
OPENAI_API_KEY=sk-...
DEEPGRAM_API_KEY=...
ELEVEN_API_KEY=...
CARTESIA_API_KEY=...
```

### Running the Agent

```bash
# Console mode - local testing in terminal
python agent.py console

# Development mode - connects to LiveKit Cloud with hot reload
python agent.py dev

# Production mode
python agent.py start
```

### Adding Function Tools

```python
from livekit.agents import Agent, function_tool, RunContext

class MyAssistant(Agent):
    def __init__(self):
        super().__init__(
            instructions="You are a helpful assistant with access to tools."
        )

    @function_tool
    async def get_weather(self, ctx: RunContext, location: str) -> str:
        """Get the current weather for a location.

        Args:
            location: The city or location to get weather for
        """
        # Your weather API logic here
        return f"The weather in {location} is sunny and 72F"

    @function_tool
    async def schedule_appointment(
        self,
        ctx: RunContext,
        date: str,
        time: str,
        description: str
    ) -> str:
        """Schedule an appointment for the user.

        Args:
            date: The date in YYYY-MM-DD format
            time: The time in HH:MM format
            description: Brief description of the appointment
        """
        # Your scheduling logic here
        return f"Appointment scheduled for {date} at {time}"
```

### Telephony Integration

```python
# telephony_agent.py
import json
from livekit import api
from livekit.agents import Agent, AgentSession, AgentServer, JobContext, function_tool, RunContext, get_job_context
from livekit.plugins import silero, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

server = AgentServer()

@server.rtc_session(agent_name="telephony-agent")  # Named for explicit dispatch
async def telephony_agent(ctx: JobContext):
    session = AgentSession(
        stt="assemblyai/universal-streaming:en",
        llm="openai/gpt-4o-mini",
        tts="cartesia/sonic-3:voice-id",
        vad=silero.VAD.load(),
        turn_detection=MultilingualModel(),
    )

    await session.start(
        room=ctx.room,
        agent=TelephonyAssistant(),
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                # Apply telephony-optimized noise cancellation
                noise_cancellation=lambda p: noise_cancellation.BVCTelephony()
            )
        )
    )

    await session.generate_reply(
        instructions="Greet the caller and ask how you can help."
    )

class TelephonyAssistant(Agent):
    def __init__(self):
        super().__init__(
            instructions="""You are a phone support agent.
            Be professional and helpful. Keep responses concise for phone conversations."""
        )

    @function_tool
    async def transfer_call(self, ctx: RunContext, department: str) -> str:
        """Transfer the call to another department.

        Args:
            department: The department to transfer to (sales, support, billing)
        """
        transfer_numbers = {
            "sales": "+15105550101",
            "support": "+15105550102",
            "billing": "+15105550103",
        }

        if department not in transfer_numbers:
            return "Invalid department"

        job_ctx = get_job_context()
        await job_ctx.api.sip.transfer_sip_participant(
            api.TransferSIPParticipantRequest(
                room_name=job_ctx.room.name,
                participant_identity="caller",
                transfer_to=f"tel:{transfer_numbers[department]}",
            )
        )
        return f"Transferring to {department}"

    @function_tool
    async def hang_up(self, ctx: RunContext) -> str:
        """End the phone call."""
        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(
            api.DeleteRoomRequest(room=job_ctx.room.name)
        )
        return "Call ended"
```

### Outbound Calling

```python
from livekit import api

# Create outbound call via API
async def make_outbound_call(phone_number: str, agent_name: str):
    lk_api = api.LiveKitAPI()

    # Dispatch agent to new room with call metadata
    await lk_api.agent_dispatch.create_dispatch(
        api.CreateAgentDispatchRequest(
            room=f"outbound-{phone_number}",
            agent_name=agent_name,
            metadata=json.dumps({"phone_number": phone_number})
        )
    )
```

</implementation>

## STT/TTS Integration

<stt-tts>

### LiveKit Inference (Recommended)

LiveKit Inference provides a unified gateway to multiple providers with just your LiveKit API key:

```python
# No additional API keys needed - uses LiveKit Inference
session = AgentSession(
    stt="assemblyai/universal-streaming:en",  # AssemblyAI via Inference
    llm="openai/gpt-4o-mini",                  # OpenAI via Inference
    tts="cartesia/sonic-3:voice-id",          # Cartesia via Inference
)
```

**Supported via Inference:**
| Type | Providers |
|------|-----------|
| STT | AssemblyAI, Deepgram, Cartesia |
| LLM | OpenAI, Google, Cerebras, Groq, Baseten |
| TTS | Cartesia, ElevenLabs, Inworld, Rime |

### Direct Plugin Integration

For more control or custom voices:

```python
from livekit.plugins import deepgram, elevenlabs, openai

session = AgentSession(
    stt=deepgram.STT(
        model="nova-2",
        language="en",
        interim_results=True,
    ),
    llm=openai.LLM(
        model="gpt-4o",
        temperature=0.7,
    ),
    tts=elevenlabs.TTS(
        voice="Rachel",  # Or custom voice ID
        model="eleven_turbo_v2_5",
        output_format="pcm_16000",
    ),
)
```

### Available Plugins

| Provider | Plugin Package | Capabilities |
|----------|---------------|--------------|
| OpenAI | `livekit-plugins-openai` | LLM, TTS, Realtime API |
| Deepgram | `livekit-plugins-deepgram` | STT, TTS |
| ElevenLabs | `livekit-plugins-elevenlabs` | TTS, Voice Cloning |
| Cartesia | `livekit-plugins-cartesia` | TTS |
| AssemblyAI | `livekit-plugins-assemblyai` | STT |
| Google | `livekit-plugins-google` | LLM (Gemini), STT, TTS |
| Azure | `livekit-plugins-azure` | STT, TTS |
| Silero | `livekit-plugins-silero` | VAD |

### Realtime Models (Speech-to-Speech)

For lower latency, use direct speech-to-speech models:

```python
from livekit.plugins import openai

session = AgentSession(
    realtime=openai.RealtimeModel(
        model="gpt-4o-realtime-preview",
        voice="alloy",
    ),
    vad=silero.VAD.load(),
)
```

</stt-tts>

## Pipecat vs LiveKit Comparison

<comparison>

| Aspect | LiveKit Agents | Pipecat |
|--------|---------------|---------|
| **Architecture** | Tightly integrated with LiveKit SFU | Transport-agnostic (Daily, LiveKit, Twilio, raw WebRTC) |
| **Language** | Python, Node.js | Python only |
| **API Design** | Clean, high-level abstractions | More verbose, requires more configuration |
| **Flexibility** | Moderate - opinionated pipeline | High - full control over pipeline |
| **Transport** | LiveKit rooms (WebRTC) | Multiple options (Daily, LiveKit, Twilio, WebRTC) |
| **Telephony** | Native SIP integration | Via transport providers |
| **Turn Detection** | Built-in semantic model (13 languages) | Requires configuration |
| **Hosting** | LiveKit Cloud or self-host | Self-host or provider cloud |
| **Plugin Ecosystem** | Growing | More mature |
| **Open Source** | Apache 2.0 | BSD 2-Clause |

### When to Choose LiveKit

- Need production-ready infrastructure quickly
- Want integrated telephony with SIP
- Prefer clean, simple API
- Using WebRTC for browser/mobile clients
- Need global scaling with managed cloud option

### When to Choose Pipecat

- Need maximum flexibility in pipeline design
- Want transport-agnostic solution
- Already using Daily.co
- Need fine-grained control over audio processing
- Building highly custom voice experiences

### Can They Work Together?

**Yes, partially.** Pipecat can use LiveKit as a transport layer:

```python
# Pipecat with LiveKit transport (audio only)
from pipecat.transports.services.livekit import LiveKitTransport

transport = LiveKitTransport(
    url="wss://your-livekit.cloud",
    api_key="...",
    api_secret="...",
    room_name="my-room",
)
```

However, this doesn't give you LiveKit Agents features - it just uses LiveKit as the WebRTC transport.

</comparison>

## Telephony Details

<telephony>

### Supported Providers

| Provider | Status | Documentation |
|----------|--------|---------------|
| Telnyx | Fully Tested | [Config Guide](https://docs.livekit.io/sip/quickstarts/configuring-telnyx-trunk/) |
| Twilio | Fully Tested | [Config Guide](https://docs.livekit.io/telephony/start/providers/twilio/) |
| Plivo | Tested | Via SIP trunk |
| Exotel | Tested | Via SIP trunk |
| Wavix | Tested | Via SIP trunk |

### Features

- **DTMF Support** - Handle tone-based input
- **HD Voice** - High-quality audio
- **Call Transfer** - SIP REFER for cold transfers
- **Secure Trunking** - TLS/SRTP support
- **Region Pinning** - Route to specific regions
- **Noise Cancellation** - Krisp AI integration

### SIP Trunk Setup (Telnyx Example)

1. Create Telnyx SIP trunk with LiveKit endpoint
2. Purchase phone number, associate with trunk
3. Configure dispatch rules in LiveKit

```bash
# Create dispatch rule for inbound calls
lk sip dispatch create dispatch-rule.json

# dispatch-rule.json
{
    "dispatch_rule": {
        "rule": {
            "dispatchRuleIndividual": {
                "roomPrefix": "call-"
            }
        },
        "roomConfig": {
            "agents": [{
                "agentName": "my-telephony-agent"
            }]
        }
    }
}
```

</telephony>

## Deployment Options

<deployment>

### LiveKit Cloud (Recommended for Production)

**Pricing Tiers:**

| Tier | Price | Participants | Minutes | Bandwidth |
|------|-------|--------------|---------|-----------|
| Build | Free | 100 concurrent | 5,000/mo | 50GB |
| Ship | $50/mo | 1,000 concurrent | 150,000/mo | 250GB |
| Scale | $500/mo | Unlimited | 1.5M/mo | 3TB |

**Cloud Features:**
- Global distribution with <100ms latency
- Auto-scaling to millions of concurrent users
- Session migration on datacenter failures
- Built-in analytics and logging
- Managed agent hosting
- Native telephony (phone numbers without SIP setup)

### Self-Hosted

**Requirements:**
- Docker/Kubernetes
- Redis for distributed state
- Ports: 7880 (HTTP), 7881 (WebSocket), 443 (TLS)
- UDP ports for WebRTC media

```yaml
# docker-compose.yml
version: '3'
services:
  livekit:
    image: livekit/livekit-server:latest
    ports:
      - "7880:7880"
      - "7881:7881"
      - "50000-60000:50000-60000/udp"
    environment:
      - LIVEKIT_KEYS=devkey: secret
    volumes:
      - ./livekit.yaml:/etc/livekit.yaml
    command: --config /etc/livekit.yaml

  redis:
    image: redis:7-alpine
```

```yaml
# livekit.yaml
port: 7880
rtc:
  port_range_start: 50000
  port_range_end: 60000
  use_external_ip: true
redis:
  address: redis:6379
keys:
  devkey: secret
```

**Self-Hosted Considerations:**
- You manage scaling, monitoring, upgrades
- Need separate SIP server for telephony
- No managed agent hosting
- Must handle global distribution yourself

</deployment>

## Integration with Voice-Noob

<integration-notes>

### Current Stack (Pipecat)

Voice-noob currently uses Pipecat with:
- Deepgram STT
- ElevenLabs TTS
- OpenAI GPT-4o
- Telnyx telephony

### Migration Considerations

**Option 1: Replace Pipecat with LiveKit Agents**
- Pros: Tighter integration, built-in telephony, semantic turn detection
- Cons: Less pipeline flexibility, migration effort

**Option 2: Use Pipecat with LiveKit Transport**
- Pros: Keep existing pipeline logic, add LiveKit WebRTC
- Cons: Doesn't get LiveKit Agents features

**Option 3: Hybrid Approach**
- Use LiveKit Agents for new features
- Maintain Pipecat for existing complex pipelines

### Code Comparison

**Current Pipecat Pattern:**
```python
# Pipecat style
pipeline = Pipeline([
    transport.input(),
    stt,
    llm_aggregator,
    llm,
    tts,
    transport.output(),
])
```

**LiveKit Agents Pattern:**
```python
# LiveKit style
session = AgentSession(
    vad=silero.VAD.load(),
    stt="deepgram/nova-3",
    llm="openai/gpt-4o",
    tts="elevenlabs/eleven_turbo_v2_5:voice-id",
)
await session.start(agent=MyAgent(), room=ctx.room)
```

</integration-notes>

## Resources

<references>

### Official Documentation
- [LiveKit Documentation](https://docs.livekit.io/) - Main docs portal
- [Agents Framework](https://docs.livekit.io/agents/) - Agents-specific docs
- [Voice AI Quickstart](https://docs.livekit.io/agents/start/voice-ai-quickstart/) - Getting started guide
- [Telephony Integration](https://docs.livekit.io/agents/start/telephony/) - Phone call setup
- [Models Overview](https://docs.livekit.io/agents/models/) - STT/LLM/TTS providers

### GitHub
- [livekit/agents](https://github.com/livekit/agents) - Main agents repository
- [livekit/livekit](https://github.com/livekit/livekit) - Server repository
- [livekit-examples/agent-starter-python](https://github.com/livekit-examples/agent-starter-python) - Starter template

### Provider Integrations
- [Telnyx SIP Configuration](https://docs.livekit.io/sip/quickstarts/configuring-telnyx-trunk/)
- [Twilio SIP Configuration](https://docs.livekit.io/telephony/start/providers/twilio/)
- [ElevenLabs Plugin](https://docs.livekit.io/agents/models/tts/plugins/elevenlabs/)

### Community
- [LiveKit Blog](https://blog.livekit.io/) - Announcements and tutorials
- [LiveKit Playground](https://agents-playground.livekit.io/) - Test agents in browser

</references>

## Research Metadata

<meta>
research-date: 2026-01-06
confidence-level: high
sources-validated: 15+
version-current: LiveKit Agents 1.3.x (December 2025)
python-support: 3.10-3.13
</meta>
