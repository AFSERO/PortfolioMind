# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## NetWorth - Personal Finance Tracker

A web app for tracking investment portfolios (stocks, forex, gold, crypto, funds, real estate) with real-time prices, visual dashboards, and (Phase 3) an AI financial assistant.

**See `SPEC.md` for detailed Phase 1 requirements, data models, and API contract.**

## Tech Stack
- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.0, Alembic, asyncpg
- **Frontend:** React 18+ (Vite), TypeScript strict mode, shadcn/ui, Tailwind CSS, Recharts, Zustand, React Router v6
- **Database:** PostgreSQL 16
- **Auth:** JWT (HS256) — access token in memory (15 min), refresh token in httpOnly cookie (7 days)
- **AI (Phase 3):** Google Gemini API, LangChain

## Canonical Local Development Runtime
Standardized runtime architecture:
- **Full Stack in Docker Compose**: PostgreSQL 16 (`db`), FastAPI Backend (`backend`), React/Vite Frontend (`frontend`).
- **Codex CLI**: Containerized Linux Codex CLI installed via `@openai/codex` inside the `backend` image.
- **Persistent Auth**: Named Docker volume `codex_data` mounted at `/root/.codex` preserves the Codex login session across container lifecycles.

## Commands
```bash
# 1. Full Stack Startup (Canonical)
docker compose up -d --build

# 2. One-Time Container Codex Login (Device Auth)
docker compose run --rm backend codex login --device-auth
# Verify login status safely without exposing tokens:
docker compose run --rm backend codex login status

# 3. View Logs / Status
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend

# 4. Stop Stack
docker compose down

# 5. Tests
cd backend && pytest
cd backend && pytest tests/test_auth.py          # single file
cd backend && pytest -k "test_login"             # single test
cd frontend && npm test
cd frontend && npm test -- --run                 # vitest single run (no watch)
```



## Architecture

### Backend: Service Layer Pattern
```
routers/ → services/ → models/
```
Routers handle HTTP, services hold business logic, models are SQLAlchemy ORM. All handlers and DB operations must be async.

### API Response Format
```json
{"status": "success", "data": {...}}
{"status": "error", "message": "..."}
```

### Price Fetching (utils/)
| Asset Type | Provider | Notes |
|---|---|---|
| Forex | ExchangeRate-API | Free: 1500 req/month |
| Crypto | CoinGecko | Free, no key needed |
| Gold | MetalPriceAPI / CollectAPI | Free tier |
| Stocks (BIST) | yfinance | Append `.IS` suffix (e.g. `THYAO.IS`) |
| Funds / Real Estate | Manual entry | User sets current value |

Price fetching rules: async with retry, 5-min in-memory cache, fallback to last known price with "last updated" timestamp.

### Asset Types Enum
`STOCK`, `FOREX`, `GOLD`, `CRYPTO`, `FUND`, `REAL_ESTATE`, `CUSTOM`

### Frontend State
- Zustand for global state
- All API calls go through `services/` directory only
- Custom hooks for data fetching (useQuery pattern)
- shadcn/ui components exclusively — never build custom UI when shadcn has a component

### UI/UX Requirements
- Loading skeletons while data fetches
- Toast notifications for success/error actions
- Green for profit, red for loss
- Currency formatting: locale-based (e.g. `1.234,56` for TRY)
- Responsive (mobile-first), dark mode supported via shadcn

## Important Rules
- Always run `alembic upgrade head` after model changes
- All monetary values stored as `DECIMAL(18,6)` — never float
- Always validate user ownership before returning any asset data
- DB indexes required on: `user_id`, `asset_type`, `symbol`, `snapshot_date`
- Auth endpoints rate-limited to 5 req/min
- CORS restricted to frontend origin only
- When compacting, preserve the list of modified files, current phase progress, and any open issues

## Development Phases
- **Phase 1 (current):** Investment portfolio tracker — auth, CRUD assets, real-time prices, dashboard with charts
- **Phase 2:** Income & expense tracking — manual entry, credit card statement parsing, categorization
- **Phase 3:** AI chatbot — RAG-based assistant using Gemini API + LangChain

## Environment Variables
Copy `.env.example` to `.env`. Key variables:
- `DATABASE_URL` — asyncpg connection string
- `SECRET_KEY` — JWT signing key
- `EXCHANGE_RATE_API_KEY` — for forex prices
- `VITE_API_URL` — frontend points to backend (default: `http://localhost:8000/api`)
