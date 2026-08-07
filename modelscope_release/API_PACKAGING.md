# API Packaging Guide

Use this guide to package your model API into BidPilot-AI safely for ModelScope Community.

## Security Rule

Do not hard-code API keys in:

- source code
- README files
- Dockerfile
- `.env.example`
- frontend code
- screenshots or logs

If a key was pasted into chat, rotate it in the provider console before publishing.

## Supported API Shape

BidPilot-AI uses an OpenAI-compatible chat completions gateway internally:

```text
POST {BIDPILOT_LLM_BASE_URL}/chat/completions
Authorization: Bearer {BIDPILOT_LLM_API_KEY}
```

The existing backend reads these variables:

```bash
BIDPILOT_LLM_PROVIDER=openai
BIDPILOT_LLM_API_KEY=<platform-secret>
BIDPILOT_LLM_BASE_URL=https://your-provider.example/v1
BIDPILOT_LLM_MODEL=your-default-model
BIDPILOT_LLM_FAST_MODEL=your-fast-model
BIDPILOT_LLM_QUALITY_MODEL=your-quality-model
```

## Recommended Public Setup

For a public ModelScope demo, start with:

```bash
BIDPILOT_LLM_PROVIDER=mock
```

This lets users test the full Agent flow without consuming your API quota.

## Recommended Private Setup

For a private authenticated deployment, configure:

```bash
BIDPILOT_LLM_PROVIDER=openai
BIDPILOT_LLM_API_KEY=<secret>
BIDPILOT_LLM_BASE_URL=https://api.openai.com/v1
BIDPILOT_LLM_FAST_MODEL=gpt-4o-mini
BIDPILOT_LLM_QUALITY_MODEL=gpt-4o
BIDPILOT_LLM_COST_LIMIT_PER_PROJECT=1.5
BIDPILOT_LLM_ESTIMATED_COST_PER_1K_TOKENS=0.002
```

## Validation Checklist

Before upload:

```bash
npm --prefix frontend run build
python -m compileall app scripts
docker build -f modelscope_release/Dockerfile -t bidpilot-ai:modelscope .
docker run --rm -p 7860:7860 --env-file modelscope_release/.env.example bidpilot-ai:modelscope
```

Then verify:

```text
http://localhost:7860/health/ready
http://localhost:7860
```

