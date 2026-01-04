# Railway Deployment Guide

Deploy Voice Noob to Railway with PostgreSQL, Redis, and automatic HTTPS.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Railway Project                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  PostgreSQL  │◄───│   Backend    │◄───│    Frontend      │  │
│  │    (DB)      │    │  (FastAPI)   │    │   (Next.js)      │  │
│  └──────────────┘    └──────────────┘    └──────────────────┘  │
│         │                   │                     │             │
│         │            ┌──────────────┐             │             │
│         └───────────►│    Redis     │◄────────────┘             │
│                      │   (Cache)    │                           │
│                      └──────────────┘                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start (5 minutes)

### 1. Install Railway CLI

```bash
# macOS
brew install railway

# npm (any platform)
npm install -g @railway/cli

# Login
railway login
```

### 2. Create Railway Project

```bash
# Create new project
railway init

# Or link to existing project
railway link
```

### 3. Add Services (Railway Dashboard)

Go to your Railway dashboard and add:

1. **PostgreSQL** - Click "New" → "Database" → "PostgreSQL"
2. **Redis** - Click "New" → "Database" → "Redis"
3. **Backend** - Click "New" → "GitHub Repo" → Select `voice-noob` → Set root to `/backend`
4. **Frontend** - Click "New" → "GitHub Repo" → Select `voice-noob` → Set root to `/frontend`

### 4. Configure Environment Variables

#### Backend Service Variables

| Variable | Source | Example |
|----------|--------|---------|
| `DATABASE_URL` | Reference PostgreSQL | `${{Postgres.DATABASE_URL}}` |
| `REDIS_URL` | Reference Redis | `${{Redis.REDIS_URL}}` |
| `SECRET_KEY` | Generate | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ADMIN_EMAIL` | Your email | `admin@yourdomain.com` |
| `ADMIN_PASSWORD` | Secure password | (use strong password) |
| `ADMIN_NAME` | Admin name | `Admin` |

**AI/Voice Provider Keys (add as needed):**
| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | For GPT-4o Realtime |
| `DEEPGRAM_API_KEY` | For speech-to-text |
| `ELEVENLABS_API_KEY` | For text-to-speech |
| `TELNYX_API_KEY` | For phone calls |
| `TELNYX_SIP_USERNAME` | Telnyx SIP credentials |
| `TELNYX_SIP_PASSWORD` | Telnyx SIP credentials |

#### Frontend Service Variables

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `${{Backend.RAILWAY_PUBLIC_DOMAIN}}` with `https://` prefix |
| `NEXT_PUBLIC_WS_URL` | Same as above but with `wss://` prefix |

**Example:**
```
NEXT_PUBLIC_API_URL=https://voice-noob-backend-production.up.railway.app
NEXT_PUBLIC_WS_URL=wss://voice-noob-backend-production.up.railway.app
```

### 5. Deploy

```bash
# Deploy from local (if not using GitHub)
cd backend && railway up
cd frontend && railway up

# Or just push to GitHub - Railway auto-deploys
git push origin main
```

### 6. Run Database Migrations

```bash
# Connect to backend service shell
railway shell -s backend

# Run migrations
alembic upgrade head
```

## Detailed Setup

### PostgreSQL Configuration

Railway provides PostgreSQL 17. The connection string is automatically set via `DATABASE_URL`.

**Important:** Update the backend to use the connection string format:
```
postgresql+asyncpg://user:pass@host:port/database
```

Railway provides `postgres://` format, so the backend config should handle both.

### Redis Configuration

Railway provides Redis 7. The connection string is automatically set via `REDIS_URL`.

### Custom Domain Setup

1. Go to your service in Railway dashboard
2. Click "Settings" → "Domains"
3. Click "Add Custom Domain"
4. Add your domain (e.g., `api.yourdomain.com` for backend)
5. Add DNS CNAME record pointing to Railway domain

### Health Checks

Both services have health check endpoints:
- Backend: `/health`
- Frontend: `/` (default Next.js page)

### Scaling

```bash
# Scale replicas (in railway.toml or dashboard)
[deploy]
numReplicas = 2
```

## Environment Variable Reference

### Backend Complete List

```env
# Database (Required - from Railway PostgreSQL)
DATABASE_URL=postgresql+asyncpg://...

# Redis (Required - from Railway Redis)
REDIS_URL=redis://...

# Security (Required)
SECRET_KEY=your-256-bit-secret-key

# Admin User (Required for first startup)
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=secure-password-here
ADMIN_NAME=Admin

# AI Providers (Add as needed)
OPENAI_API_KEY=sk-...
DEEPGRAM_API_KEY=...
ELEVENLABS_API_KEY=...

# Telephony (Add as needed)
TELNYX_API_KEY=KEY...
TELNYX_API_SECRET=...
TELNYX_SIP_USERNAME=...
TELNYX_SIP_PASSWORD=...

# Optional
SENTRY_DSN=https://...
CORS_ORIGINS=https://your-frontend.railway.app
```

### Frontend Complete List

```env
# API Connection (Required)
NEXT_PUBLIC_API_URL=https://your-backend.railway.app
NEXT_PUBLIC_WS_URL=wss://your-backend.railway.app
```

## Troubleshooting

### Build Failures

```bash
# View build logs
railway logs -s backend

# Common issues:
# 1. Missing dependencies - check pyproject.toml
# 2. Wrong Python version - Dockerfile uses 3.12
# 3. Missing env vars - check Railway dashboard
```

### Database Connection Issues

```bash
# Test database connection
railway shell -s backend
python -c "from app.db.session import engine; print(engine.url)"
```

### WebSocket Issues

Ensure:
1. Backend CORS allows frontend origin
2. `NEXT_PUBLIC_WS_URL` uses `wss://` (not `ws://`)
3. Railway's proxy supports WebSockets (it does by default)

## Costs Estimate

| Service | Estimated Monthly Cost |
|---------|----------------------|
| PostgreSQL | $5-10 (usage-based) |
| Redis | $5-10 (usage-based) |
| Backend | $5-15 (usage-based) |
| Frontend | $5-10 (usage-based) |
| **Total** | **~$20-45/month** |

*Railway billing is usage-based. Start with $5 credit on free tier.*

## CLI Commands Reference

```bash
# Login
railway login

# Create/link project
railway init
railway link

# Deploy
railway up

# View logs
railway logs
railway logs -s backend
railway logs -s frontend

# Open shell
railway shell -s backend

# Run command
railway run -s backend alembic upgrade head

# Open dashboard
railway open

# View variables
railway variables
```

## Production Checklist

- [ ] All API keys are set in Railway dashboard
- [ ] `SECRET_KEY` is a secure random value
- [ ] Database migrations have run
- [ ] CORS is configured for production domains
- [ ] Custom domains are set up (optional)
- [ ] Health checks are passing
- [ ] Sentry is configured for error tracking (optional)
