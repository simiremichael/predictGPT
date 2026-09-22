# Football AI

A production-ready, AI-powered football (soccer) match prediction platform.

Predicts exact scorelines and match market probabilities (1X2, Over/Under, BTTS)
using a mathematically-transparent Poisson model, with optional AI-driven
news research and injury analysis layered on top as structured features.

## Architecture

The core architectural principle is a **provider abstraction layer** that
decouples the prediction engine from any specific football API.

```
                    ┌──────────────────────┐
                    │   Web / Mobile       │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │       FastAPI        │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ FootballDataProvider │
                    │      Interface       │
                    └──────────┬───────────┘
                               │
                    ┌──────────┴───────────┐
                    ▼                      ▼
               API-Football              Sportmonks
                    │                      │
                    └──────────┬───────────┘
                               ▼
                     Normalized Data
                               │
                               ▼
                 PostgreSQL + Redis (Caching)
                               │
                               ▼
                Prediction Feature Layer
                               │
                               ▼
                  Statistical Models (Poisson)
                               │
                               ▼
           Score Probability Matrix → Top 4 Scores
                               │
                               ▼
               AI Research / Explanation (LLM)
                               │
                               ▼
                       Final Prediction
```

Switching providers requires only changing one environment variable:

```
FOOTBALL_DATA_PROVIDER=api_football   →  api_football
FOOTBALL_DATA_PROVIDER=sportmonks      →  sportmonks
```

No prediction-engine, route, database, or frontend code changes are needed.

---

## Prerequisites

