# BidPilot-AI ModelScope Release Pack

This folder is a standalone deployment pack for publishing BidPilot-AI to ModelScope Community or any Docker-based demo platform.

It keeps secrets out of the repository. Do not commit API keys. Configure real model access through environment variables on the platform.

## What This Pack Provides

- Single-container Docker build for backend API and built Vue frontend.
- FastAPI static frontend wrapper.
- Mock LLM mode for public demos without API keys.
- Real LLM mode through OpenAI-compatible API settings.
- Demo data seeding command.
- Safe `.env.example` with placeholders only.

## Files

| File | Purpose |
| --- | --- |
| `Dockerfile` | Builds frontend, backend, and release wrapper into one image. |
| `server.py` | Imports the existing FastAPI app and serves Vue static files. |
| `start.sh` | Starts the release server. |
| `.env.example` | Safe environment variable template. |
| `API_PACKAGING.md` | How to encapsulate your API provider safely. |

## Local Build

Run from the project root:

```bash
docker build -f modelscope_release/Dockerfile -t bidpilot-ai:modelscope .
docker run --rm -p 7860:7860 --env-file modelscope_release/.env.example bidpilot-ai:modelscope
```

Open:

```text
http://localhost:7860
```

## Mock Demo Mode

Default release mode is Mock LLM:

```bash
BIDPILOT_LLM_PROVIDER=mock
```

This mode does not call external APIs and is suitable for public community demos.

## Real Model Mode

Set these variables in ModelScope platform settings:

```bash
BIDPILOT_LLM_PROVIDER=openai
BIDPILOT_LLM_API_KEY=<set-in-platform-secret>
BIDPILOT_LLM_BASE_URL=https://api.openai.com/v1
BIDPILOT_LLM_MODEL=gpt-4o-mini
BIDPILOT_LLM_FAST_MODEL=gpt-4o-mini
BIDPILOT_LLM_QUALITY_MODEL=gpt-4o
```

For DeepSeek-compatible mode:

```bash
BIDPILOT_LLM_PROVIDER=deepseek
BIDPILOT_LLM_API_KEY=<set-in-platform-secret>
BIDPILOT_LLM_BASE_URL=https://api.deepseek.com
BIDPILOT_LLM_MODEL=deepseek-v4-flash
BIDPILOT_LLM_FAST_MODEL=deepseek-v4-flash
BIDPILOT_LLM_QUALITY_MODEL=deepseek-v4-pro
```

Never paste a real key into this folder.

## Demo Data

Inside a running container:

```bash
python scripts/seed_demo_data.py
```

Local demo accounts are for Mock demos only and must not be used in production.

## Health Check

```text
GET /health/live
GET /health/ready
```

## Recommended ModelScope Settings

- Port: `7860`
- Start command: `/release/start.sh`
- Secret variables:
  - `BIDPILOT_SECRET_KEY`
  - `BIDPILOT_LLM_API_KEY` if using a real model
- Public demo variables:
  - `BIDPILOT_LLM_PROVIDER=mock`

