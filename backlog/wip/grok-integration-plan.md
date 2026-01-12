# Add xAI Grok Realtime Provider Integration

## Goal
Add xAI Grok as a new realtime voice provider to offer provider diversity and unique features (X/web search, alternative to OpenAI).

**Note:** Grok ($3/hr) is positioned as a premium option for provider diversity, NOT cost savings (current OpenAI tiers are $1.92/hr and $0.54/hr).

## Architecture Overview

Current routing:
```
Pricing Tier → Session Handler → API
├─ premium/premium-mini → GPTRealtimeSession → OpenAI Realtime
├─ balanced/budget → PipecatPipelineSession → STT+LLM+TTS
└─ [NEW] grok-realtime → GrokRealtimeSession → xAI Grok Realtime
```

## Implementation Plan

### Phase 1: Database Migration (Week 1)

**Add xAI API key storage to UserSettings model**

Files to modify:
- `/Users/vasanth/Code/kens/voice-noob/backend/app/models/user_settings.py`
  - Add field: `xai_api_key: Mapped[str | None] = mapped_column(Text, nullable=True, comment="xAI API key for Grok Realtime")`

- Create migration: `/Users/vasanth/Code/kens/voice-noob/backend/migrations/versions/YYYYMMDDHHMMSS_add_xai_api_key.py`
  ```sql
  ALTER TABLE user_settings
  ADD COLUMN xai_api_key TEXT NULL
  COMMENT 'xAI API key for Grok Realtime';
  ```

Deploy and verify: No impact on existing functionality.

---

### Phase 2: Backend - Grok Session Handler (Week 1-2)

**Create GrokRealtimeSession class following GPTRealtimeSession pattern**

**New file:** `/Users/vasanth/Code/kens/voice-noob/backend/app/services/grok_realtime.py`

Key implementation details:
```python
from pipecat.services.grok.realtime.llm import GrokRealtimeLLMService
from pipecat.services.grok.realtime.events import SessionProperties, TurnDetection

class GrokRealtimeSession:
    """Manages Grok Realtime API session for voice calls."""

    async def initialize(self) -> None:
        # Get xAI API key from user_settings (workspace-isolated)
        user_settings = await get_user_api_keys(
            self.user_id_uuid, self.db, workspace_id=self.workspace_id
        )

        if not user_settings.xai_api_key:
            raise ValueError("xAI API key not configured for this workspace")

        # Create Grok session using Pipecat
        self.session_properties = SessionProperties(
            voice=self._map_voice(agent_config.get("voice", "Ara")),
            instructions=build_instructions_with_language(...),
            turn_detection=TurnDetection(
                type="server_vad",
                threshold=agent_config.get("turn_detection_threshold", 0.7),
                prefix_padding_ms=200,
                silence_duration_ms=600,
            ),
            tools=self._convert_tools_to_grok_format(chat_tools),
        )

        self.llm = GrokRealtimeLLMService(
            api_key=user_settings.xai_api_key,
            session_properties=self.session_properties,
        )

    def _map_voice(self, voice: str) -> str:
        """Map OpenAI voice names to Grok voices."""
        voice_map = {
            "marin": "Ara",    # Professional → Warm friendly female
            "cedar": "Rex",    # Conversational → Confident male
            "shimmer": "Eve",  # Energetic → Energetic female
            "alloy": "Sal",    # Neutral → Neutral smooth
            "onyx": "Rex",     # Deep → Confident male
        }
        return voice_map.get(voice.lower(), "Ara")  # Default Ara

    async def handle_tool_call(self, tool_call: dict) -> dict:
        """Route to internal ToolRegistry (same as GPT)."""
        return await self.tool_registry.execute_tool(...)
```

Similar methods as GPTRealtimeSession: send_audio(), transcripts, cleanup()

---

### Phase 3: Backend - API Routing (Week 2)

**Update routing logic to support grok-realtime tier**

