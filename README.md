---
domain:
  - nlp
tags:
  - agent
  - fastapi
  - vue
  - bid-document
deployspec:
  entry_file: app.py
license: Apache License 2.0
---

# BidPilot-AI

BidPilot-AI is a FastAPI + Vue 3 platform for AI-assisted bid document preparation. The current build supports document upload and parsing, requirement and fact extraction, addendum conflict detection, outline and draft generation, review, export, enterprise knowledge retrieval, SSE workflow progress, and a local Mock LLM mode for demos without API keys.

This repository directory is `BidPilot-AI-main`.

## Current Architecture

```text
Vue 3 frontend
  -> REST / SSE / WebSocket
FastAPI backend
  -> SQLAlchemy Async ORM
  -> SQLite local database
  -> Agent abstraction with Mock or OpenAI-compatible LLM gateway
  -> Fixed workflow engine retained as the stable fallback path
```

Core paths:

- Backend entrypoint: `app/main.py`
- Settings: `app/core/config.py`
- Database initialization: `app/core/database.py`
- Domain models: `app/domain/models.py`
- Workflow definition: `app/workflows/engine.py`
- Workflow execution service: `app/workflows/workflow_service.py`
- Agents: `app/agents/`
- Frontend: `frontend/`

## Requirements

- Python 3.12+
- Node.js 18+
- npm
- Docker and Docker Compose, optional

## Local Startup

```bash
cp .env.example .env
pip install -r requirements.txt
cd frontend && npm install && cd ..
./start.sh
```

When the starter asks whether to enable the real DeepSeek API:

- Choose `n` for Mock mode. This is the recommended local demo path and does not call external models.
- Choose `y` only when you have a valid API key.

Open:

- Frontend: http://localhost:5173
- Backend API docs: http://localhost:8000/docs
- Liveness: http://localhost:8000/health/live
- Readiness: http://localhost:8000/health/ready

## Manual Startup

Backend:

```bash
cp .env.example .env
BIDPILOT_LLM_PROVIDER=mock python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Docker Compose Startup

```bash
docker compose up --build
```

Docker ports:

- Frontend: http://localhost
- Backend: http://localhost:8080
- Backend docs: http://localhost:8080/docs

The Compose file uses SQLite volumes for local persistence. For production, replace the default secret key, demo users, CORS settings, and database/storage configuration.

## Mock Mode

Mock mode is enabled by default:

```bash
BIDPILOT_LLM_PROVIDER=mock
BIDPILOT_LLM_API_KEY=
```

In this mode, rule-based fallbacks and Mock LLM responses allow local workflow demos without API keys or model spend.

## Real Model Mode

Use an OpenAI-compatible provider such as DeepSeek:

```bash
BIDPILOT_LLM_PROVIDER=deepseek
BIDPILOT_LLM_API_KEY=your_api_key
BIDPILOT_LLM_BASE_URL=https://api.deepseek.com
BIDPILOT_LLM_FAST_MODEL=deepseek-v4-flash
BIDPILOT_LLM_QUALITY_MODEL=deepseek-v4-pro
```

Then start the backend:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Database Initialization

The backend calls `init_db()` on startup and creates missing SQLite tables with SQLAlchemy `create_all`.

Default database:

```bash
sqlite+aiosqlite:///./bidpilot.db
```

No schema migration is required for the phase-one changes in this repository snapshot.

## Demo Data

Initialize local Mock demo data:

```bash
python scripts/seed_demo_data.py
```

The command is idempotent by project name and creates:

- A main tender file.
- An addendum changing project duration from 120 days to 90 days.
- A qualification material with an intentional high-risk missing certificate.
- An audited knowledge chunk for local retrieval.

See [docs/DEMO_GUIDE.md](docs/DEMO_GUIDE.md) for the full local demo flow.

## Demo Accounts

These accounts are only for local Mock demonstration and must not be used in production.

| Username | Password | Role |
| --- | --- | --- |
| `admin` | `admin123` | System admin |
| `bid_manager` | `bid123` | Bid manager |
| `writer` | `write123` | Writer |
| `reviewer` | `review123` | Reviewer |

## Useful Commands

Backend import check:

```bash
python -m compileall app scripts
```

Backend startup check:

```bash
BIDPILOT_LLM_PROVIDER=mock python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend build:

```bash
cd frontend
npm run build
```

## Troubleshooting

- `401` from APIs: log in again and confirm the frontend has a token in local storage.
- Frontend API errors in local dev: confirm the backend is on `http://localhost:8000`.
- Docker backend not reachable from browser: use `http://localhost:8080/docs`, not port 8000.
- Readiness check fails: check `BIDPILOT_DATABASE_URL` and filesystem permissions for `bidpilot.db`.
- Real LLM fails: switch to `BIDPILOT_LLM_PROVIDER=mock` to keep the demo running.
- Old local data causes confusion: stop the app and remove `bidpilot.db` only if you do not need the previous local data.

## Roadmap For This Iteration

The fixed workflow remains available as a stable fallback. Planned follow-up phases will add:

- Planner Agent with Pydantic-validated JSON decisions.
- Dynamic workflow dependencies and incremental rerun.
- Requirement evidence graph and coverage matrix.
- Structured Reviewer and bounded Fixer loop.
- Real enforcement of node timeout, retry, backoff, cost, and idempotency.
- Lightweight and enhanced RAG modes.
- Backend tests, frontend build checks, and GitHub Actions.
- A 90-second hackathon demo dashboard using computed metrics only.
