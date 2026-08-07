# Qoder Build Log

This log records only development activity that actually happened in this workspace.

## 2026-08-07 ModelScope Release Pack

- Qoder added the standalone `modelscope_release/` folder for ModelScope Community publishing:
  - `README.md`
  - `.env.example`
  - `Dockerfile`
  - `server.py`
  - `start.sh`
  - `API_PACKAGING.md`
- Qoder added `.dockerignore` so Docker builds do not include local databases, uploads, frontend build output, caches, `.env` files, or secret key files.
- Qoder implemented `modelscope_release/server.py` to import the existing FastAPI app, serve built Vue assets, and return the SPA index for frontend routes.
- Qoder adjusted the release wrapper so `/` serves the Vue frontend rather than the backend JSON root route.
- Qoder did not store the API key pasted in chat. A secret-prefix scan found no matching key material in repository files.
- Validation performed:
  - `python -m compileall app scripts modelscope_release`
  - `npm run build`
  - local release wrapper startup on port `8013`
  - `/health/ready`
  - `GET /`
  - `GET /project/demo/workflow?demo=1`
  - release directory cleanup for generated `__pycache__`
- Docker build was attempted with `docker build -f modelscope_release/Dockerfile -t bidpilot-ai:modelscope-test .`, but Docker daemon was not running in the local environment.
- No git commit metadata was recorded because this workspace is not a git repository.
- No screenshots or performance claims were generated.

## 2026-08-07 Final Demo Visual Polish

- Qoder updated `frontend/src/components/DemoRemote.vue`:
  - centered the countdown number and `SEC` label inside the timer ring
  - switched the countdown number to tabular numerals to avoid horizontal jitter
  - tightened remote padding, ring size, and text hierarchy
- Qoder updated `frontend/src/pages/WorkflowPage.vue`:
  - increased the contrast of the 90-second Agent decision hero
  - strengthened title and supporting-copy legibility
  - added a darker readable overlay and text shadow
  - made the status card surface more opaque and consistent
- Validation performed:
  - `npm run build`
  - `python -m compileall app scripts`
  - local Vite response check with `curl -I http://127.0.0.1:5173/`
- No git commit metadata was recorded because this workspace is not a git repository.
- No screenshots or performance claims were generated.

## 2026-08-07 Demo Focus Auto Scroll

- Qoder added `frontend/src/demoScroll.js` with a reusable `scrollDemoFocus` helper.
- Qoder updated `frontend/src/pages/WorkflowPage.vue` so Demo mode scrolls to the Planner focus or incremental-preview focus when entering or changing demo steps.
- Qoder updated `frontend/src/pages/EvidenceMatrixPage.vue` so Demo mode scrolls to the evidence-chain focus after loading or selecting a requirement row.
- Qoder updated `frontend/src/pages/ReviewsPage.vue` so Demo mode scrolls to Reviewer/Fixer focus after preparing or loading review data.
- Validation performed:
  - `npm run build`
  - `python -m compileall app scripts`
  - local Vite response check with `curl -I http://127.0.0.1:5173/`
- No git commit metadata was recorded because this workspace is not a git repository.
- No screenshots or performance claims were generated.

## 2026-08-07 Demo Remote

- Qoder added `frontend/src/components/DemoRemote.vue`, a fixed bottom-right demo controller with:
  - current demo step
  - 90-second countdown
  - progress dots
  - timer reset
  - next-step navigation
  - project-detail and exit actions
- Qoder updated `frontend/src/pages/MainLayout.vue` so the remote appears only when `?demo=1` is present and a project id exists in the current route.
- Validation performed:
  - `npm run build`
  - `python -m compileall app scripts`
  - local Vite response check with `curl -I http://127.0.0.1:5173/`
- No git commit metadata was recorded because this workspace is not a git repository.
- No screenshots or performance claims were generated.

## 2026-08-07 Demo Mode Preheat