- Docker / Docker Compose
- Python 3.12+ (for local development without Docker)
- PostgreSQL 16+ (if running without Docker)
- Redis 7+ (if running without Docker)
- API keys for at least one football data provider:
  - [API-Football (api-sports)](https://api-sports.io/market/football-api)
  - [Sportmonks Football](https://docs.sportmonks.com/football/)

---

## Quick Start (Docker)

```bash
# 1. Copy the example environment file
cp .env.example .env

# 2. Edit .env and add your API keys
#    FOOTBALL_DATA_PROVIDER=api_football
#    API_FOOTBALL_KEY=your_key_here

# 3. Start all services
docker compose up

# The backend API will be available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

---

## Quick Start (Local / No Docker)

```bash
# 1. Start PostgreSQL and Redis (using your preferred method)

# 2. Set environment variables
cp .env.example .env
# Edit .env with your credentials

# 3. Run database migrations
cd backend
python -m alembic upgrade head

# 4. Start the API server
python -m uvicorn api.main:app --reload --port 8000
```

---

## Project Structure

```
football-ai/
├── apps/
│   ├── web/          # Next.js web application (Phase 8)
│   └── mobile/       # Expo React Native app (Phase 9)
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI app, routers, endpoints
│   │   ├── core/          # Config, exceptions, logging, security
│   │   ├── db/            # SQLAlchemy async engine, Redis client
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── schemas/       # Pydantic response schemas
│   │   ├── repositories/  # Data access layer
│   │   ├── services/      # Business logic services
│   │   ├── prediction/    # Prediction engine (Poisson, score matrix)
│   │   ├── ai/            # LLM integration for research/explanation
│   │   ├── web_research/  # News search and source extraction
│   │   ├── football_data/ # Provider abstraction layer
│   │   │   ├── base.py           # FootballDataProvider ABC
│   │   │   ├── models.py         # Normalized internal models
│   │   │   ├── http_client.py    # Shared HTTP client
│   │   │   ├── league_mappings.py
│   │   │   ├── api_football.py   # API-Football provider
│   │   │   ├── sportmonks.py     # Sportmonks provider
│   │   │   └── factory.py        # Provider factory
│   │   ├── jobs/        # Background sync jobs (Celery/Redis)
│   │   └── utils/
│   ├── alembic/         # Database migrations
│   ├── tests/           # Unit, integration, and contract tests
│   ├── Dockerfile
│   └── requirements.txt
├── packages/
│   └── shared-types/    # Shared TypeScript types
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FOOTBALL_DATA_PROVIDER` | Active provider: `api_football` or `sportmonks` | `api_football` |
| `API_FOOTBALL_KEY` | API-Football API key | (none) |
| `API_FOOTBALL_BASE_URL` | API-Football base URL | `https://v3.football.api-sports.io` |
| `SPORTMONKS_API_TOKEN` | Sportmonks API token | (none) |
| `SPORTMONKS_BASE_URL` | Sportmonks base URL | `https://api.sportmonks.com/v3/football` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://postgres:postgres@localhost:5432/football_ai` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `OPENAI_API_KEY` | OpenAI API key for AI features | (none) |
| `OPENAI_BASE_URL` | OpenAI-compatible endpoint | `https://api.openai.com/v1` |
| `AI_MODEL` | LLM model for research | `gpt-4o-mini` |
| `AI_ATTACK_IMPACT_CAP` | Max absolute attack lambda adjustment | `0.15` |
| `AI_DEFENSE_IMPACT_CAP` | Max absolute defense lambda adjustment | `0.15` |
| `WEB_SEARCH_PROVIDER` | Search provider: `duckduckgo` or `brave` | `duckduckgo` |
| `WEB_SEARCH_API_KEY` | API key for search provider (Brave) | (none) |
| `WEB_SEARCH_BASE_URL` | Search API base URL | `https://api.duckduckgo.com` |
| `RESEARCH_MAX_AGE_HOURS` | Max age of news sources for research | `24` |
| `SOURCE_CREDIBILITY_ENABLED` | Enable source credibility weighting | `true` |
| `ADMIN_API_KEY` | API key for admin endpoints | (none) |
| `APP_ENV` | Environment: `development`, `staging`, `production`, `testing` | `development` |
| `APP_DEBUG` | Enable debug mode | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |

### Switching Providers

```bash
# Switch from API-Football to Sportmonks
FOOTBALL_DATA_PROVIDER=sportmonks \
SPORTMONKS_API_TOKEN=your_token \
python -m uvicorn api.main:app
```

The inactive provider's credentials are optional — if not configured,
it appears as `configured: false` in the health check.

---

## API Endpoints

### Public

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/` | Service info |
| GET | `/api/v1/providers/status` | Provider health & configuration |
| GET | `/api/v1/leagues` | List supported leagues |
| GET | `/api/v1/teams` | List teams |
| GET | `/api/v1/matches` | List upcoming matches |
| GET | `/api/v1/matches/{match_id}` | Match details |
| GET | `/api/v1/matches/{match_id}/prediction` | Get prediction |
| GET | `/api/v1/predictions` | List predictions |
| GET | `/api/v1/performance` | Model performance dashboard |
| GET | `/api/v1/research/{match_id}` | Web research for a match |
| POST | `/api/v1/research/{match_id}` | Trigger research for a match |
| GET | `/api/v1/research/{match_id}/analysis` | Research + AI-adjusted prediction |

### Admin (requires `X-Admin-Api-Key` header)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/admin/providers/compare` | Compare providers' normalized output |

---

## Running Tests

```bash
cd backend

# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=app --cov-report=term-missing

# Run only contract tests
python -m pytest tests/contract/ -v

# Run only unit tests
python -m pytest tests/unit/ -v
```

---

## Database Migrations

```bash
cd backend

# Apply migrations
python -m alembic upgrade head

# Create a new migration
python -m alembic revision --autogenerate -m "Description here"

# Roll back one migration
python -m alembic downgrade -1

# View migration history
python -m alembic history
```

---

## Provider Health Check

```bash
curl http://localhost:8000/api/v1/providers/status
```

```json
{
  "active_provider": "api_football",
  "providers": {
    "api_football": {"configured": true, "healthy": true, ...},
    "sportmonks": {"configured": false, "healthy": false, ...}
  }
}
```

---

## Roadmap (Phases)

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Project foundation, provider abstraction, normalized models | ✅ |
| 2 | API-Football full implementation | ✅ |
| 3 | Sportmonks implementation + contract tests | ✅ |
| 4 | Database sync + prediction engine (Poisson model) | ✅ |
| 5 | Web research + AI adjustment layer | ✅ |
| 6 | Background sync jobs | ⬜ |
| 7 | Backend API endpoints | ✅ |
| 8 | Next.js web application | ⬜ |
| 9 | Expo mobile application | ⬜ |
| 10 | Prediction history | ⬜ |
| 11 | Backtesting system | ⬜ |
| 12 | Performance dashboard | ⬜ |
| 13 | Production hardening | ⬜ |

---

## License

This project is provided for educational and analytical purposes.
Football match predictions are probabilistic and should never be treated
as guaranteed outcomes.
