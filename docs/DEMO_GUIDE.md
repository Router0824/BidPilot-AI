# BidPilot-AI Demo Guide

This guide is for a local Mock-mode demonstration. It does not require an LLM API key.

## Demo Safety Notice

The demo accounts are only for local Mock demonstration and must not be used in production.

## Start In Mock Mode

```bash
cp .env.example .env
BIDPILOT_LLM_PROVIDER=mock ./start.sh
```

When prompted by the starter, choose `n` for the real DeepSeek API question.

Open:

- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs
- Readiness check: http://localhost:8000/health/ready

## Seed Demo Data

```bash
python scripts/seed_demo_data.py
```

The command creates or reuses a project named `BidPilot-AI Mock 演示项目` with:

- One main tender text file.
- One addendum text file that changes the schedule from 120 days to 90 days.
- One qualification material that intentionally lacks the project manager certificate.
- One audited knowledge chunk for local RAG retrieval.

## Demo Login

| Username | Password | Role |
| --- | --- | --- |
| `admin` | `admin123` | System admin |
| `bid_manager` | `bid123` | Bid manager |
| `writer` | `write123` | Writer |
| `reviewer` | `review123` | Reviewer |

These accounts are only for local Mock demonstration and must not be used in production.

## 90-Second Narrative For The Current Build

1. Log in as `bid_manager`.
2. Open `BidPilot-AI Mock 演示项目`.
3. Show the uploaded main tender, addendum, and qualification material.
4. Start the existing fixed workflow in Mock mode.
5. Open Agent Task Center and show the Planner Agent decision block.
6. Point out why `parse_documents` is skipped when seeded files are already parsed.
7. Show which planned nodes require human confirmation.
8. Use the incremental rerun preview to show the addendum impact range.
9. Point out that `parse_documents` is preserved while fact, addendum, requirement, outline, draft, review, and export-readiness nodes are affected.
10. Confirm the high-risk incremental rerun and watch the SSE progress stream.
11. Show addendum conflict detection for the changed schedule.
12. Show extracted requirements and the high-risk qualification requirement.
13. Open Response Evidence Graph and show the requirement coverage matrix.
14. Click a requirement and show the full source document, page, source quote, target section, enterprise material, generated content, and review chain.
15. Generate or inspect an outline and draft.
16. Run review and show uncovered or risky items.
17. Use Fixer on a low-risk citation issue and show the before/after diff.
18. Use Fixer on a high-risk issue and show that it stops for human handling instead of rewriting.
19. Export the current document.

Current limitation: timeout/retry/cost enforcement is planned for a later phase and is not represented as completed in this guide.

## Troubleshooting

- If the frontend cannot call the API, confirm the backend is on `http://localhost:8000` and Vite is on `http://localhost:5173`.
- If login fails, make sure the backend was restarted after changing `BIDPILOT_SECRET_KEY`.
- If readiness fails, delete a corrupted local demo database only when you no longer need its data: `rm bidpilot.db`.
- If Docker frontend cannot reach the backend, use `docker compose up --build` so the nginx config and backend service start together.
- If a real model call fails, switch back to `BIDPILOT_LLM_PROVIDER=mock` and rerun the workflow.
