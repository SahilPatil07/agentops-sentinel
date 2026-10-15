# AgentOps Sentinel

A personal project for evidence-grounded investigation of simulated incidents.
The planned system combines RAG, bounded LangGraph workflows,
typed diagnostic tools, human approval, and reproducible evaluation. It is not a
production incident-response service or an enterprise-certified product.

## Current Status

Phase 0 provides the Python package, validated settings, FastAPI health endpoints,
bounded incident input contracts, safe JSON error responses, request correlation,
structured HTTP logs, tests, and initial CI. There are **no incident, investigation,
provider, retrieval, persistence, approval, or evaluation endpoints yet**.

The application currently consists of:

```text
HTTP client -> request size/correlation boundary -> FastAPI health routes
                       |                                 |
                       +-------- safe JSON logs ---------+
```

The complete architecture and product requirements remain in the supplied
[documentation pack](amd_agentic_digital_worker_prd_pack/amd_agentic_digital_worker_prd_pack/00_PROJECT_OVERVIEW.md).
Future directories will be added when their phase is implemented; there are no
placeholder providers or diagnostic tools.

## Local Setup

Requirements: Python 3.12+ and internet access for the initial dependency install.
No GPU, LLM credentials, Docker, or corporate model access is required for Phase 0.
The local verification environment is Windows with Python 3.14.6. CI is configured
for Python 3.12 and 3.14 on Windows and Linux; hosted CI has not run yet.

Run from the repository root in PowerShell with Python 3.12+ on your PATH.
An existing project `.venv` can be reused.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install --require-hashes -r requirements.lock
.venv/Scripts/python.exe -m pip install --no-deps --no-build-isolation -e .
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -m uvicorn agentic_worker.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Stop with Ctrl+C. Use a different `--port` if 8000 is occupied. Interactive API
documentation is at http://127.0.0.1:8000/docs and the schema at
http://127.0.0.1:8000/openapi.json.

The default settings work without a `.env` file. Optional values are documented in
[.env.example](.env.example). Do not put secrets in that example or commit a real
`.env`. Environment variables take precedence over `.env` values.

| Variable | Default | Accepted values |
| --- | --- | --- |
| `WORKER_ENVIRONMENT` | `local` | `local`, `test` |
| `WORKER_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `WORKER_MAX_REQUEST_BYTES` | `65536` | Integer from 1024 to 1048576 |

Unknown `.env` keys and invalid settings fail startup. `WORKER_ENVIRONMENT` is a
configuration label, not authentication or a deployment security boundary.
Request-body limits apply to declared lengths and actual streamed bytes.

## API And Logs

| Endpoint | Result |
| --- | --- |
| `GET /api/v1/health/live` | 200, `{"status":"alive"}` |
| `GET /api/v1/health/ready` | 200, `{"status":"ready"}` after startup |

Readiness returns 503 with `{"status":"not_ready"}` outside the application
lifespan. There are currently no external dependencies to probe. Later phases
must extend readiness as their required dependencies are introduced.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/live
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
```

Each response receives a server-generated `X-Request-ID`. Error responses contain
`code`, `message`, and the matching `request_id`. Validation failures use 422,
oversized bodies 413, unknown resources 404, and unexpected failures 500.
Messages intentionally do not echo rejected inputs or internal exception text;
use the OpenAPI schema to inspect required fields.

Application JSON logs on stdout contain timestamp, level, event, HTTP stage,
request ID, method, matched route template, status code, and duration. Logs exclude
raw request paths, query strings, headers, bodies, and exception messages. Unknown
paths are logged as `unmatched`. Uvicorn access logging is disabled in the startup
command because its normal request-line logs can expose query strings. Run-level
traces and concise evidence rationales are deferred to the workflow phases.

The `IncidentCreate` contract accepts a title (1-200 characters), description
(1-10000), service slug (1-100), severity (`low`, `medium`, `high`, `critical`),
environment (`demo` only), and up to 20 evidence references (1-500 each). Strings
are trimmed, unknown fields are forbidden, and types are not silently coerced.
This contract does not create a resource until Phase 1 adds persistence and APIs.