- Qoder updated `frontend/src/pages/ProjectDetailPage.vue` with a Demo preheat control that calls existing APIs to prepare:
  - addendum conflict detection
  - workflow impact preview
  - coverage matrix rebuild
  - full review
  - up to two low-risk auto-fix attempts
- Qoder updated `frontend/src/pages/WorkflowPage.vue` so `?demo=1&step=impact` automatically prepares an addendum impact preview when entering the page.
- Qoder updated `frontend/src/pages/EvidenceMatrixPage.vue` so Demo mode rebuilds an empty matrix and selects the first evidence-chain row when possible.
- Qoder updated `frontend/src/pages/ReviewsPage.vue` so Demo mode prepares a review and low-risk Fixer records if the page has no review/fix data yet.
- Validation performed:
  - `npm run build`
  - `python -m compileall app scripts`
  - temporary backend startup on port `8012`
  - `/health/ready`
  - verified a blank project rebuild returns `rebuilt_links: 0`
  - verified the Mock demo project has 3 documents and 1 addendum
  - verified coverage rebuild on the Mock demo project returned `rebuilt_links: 1`
  - verified addendum impact preview returned 10 affected nodes, 1 unaffected node, and `confirmation_required: true`
  - verified full review on the Mock demo project returned 8 findings, including 1 high-risk finding
- No git commit metadata was recorded because this workspace is not a git repository.
- No screenshots or performance claims were generated.

## 2026-08-07 Demo Mode Guided Tour

- Qoder added `frontend/src/components/DemoGuide.vue`, a reusable sticky guide bar for the 90-second demo flow.
- Qoder updated `frontend/src/pages/ProjectDetailPage.vue` with a `DEMO MODE` launch panel and four guided entry points:
  - Agent plan graph
  - addendum incremental preview
  - evidence-chain matrix
  - Reviewer/Fixer loop
- Qoder updated `frontend/src/pages/WorkflowPage.vue` to read `?demo=1&step=planner|impact`, show the guide bar, and highlight Planner or incremental rerun areas.
- Qoder updated `frontend/src/pages/EvidenceMatrixPage.vue` to read `?demo=1`, show the guide bar, and focus the evidence-chain detail panel.
- Qoder updated `frontend/src/pages/ReviewsPage.vue` to read `?demo=1`, show the guide bar, and focus Reviewer findings plus Fixer diff records.
- Validation performed:
  - `npm run build`
  - `python -m compileall app scripts`
  - local Vite response check with `curl -I http://127.0.0.1:5173/`
- No git commit metadata was recorded because this workspace is not a git repository.

## 2026-08-07 Dashboard Filter And Consultation Citation Fix

- Qoder fixed the project dashboard status filter wiring:
  - `frontend/src/stores/app.js` now supports `fetchProjects({ status })`
  - `frontend/src/pages/DashboardPage.vue` reloads projects when the selected status changes
  - the empty state now reflects active filtering
- Qoder fixed repeated consultation citations:
  - `app/application/consultation_service.py` now deduplicates citations before saving assistant messages
  - `frontend/src/pages/ConsultationPage.vue` deduplicates citations while rendering, so older stored duplicate messages are also displayed cleanly
- Validation performed:
  - `npm run build`
  - `python -m compileall app scripts`
  - temporary backend startup on port `8011`
  - `/health/ready`
  - `GET /api/v1/projects?status=active`
  - `GET /api/v1/projects?status=completed`
  - local citation dedupe check
- No git commit metadata was recorded because this workspace is not a git repository.

## 2026-08-07 Workflow And Evidence Demo Stage Polish

- Qoder refined `frontend/src/pages/WorkflowPage.vue` into a 90-second demo control stage with:
  - Agent mission hero
  - workflow status pulse
  - live event feed
  - selected-node execution runway
  - Planner decision map
  - incremental rerun scoreboard
  - clearer affected and unaffected node lanes
