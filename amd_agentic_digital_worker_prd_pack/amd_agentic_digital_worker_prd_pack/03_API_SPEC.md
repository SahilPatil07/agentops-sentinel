# API Specification

Base path: `/api/v1`

Phase 2 status: incident, run, report, trace, health, and read-only knowledge
endpoints below are implemented. Approval execution, knowledge mutation, and
evaluation remain planned.
The OpenAPI schema at `/openapi.json` describes the implemented contracts.

## 1. Create an incident

`POST /incidents`

Request:

``` json
{
  "title": "Document ingestion returns 502",
  "description": "Upload completes but extraction fails with connection errors.",
  "service": "document-ingestion",
  "severity": "high",
  "environment": "demo",
  "evidence": ["request-id-123"]
}
```

Response (201; abbreviated, IDs generated at runtime):

``` json
{
  "incident_id": "inc_...",
  "status": "created"
}
```

The full response also includes the validated input fields and `created_at`.
`GET /incidents/{incident_id}` returns that persisted record, or 404 if missing.
Creating an incident does not start a run; incident and run IDs are separate.

## 2. Start an investigation

`POST /incidents/{incident_id}/runs`

Request:

``` json
{
  "mode": "investigate",
  "max_tool_calls": 8
}
```

Response (200; abbreviated, IDs generated at runtime):

``` json
{
  "run_id": "run_...",
  "status": "succeeded"
}
```

Phase 2 runs synchronously and returns the persisted terminal run. The full
record includes incident ID, timestamps, tool/step counters, effective tool
budget, provider/model names, and a nullable error code. Outcomes are `succeeded`,
`needs_input`, `blocked`, `degraded`, or `failed`. HTTP 200 means the operation
returned a run record, not that the investigation succeeded or an action ran.
An interrupted run is marked failed on the next single-process startup.

Requests accept only `mode: investigate` and an integer `max_tool_calls` from
1 to 16 (default 8), capped by the server limit. Every POST creates a new run.

## 3. Read run status/report

-   `GET /runs/{run_id}`
-   `GET /runs/{run_id}/report`
-   `GET /runs/{run_id}/trace`

The report schema includes summary, status, observed facts, hypotheses with
evidence references and confidence rationale, missing information, simulated
recommended actions, diagnostic source citations, knowledge chunk citations,
and limitations.

Diagnostic citations are validated against collected observations. Knowledge
citations include the document and chunk IDs, stance, content hash, exact source
offsets, excerpt, and retrieval score; each is validated against the persistent
index before a report is accepted.
Actions are simulated proposals with `approval_required: true` and
`execution_status: not_executed`. No proposal can execute in Phase 2.

Missing runs return 404; a run without a validated report returns 409 from the
report endpoint. Trace pagination accepts `offset >= 0` and `limit` from 1 to
100 (default 100). Events are ordered by sequence and include safe failure codes,
tool observations, and timing metadata rather than raw exception messages.

## 4. Approvals (planned)

-   `POST /runs/{run_id}/actions/{action_id}/approve`
-   `POST /runs/{run_id}/actions/{action_id}/reject`

Approval request requires reviewer label and plan version. In a
portfolio demo, reviewer identity may be a local demo identity, but must
be clearly documented as not production authentication.

## 5. Knowledge retrieval

-   `GET /knowledge/documents`
-   `GET /knowledge/chunks/{chunk_id}`

Both implemented endpoints are read-only. A missing chunk returns 404. The local
corpus is synchronized at startup when the index is empty, or explicitly with
`python -m agentic_worker.retrieval.ingest`. No unauthenticated mutation endpoint
is exposed.

## 6. Health and evaluation

-   `GET /health/live`
-   `GET /health/ready`
-   `POST /evals/run` (optional; admin-only)
-   CLI alternative:
    `python -m agentic_worker.evaluation.run --dataset evals/cases.jsonl`

Readiness checks access to the incident, run, and trace tables and the local
vector index; failure returns 503 without storage details. Liveness does
not depend on storage. Evaluation routes and CLI are planned and are not runnable yet.

## 7. HTTP status conventions

-   200: successful read/action result
-   201: created resource
-   202: accepted asynchronous run
-   400: malformed request
-   401/403: authentication/authorization failure when auth is enabled
-   404: resource not found
-   409: invalid state transition or stale approval plan
-   422: schema validation failure
-   429: rate limit
-   502/503: upstream provider unavailable
-   500: unexpected internal error with correlation ID, without leaking
    stack traces

## 8. API rules

-   Pydantic schemas for every request and response.
-   Version the API.
-   Use pagination for trace/events if large.
-   Bound request size and evidence count.
-   Redact secrets and sensitive content from logs.
-   Never return provider API keys or raw internal exceptions.
