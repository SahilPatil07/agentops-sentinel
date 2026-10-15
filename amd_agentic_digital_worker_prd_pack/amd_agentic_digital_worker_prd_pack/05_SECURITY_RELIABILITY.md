# Security, Safety, Reliability, and Operations

## 1. Threat model

Protect against: - prompt injection in user input, retrieved documents,
and tool outputs - tool misuse or privilege escalation - secrets
accidentally logged or committed - unbounded loops and runaway token/API
costs - malformed or adversarial model outputs - denial of service via
oversized inputs or repeated requests - unauthorized approval or stale
approval reuse - misleading claims that an action succeeded

## 2. Security controls

-   Store secrets only in environment variables or a local secret
    manager.
-   Include `.env.example`, never a real `.env`.
-   Add `.env`, local databases, raw user uploads, and private
    evaluation data to `.gitignore` where appropriate.
-   Use strict typed schemas for every tool.
-   Expose only allowlisted tools.
-   No arbitrary shell, `eval`, Python execution, or unrestricted SQL.
-   Treat all retrieved text as untrusted content.
-   Separate system policy from retrieved context.
-   Limit tool output size and redact sensitive fields.
-   Add request-size limits and rate limiting for public deployments.
-   Use authentication before exposing approval or knowledge mutation
    endpoints outside localhost.
-   Pin dependencies and run vulnerability checks.
-   Include a security contact and responsible disclosure note if
    publicly deployed.

## 3. Human approval

Every state-changing action: - is represented as a proposal first -
lists expected effect, risk, preconditions, verification, and rollback -
requires explicit approval tied to the current plan version - is
rejected if the plan changes after approval - is executed only by a
simulator in this project - records approval/rejection and outcome in
the audit trace

## 4. Reliability policies

-   finite max graph steps
-   finite max tool calls
-   per-provider and per-tool timeout
-   bounded exponential backoff for retryable errors
-   no retry for invalid input or policy violations
-   idempotency key for state-changing simulated actions
-   circuit-breaker/degraded mode if repeated upstream failures occur
    (optional after MVP)
-   clear run status: succeeded, needs_input, blocked, failed, degraded
-   readiness endpoint checks required dependencies without exposing
    secrets

## 5. Observability

Record structured events: - request_received - run_started -
state_transition - retrieval_completed -
tool_call_started/completed/failed - schema_validation_failed -
approval_requested/approved/rejected - report_generated -
run_completed/failed

Each event should include timestamp, run_id, stage, duration_ms where
applicable, status, and safe metadata. Never log API keys, auth headers,
or hidden chain-of-thought.

## 6. Operational documentation

Document: - local startup and shutdown - configuration and provider
setup - health checks - common failures and fixes - how to re-index
knowledge - how to run tests/evals - how to inspect traces - data reset
procedure - limitations and security assumptions