## Validation

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m mypy src tests
.venv/Scripts/python.exe -m build --no-isolation
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -m pip_audit -r requirements.lock --no-deps --disable-pip --progress-spinner off
```

Tests use in-process HTTP clients and deterministic local inputs, with no LLM or
external service calls. The dependency audit queries a public advisory service
and needs internet access; it is separate from the offline test suite. Build
output is generated under `dist/` and ignored by Git.

Verified locally on 2026-10-15 with Python 3.14.6:

- 35 tests passed, with one upstream Starlette/httpx deprecation warning.
- Ruff lint and formatting passed; strict mypy passed for 15 source/test files.
- Locked dependency installation and editable package installation succeeded.
- Source distribution and wheel built successfully with `--no-isolation`.
- `pip check` found no broken requirements; pip-audit found no known vulnerabilities.
- Real localhost requests returned `alive` and `ready` on the health endpoints.
- Hosted GitHub Actions, Python 3.12 execution, Docker, and later-phase acceptance
  gates are not claimed as verified.

The vulnerability result is a point-in-time advisory check, not a guarantee that
dependencies are vulnerability-free. Local environments, caches, build artifacts,
editor settings, and AI prompt/interview material are excluded from the repository.

Dependency ranges live in [pyproject.toml](pyproject.toml). Installs use the fully
pinned, hash-checked [requirements.lock](requirements.lock), including development
and build tools. The lock was resolved on Python 3.14; cross-platform and minimum
Python support remain subject to the CI matrix rather than an unverified claim.
To deliberately update dependencies, use pip-compile with `--upgrade`, review the
changes, reinstall, and rerun every check:

```powershell
.venv/Scripts/python.exe -m piptools compile pyproject.toml --extra dev --generate-hashes --allow-unsafe --strip-extras --output-file requirements.lock
```

## Documentation Decisions

The numbered source documents are retained rather than duplicated under `docs/`:

| Original prompt path | Existing source of truth |
| --- | --- |
| `docs/PRD.md` | [01_PRD.md](amd_agentic_digital_worker_prd_pack/amd_agentic_digital_worker_prd_pack/01_PRD.md) |
| `docs/ARCHITECTURE.md` | [02_ARCHITECTURE.md](amd_agentic_digital_worker_prd_pack/amd_agentic_digital_worker_prd_pack/02_ARCHITECTURE.md) |
| `docs/API_SPEC.md` | [03_API_SPEC.md](amd_agentic_digital_worker_prd_pack/amd_agentic_digital_worker_prd_pack/03_API_SPEC.md) |
| `docs/EVALUATION.md` | [04_EVALUATION_TEST_PLAN.md](amd_agentic_digital_worker_prd_pack/amd_agentic_digital_worker_prd_pack/04_EVALUATION_TEST_PLAN.md) |
| `docs/SECURITY.md` | [05_SECURITY_RELIABILITY.md](amd_agentic_digital_worker_prd_pack/amd_agentic_digital_worker_prd_pack/05_SECURITY_RELIABILITY.md) |
| `docs/IMPLEMENTATION_ROADMAP.md` | [06_IMPLEMENTATION_ROADMAP.md](amd_agentic_digital_worker_prd_pack/amd_agentic_digital_worker_prd_pack/06_IMPLEMENTATION_ROADMAP.md) |

Additional scope decisions:

- API examples separate incident creation from starting an investigation, while
  US-01 mentions receiving a run ID on submission. Recommendation for Phase 1:
  return an incident ID at creation and a stable run ID when starting a run.
- The API specification's `/api/v1` base path applies to health endpoints too.
- Initial CI belongs to Phase 0 per the roadmap; container
  builds and expanded deployment checks remain Phase 6.
- Initial report generation belongs to Phase 1. Citation-bearing report contracts
  will evolve with real retrieval and evidence validation, not invented sources.
- No runtime LLM provider is configured. Phase 1 will use a deterministic mock;
  a real runtime adapter is a separate Phase 4 integration.

## Limitations And Next Phase

There is no authentication, rate limiter, request-read deadline, persistence,
workflow, RAG, tool execution, approval enforcement, Docker setup, or evaluation
runner yet. Bind to localhost only. Public deployment requires authentication,
TLS, server/proxy timeouts, rate limits, and additional review. Schema definitions
are not evidence that workflow safety or citation validity has been implemented.

If startup fails, verify the interpreter, run `pip check`, and check `.env` keys.
If imports fail, reinstall the editable package from the repository root. If
readiness fails, ensure the server runs the application lifespan. The pinned
Starlette TestClient currently emits an `httpx` deprecation warning; tests retain
the documented httpx stack and do not suppress that warning.

Phase 1, after review, adds SQLite persistence, incident create/read endpoints,
a deterministic mock provider, bounded LangGraph workflow, synthetic diagnostic
data, structured reports, and persisted traces. Later phases add RAG, tool and
approval policies, a real provider, evaluation, and container deployment.

No license has been selected yet. Evaluation metrics will only be published once
the corresponding features are implemented and verified.