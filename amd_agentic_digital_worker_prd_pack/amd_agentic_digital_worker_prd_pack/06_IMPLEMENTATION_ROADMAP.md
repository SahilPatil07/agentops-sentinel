# Implementation Roadmap

Build in vertical slices. Do not ask Copilot to generate the entire
repository in one enormous pass and then act surprised when it invents a
framework inside a framework.

## Phase 0 --- Repository foundation

Deliver: - package configuration - settings and `.env.example` - FastAPI
app and health endpoint - domain schemas - logging and error response
convention - README skeleton - CI for lint, type checks, and tests

Exit gate: app starts locally; health test passes; no secrets committed.

## Phase 1 --- Deterministic incident workflow

Deliver: - incident create/read endpoints - SQLite persistence -
deterministic mock provider - explicit state graph - seeded incident
data and tools - structured incident report - trace events

Exit gate: end-to-end workflow passes without network access or paid API
credentials.

## Phase 2 --- RAG

Deliver: - knowledge corpus with at least 8 realistic runbooks/past
incidents - document ingestion and chunk metadata - local embedding
adapter and vector index - retrieval tests and source citations -
low-evidence abstention

Exit gate: report citations refer to actual indexed chunks; no
fabricated sources.

## Phase 3 --- Tool calling and guardrails

Deliver: - typed allowlisted tools - log, metric, and past-incident
adapters - bounded retries/timeouts - tool budgets and duplicate-call
detection - prompt-injection tests - simulated remediation and approval
flow

Exit gate: all safety tests pass; no simulated write action can run
without current approval.

## Phase 4 --- Real LLM provider

Deliver: - one provider adapter first - structured outputs/function
calling - configuration through environment variables - provider errors
and usage metadata - opt-in live tests

Exit gate: mock path remains fully tested; live provider is optional.

## Phase 5 --- Evaluation and observability

Deliver: - fixed JSONL evaluation set - metric calculations - raw run
records and Markdown report - trace inspection endpoint - latency
breakdown - redaction tests

Exit gate: one command runs evaluation and writes a reproducible report.

## Phase 6 --- Deployment and developer experience

Deliver: - Dockerfile and Docker Compose - CI pipeline - Makefile
commands - setup guide and troubleshooting guide - API
examples/OpenAPI - demo script and sample outputs

Exit gate: clean clone can be started using documented commands.

## Phase 7 --- Portfolio polish

Deliver: - architecture diagram - short demo video/GIF - sample
evaluation report clearly labeled with environment/provider - design
decisions and limitations - GitHub issue board and roadmap - resume
bullets only for features actually implemented

Exit gate: a reviewer can understand the problem, run the app, inspect
tests, and verify evidence within five minutes.

## Suggested weekly plan

Week 1: foundation + deterministic workflow\
Week 2: retrieval + citations\
Week 3: tools + approval gates + safety tests\
Week 4: real provider + evaluation\
Week 5: deployment, docs, demo, cleanup

Adjust the timeline to your availability. Correctness beats a rushed
collection of folders.
