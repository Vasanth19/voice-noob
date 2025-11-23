# Voice Agent Platform

AI-powered voice agent platform for configuring and deploying custom voice agents with tool calling, multi-provider support, and transparent pricing tiers.

## Project Structure

```
voice-noob/
├── backend/              # FastAPI Python backend
│   ├── app/
│   │   ├── api/         # API endpoints (health checks)
│   │   ├── core/        # Config, security, settings
│   │   ├── db/          # Database session, Redis, models
│   │   ├── models/      # SQLAlchemy models (User)
│   │   └── services/    # Business logic (tools, voice agents)
│   ├── migrations/      # Alembic database migrations
│   └── tests/           # Backend tests
├── frontend/            # Next.js 15 React frontend
│   ├── src/
│   │   ├── app/        # Next.js App Router pages
│   │   │   └── dashboard/  # Main dashboard UI
│   │   ├── components/ # Reusable UI (shadcn/ui)
│   │   └── lib/        # Utilities, API client, integrations
│   └── public/         # Static assets
└── docker-compose.yml  # PostgreSQL + Redis services
```

## Organization Rules

**Backend:**
- API routes → `app/api/`, one file per resource
- Business logic → `app/services/`, organized by domain
- Models → `app/models/`, one model per file
- Tools/integrations → `app/services/tools/`, one class per integration

**Frontend:**
- Pages → `src/app/`, using Next.js App Router
- Components → `src/components/`, reusable UI elements
- Lib → `src/lib/`, utilities, types, config
- One component per file, co-locate related files

## Code Quality - Zero Tolerance

### Backend Quality Checks:
```bash
cd backend
uv run ruff check app tests              # Linting (40+ rules)
uv run mypy app                          # Type checking (strict)
uv run ruff format --check app tests     # Format check
```

Auto-fix:
```bash
uv run ruff check app tests --fix
uv run ruff format app tests
```

### Frontend Quality Checks:
```bash
cd frontend
npm run check    # Runs: eslint + tsc + prettier
```

Auto-fix:
```bash
npm run lint:fix
npm run format
```

### Server Checks:
After changes, verify servers start cleanly:
```bash
# Backend: Check for runtime warnings
cd backend && uv run uvicorn app.main:app --reload

# Frontend: Check for compilation warnings
cd frontend && npm run dev
```

**Fix ALL errors/warnings before continuing!**

## Key Commands

- `/update-app` - Update all dependencies, fix deprecations
- `/check` - Run all quality checks, auto-fix issues
- `make check` - Quick quality check (both backend + frontend)
- `make dev` - Start development environment

## Tech Stack

**Voice & AI**: Pipecat, Deepgram, ElevenLabs, OpenAI, Anthropic Claude, Google Gemini
**Backend**: FastAPI, PostgreSQL 17, Redis, SQLAlchemy 2.0, uv
**Frontend**: Next.js 15, React 19, TypeScript, Tailwind, shadcn/ui
**Telephony**: Telnyx (primary), Twilio (optional)