**File:** `/Users/vasanth/Code/kens/voice-noob/backend/app/api/telephony_ws.py`
- Line ~144: Update session selection
```python
use_openai_realtime = agent.pricing_tier in ("premium", "premium-mini")
use_grok_realtime = agent.pricing_tier == "grok-realtime"

if use_openai_realtime:
    async with GPTRealtimeSession(...) as realtime_session:
        ...
elif use_grok_realtime:
    from app.services.grok_realtime import GrokRealtimeSession
    async with GrokRealtimeSession(...) as realtime_session:
        ...
else:
    # Pipeline mode for budget/balanced
    ...
```

**File:** `/Users/vasanth/Code/kens/voice-noob/backend/app/api/realtime.py`
- Line ~169: Add grok-realtime tier validation in WebSocket endpoint
- Update tier checks throughout

**File:** `/Users/vasanth/Code/kens/voice-noob/backend/app/api/settings.py`
- Add xai_api_key to UserAPIKeysUpdate schema
- Update PUT /settings/api-keys endpoint to save xai_api_key

---

### Phase 4: Frontend - Pricing Tier & UI (Week 2-3)

**Add Grok tier to pricing configuration**

**File:** `/Users/vasanth/Code/kens/voice-noob/frontend/src/lib/pricing-tiers.ts`
- Add new tier to PRICING_TIERS array:
```typescript
{
  id: "grok-realtime",
  name: "Grok Realtime",
  description: "xAI Grok Voice Agent with X/web search integration",
  costPerHour: 3.00,
  costPerMinute: 0.05,
  features: [
    "Provider diversity (alternative to OpenAI)",
    "Real-time audio over WebSocket",
    "0.78s first-audio latency",
    "Built-in X search & web search",
    "5 native voices (Ara, Rex, Sal, Eve, Leo)",
  ],
  config: {
    llmProvider: "grok-realtime",
    llmModel: "grok-2-realtime",
    sttProvider: "grok",
    sttModel: "built-in",
    ttsProvider: "grok",
    ttsModel: "built-in",
    telephonyProvider: "telnyx",
  },
  performance: {
    latency: "~780ms",
    speed: "Good",
    quality: "Very Good",
  },
}
```

**File:** `/Users/vasanth/Code/kens/voice-noob/frontend/src/app/dashboard/agents/create-agent/page.tsx`
- Add GROK_VOICES constant (Ara, Rex, Sal, Eve, Leo)
- Update voice selector to show Grok voices when tier="grok-realtime"
- Implement auto-mapping with fallback to "Ara"

**File:** `/Users/vasanth/Code/kens/voice-noob/frontend/src/app/dashboard/settings/page.tsx`
- Add xAI API key input field (similar to OpenAI key)
```tsx
<FormField
  name="xai_api_key"
  render={({ field }) => (
    <FormItem>
      <FormLabel>xAI API Key</FormLabel>
      <Input type="password" placeholder="xai-..." {...field} />
      <FormDescription>
        Required for Grok Realtime tier. Get your key at{" "}
        <a href="https://console.x.ai" target="_blank">console.x.ai</a>
      </FormDescription>
    </FormItem>
  )}
/>
```

---

### Phase 5: Testing (Week 3)

**Unit Tests** (`backend/tests/unit/`)
1. test_grok_realtime_session.py
   - Initialization with xAI API key
   - Voice mapping (OpenAI → Grok)
   - Tool call routing
   - Transcript accumulation

2. test_api_keys.py
   - xAI API key CRUD operations
   - Workspace isolation
   - Missing key error handling

**Integration Tests** (`backend/tests/integration/`)
1. test_grok_telephony.py
   - Mock xAI WebSocket connection
   - Audio streaming (Twilio → Grok → Twilio)
   - Tool calling flow
   - Call termination

2. test_tier_routing.py
   - Routing logic for all tiers including grok-realtime
   - Tier validation
   - WebSocket upgrade

**API Tests** (`backend/tests/api/`)
1. test_realtime_endpoints.py
   - /ws/realtime/{agent_id} with grok-realtime tier
   - WebRTC session creation
   - Error handling for missing API key

---

### Phase 6: Gradual Rollout (Week 4)

**Week 1: Backend + DB Migration**
- Deploy migration to add xai_api_key column
- Deploy GrokRealtimeSession service (inactive)
- Monitor: No errors, no impact