- Qoder refined `frontend/src/pages/EvidenceMatrixPage.vue` into a traceability main stage with:
  - coverage hero metrics
  - dense requirement matrix
  - persistent evidence-chain detail panel
  - explicit source-to-review chain path
  - empty state for guided demo narration
- Validation performed:
  - `npm run build`
- No git commit metadata was recorded because this workspace is not a git repository.
- No screenshots or performance claims were generated.

## 2026-08-07

- Qoder inspected the current repository structure under `/Users/aaa/Desktop/BidPilot-AI-main`.
- Qoder reviewed the FastAPI entrypoint, settings, database initialization, domain models, workflow engine, workflow service, Agent gateway, addendum detection, progress/SSE code, document parsing, knowledge retrieval, review/export service, frontend workflow page, Docker Compose, startup script, and environment example.
- Qoder identified that workflow timeout, retry, backoff, and node-level cost settings are declared but not fully enforced by the workflow execution service.
- Qoder identified that the current workflow is a fixed recursive chain and does not yet include a Planner Agent, dynamic dependency graph, or incremental invalidation model.
- Qoder identified documentation issues: old repository path, mixed project naming, missing explicit production warning for demo accounts, and incomplete demo data initialization guidance.
- Qoder changed:
  - `app/main.py`: readiness now executes a database `SELECT 1` and reports the configured LLM provider.
  - `.env.example`: normalized local development defaults for BidPilot-AI and Mock mode.
  - `scripts/seed_demo_data.py`: added an idempotent local Mock demo data seed command.
  - `docs/DEMO_GUIDE.md`: added local demo startup, seed, login, narrative, and troubleshooting notes.
  - `docs/QODER_BUILD_LOG.md`: added this factual build log.
  - `README.md`: refreshed startup, configuration, demo, and roadmap documentation.
- No git commit metadata was recorded because this workspace is not a git repository.

## 2026-08-07 Frontend Interaction Refresh

- Qoder reviewed the referenced Apple-style design note at `https://getdesign.md/apple/design-md`, especially its emphasis on premium white space, SF Pro-like typography, cinematic restraint, and monochrome luxury direction.
- Qoder updated the global visual tokens in `frontend/src/App.vue`:
  - switched to Apple-system font stacks
  - moved from dark command-center colors to light neutral surfaces
  - standardized pill buttons, subtle borders, blur, and soft shadows
  - improved focus and active states
- Qoder updated `frontend/src/pages/MainLayout.vue`:
  - converted the dark sidebar into a light translucent sidebar
  - added sticky desktop navigation
  - made active navigation feel like a selected macOS-style surface
- Qoder updated `frontend/src/pages/LoginPage.vue` with a cleaner light background, glass card, monochrome brand mark, rounded controls, and softer depth.
- Qoder updated `frontend/src/pages/DashboardPage.vue` with a calmer hero strip, translucent toolbar, and elevated project cards.
- Qoder updated `frontend/src/pages/ProjectDetailPage.vue` to align the project header, metric cards, sections, node chips, and quick action cards with the lighter design system.
- Qoder updated `frontend/src/components/ApiActivity.vue` from a dark command overlay to a light notification-center style panel.
- Validation performed:
  - `npm run build`
  - `python -m compileall app scripts`
  - temporary Vite dev server on `http://127.0.0.1:5173/`
  - `curl -I http://127.0.0.1:5173/` returned HTTP 200
- No git commit metadata was recorded because this workspace is not a git repository.

## 2026-08-07 Phase Six

- Qoder updated `app/workflows/workflow_service.py` so workflow node execution now uses `asyncio.wait_for` with each node's configured `timeout_seconds`.
- Qoder implemented retry handling using each node's `max_retries` and `retry_backoff_seconds`.
- Qoder added basic error classification:
  - timeout: retryable
  - runtime error: retryable until max attempts
  - validation error: non-retryable
  - cost limit exceeded: manual handling
