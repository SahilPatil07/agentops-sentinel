# API Specification

Base path: `/api/v1`

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

Response:

``` json
{
  "incident_id": "inc_...",
  "status": "created"
}
```

## 2. Start an investigation

`POST /incidents/{incident_id}/runs`

Request:

``` json
{
  "mode": "investigate",
  "max_tool_calls": 8
}
```

Response:

``` json
{
  "run_id": "run_...",
  "status": "running"
}
```

If implemented synchronously for the MVP, return a completed run
response; preserve a run resource either way.

## 3. Read run status/report

-   `GET /runs/{run_id}`
-   `GET /runs/{run_id}/report`
-   `GET /runs/{run_id}/trace`

The report schema should include: - summary - observed_facts\[\] -
hypotheses\[\] with evidence_refs and confidence_rationale -
missing_information\[\] - recommended_actions\[\] with risk,
preconditions, verification, rollback, approval_required -
source_citations\[\] - limitations - status

## 4. Approvals

-   `POST /runs/{run_id}/actions/{action_id}/approve`
-   `POST /runs/{run_id}/actions/{action_id}/reject`

Approval request requires reviewer label and plan version. In a
portfolio demo, reviewer identity may be a local demo identity, but must
be clearly documented as not production authentication.

## 5. Knowledge ingestion

-   `POST /knowledge/documents` for a local/admin ingestion path
-   `GET /knowledge/documents`
-   `DELETE /knowledge/documents/{document_id}`

Do not expose ingestion to unauthenticated public deployment without
protections. For MVP, disable mutation endpoints by default or protect
them with a demo admin token.

## 6. Health and evaluation

-   `GET /health/live`
-   `GET /health/ready`
-   `POST /evals/run` (optional; admin-only)
-   CLI alternative:
    `python -m agentic_worker.evaluation.run --dataset evals/cases.jsonl`

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