**Week 2: API Key Management UI**
- Deploy settings page with xAI API key field
- Alpha testing: Internal team tests with test agents
- Monitor: API key storage, encryption

**Week 3: Limited Beta**
- Enable "grok-realtime" tier for beta users (feature flag)
- Deploy agent creation wizard with Grok tier
- Monitor: Session creation, audio quality, tool calling

**Week 4: General Availability**
- Remove feature flag, enable for all users
- Marketing: Announce Grok provider option
- Monitor: Adoption rate, error rate, user feedback

---

## Voice Mapping Table

Auto-map OpenAI voices to Grok equivalents:

| OpenAI Voice | Grok Voice | Rationale |
|--------------|------------|-----------|
| marin | Ara | Professional & clear → Warm, friendly female |
| cedar | Rex | Natural & conversational → Confident male |
| shimmer | Eve | Energetic → Energetic female |
| alloy | Sal | Neutral → Neutral, smooth |
| onyx | Rex | Deep & authoritative → Confident male |
| echo | Ara | Warm & engaging → Warm, friendly |
| nova | Eve | Friendly & upbeat → Energetic female |
| (default) | Ara | Fallback for unmapped voices |

---

## Dependencies

**Backend:**
- Verify Pipecat includes Grok support: `pipecat-ai[grok]`
- Current: `pipecat-ai[daily]==0.0.67` - check if includes Grok plugin
- If not, update requirements.txt: `pipecat-ai[grok]>=0.0.67`

**Frontend:**
- No new dependencies needed

---

## Error Handling

**Missing xAI API Key:**
```python
if not user_settings.xai_api_key:
    raise ValueError(
        "xAI API key not configured for this workspace. "
        "Please add it in Settings > Workspace API Keys."
    )
```

**Frontend Warning:** Show alert in agent creation if grok-realtime selected but no API key configured.

**No Automatic Fallback:** If Grok API fails, fail explicitly with clear error (prevents unexpected OpenAI costs).

---

## Success Metrics

**Technical:**
- Zero initialization errors
- Audio streaming works for Twilio/Telnyx
- Tool calling success rate ≥ 95%
- Transcript accuracy ≥ 90%

**Business:**
- 5%+ of new agents use grok-realtime within 30 days
- User satisfaction: NPS ≥ 40 for Grok tier

**Performance:**
- First-audio latency ≤ 1.0s (target: 0.78s)
- Call completion rate ≥ 98%
- WebSocket stability ≥ 99.5%

---

## Timeline Summary

| Phase | Duration | Effort |
|-------|----------|--------|
| Phase 1: DB Migration | 2 days | 1 dev day |
| Phase 2: Backend Session | 5 days | 3 dev days |
| Phase 3: API Routing | 3 days | 2 dev days |
| Phase 4: Frontend UI | 4 days | 2 dev days |
| Phase 5: Testing | 5 days | 3 dev days |
| Phase 6: Rollout | 14 days | 1 dev day (monitoring) |
| **Total** | **5 weeks** | **12 dev days** |

---

## Critical Files Reference

**Backend:**
1. `backend/app/models/user_settings.py` - Add xai_api_key field
2. `backend/app/services/grok_realtime.py` - NEW: Core session handler
3. `backend/app/api/telephony_ws.py` - Update routing logic
4. `backend/app/api/realtime.py` - Add tier validation
5. `backend/app/api/settings.py` - Add API key management
6. `backend/migrations/versions/YYYYMMDDHHMMSS_add_xai_api_key.py` - NEW: Migration

**Frontend:**
7. `frontend/src/lib/pricing-tiers.ts` - Add grok-realtime tier
8. `frontend/src/app/dashboard/agents/create-agent/page.tsx` - Add Grok voices
9. `frontend/src/app/dashboard/settings/page.tsx` - Add xAI API key input

---

## Next Steps

1. Review and approve this plan
2. Create feature branch: `feature/grok-realtime-provider`
3. Phase 1: Write database migration
4. Phase 2: Implement GrokRealtimeSession service
5. Begin testing with mock xAI API