- Qoder added cost-limit checks before each node attempt using configured project/node cost limits and current token-cost estimates.
- Qoder added per-process node concurrency protection to block duplicate execution of the same node in the same workflow run.
- Qoder added same-run idempotency reuse for already succeeded or waiting-confirmation node results.
- Qoder extended workflow status node payloads with `error_code` and structured `_execution` metadata from node snapshots.
- Qoder added SSE progress phases for retry, retry start, failure, idempotent reuse, waiting confirmation, and workflow completion.
- Validation performed:
  - `python -m compileall app scripts`
  - `npm run build`
  - in-process WorkflowService verification where a node failed once, retried with configured zero delay, then succeeded
  - in-process cost-limit verification where a node returned `manual_required` with `cost_limit_exceeded`
  - temporary backend startup on port `8010`
  - workflow status API check
  - `/health/ready`
- No git commit metadata was recorded because this workspace is not a git repository.

## 2026-08-07 Phase Five

- Qoder added `FixAttempt` to `app/domain/models.py` to persist before/after content, diff, reason, issue id, section id, status, and human-confirmation state for each Fixer action.
- Qoder updated `app/application/review_export_service.py`:
  - mapped Review findings to structured issue types including `missing_requirement`, `internal_conflict`, `numeric_inconsistency`, `citation_missing`, and `unsupported_claim`
  - added `FixerService`
  - limited automatic fixes to low-risk `citation_missing`
  - blocked high-risk or commitment-related issues from automatic rewriting
  - enforced a maximum of two applied automatic fixes per section
  - recorded every attempt with a simple before/after line diff
- Qoder updated `app/api/v1/bid.py` with:
  - `GET /projects/{project_id}/fixes`
  - `POST /projects/{project_id}/reviews/findings/{finding_id}/fix`
- Qoder updated `frontend/src/stores/app.js` and `frontend/src/pages/ReviewsPage.vue` so the review center can invoke Fixer, show auto-fix/manual-required state, and compare before/after content.
- During validation, Qoder created local verification-only review findings in the demo project:
  - one medium-risk `citation_missing`
  - one high-risk `unsupported_claim`
- Validation performed:
  - `python -m compileall app scripts`
  - `npm run build`
  - temporary backend startup on port `8010`
  - low-risk Fixer API returned `applied`, `auto_fix_allowed=true`, and a non-empty diff
  - high-risk Fixer API returned `manual_required`, `auto_fix_allowed=false`, and did not rewrite content
  - `GET /fixes`
  - `/health/ready`
- No git commit metadata was recorded because this workspace is not a git repository.

## 2026-08-07 Phase Four

- Qoder added `CoverageStatus` and `RequirementEvidenceLink` to `app/domain/models.py`.
- Qoder added `app/application/evidence_service.py` to rebuild and query requirement evidence links from existing requirements, document pages, outline sections, draft versions, knowledge citations, scoring items, and review findings.
- Qoder added coverage APIs in `app/api/v1/bid.py`:
  - `GET /projects/{project_id}/coverage-matrix`
  - `POST /projects/{project_id}/coverage-matrix/rebuild`
  - `GET /projects/{project_id}/requirements/{requirement_id}/evidence-chain`
- Qoder added frontend store methods and route support for the evidence matrix.
- Qoder added `frontend/src/pages/EvidenceMatrixPage.vue`, showing requirement text, source page, source quote, type, score, risk, target section, enterprise materials, coverage status, review issue count, confidence, and click-through evidence-chain details.
- Qoder added a Project Detail entry point named `响应证据图谱`.
- During validation, Qoder found repeated local demo runs had duplicate records. Qoder made `scripts/seed_demo_data.py` and evidence source-page lookup tolerant of existing duplicate local data.
- During validation, Qoder improved source-section inference so the seeded qualification requirement resolves to `资格要求` rather than a nearby fact line.
- Validation performed:
  - `python -m compileall app scripts`
  - `python scripts/seed_demo_data.py`
  - `npm run build`
  - temporary backend startup on port `8010`
  - `POST /coverage-matrix/rebuild`
  - `GET /coverage-matrix`
  - `GET /requirements/{requirement_id}/evidence-chain`
  - `/health/ready`
- No git commit metadata was recorded because this workspace is not a git repository.

## 2026-08-07 Phase Three

- Qoder extended `NodeDefinition` in `app/workflows/engine.py` with `inputs`, `outputs`, `dependencies`, `invalidated_by`, `risk_level`, `requires_human_confirmation`, and `idempotency_key`.
- Qoder added `app/workflows/dependency_graph.py` to calculate changed signals, propagate invalidation through node dependencies, and split affected vs unaffected nodes.
- Qoder added the `workflow_impact_previews` ORM model in `app/domain/models.py` to persist execution-preview decisions.
- Qoder updated `app/workflows/workflow_service.py` with impact preview creation and confirmed incremental rerun execution using a saved plan.
- Qoder updated `app/api/v1/workflows.py` with:
  - `POST /projects/{project_id}/workflow/impact-preview`
  - `POST /projects/{project_id}/workflow/incremental-rerun`
- Qoder updated `frontend/src/stores/app.js` and `frontend/src/pages/WorkflowPage.vue` so the UI can preview affected nodes, show unaffected preserved nodes, and require confirmation before high-risk incremental execution.
- During API verification, Qoder found JSON serialization failed because a preview timestamp was embedded in a JSON column. Qoder fixed preview serialization to use string timestamps.
- During API verification, Qoder tightened addendum signals so an already parsed addendum does not rerun `parse_documents`; it invalidates downstream facts, addendum conflict detection, requirements, matrix, outline, retrieval, draft, review, and export readiness.
- Validation performed:
  - `python -m compileall app scripts`
  - `npm run build`
  - temporary backend startup on port `8010`
  - `POST /impact-preview` for the seeded addendum
  - confirmed affected nodes exclude `parse_documents`
  - confirmed high-risk incremental rerun without confirmation returns HTTP `409`
  - confirmed `confirm_high_risk=true` starts `tender_incremental`
  - `/health/ready`
- No git commit metadata was recorded because this workspace is not a git repository.
- No screenshots or performance claims were generated.

## Rejected Or Deferred Suggestions

- Deferred Planner Agent implementation to phase two to avoid a broad rewrite during phase one.
- Deferred database schema changes for evidence graph and incremental workflow state to later phases, where migrations or compatibility handling can be designed together.
- Deferred test-suite creation to the dedicated testing phase, while still running import/startup/build checks for this phase.

## 2026-08-07 Phase Two

- Qoder added `app/agents/planner_agent.py` with Pydantic-validated Planner output models, registered-node validation, deterministic Mock planning, and safe fixed-workflow fallback.
- Qoder added the `workflow_plans` ORM model in `app/domain/models.py` to persist Planner decisions without changing existing workflow tables.
- Qoder updated `app/workflows/workflow_service.py` so workflow startup first asks the Planner for selected/skipped nodes, saves the decision, emits a Planner progress event, and executes only the selected registered nodes.
- Qoder updated workflow resume logic so a paused planned workflow continues along the saved Planner sequence where available.
- Qoder updated `frontend/src/pages/WorkflowPage.vue` to show the Planner goal, risk level, fallback state, selected-node reasons, skipped-node reasons, human-confirmation nodes, and dependency edges.
- During API verification, Qoder found the Mock Planner was selecting `parse_documents` even when seeded demo files were already parsed. Qoder changed the Mock Planner to skip parsing when all files are already parsed and record the skip reason instead.
- Validation performed:
  - `python -m compileall app scripts`
  - `python scripts/seed_demo_data.py`
  - temporary backend startup on port `8010`
  - login and workflow start through HTTP API
  - workflow status inspection confirming `planner_plan`
  - `/health/ready`
  - `npm run build`
- No git commit metadata was recorded because this workspace is not a git repository.
