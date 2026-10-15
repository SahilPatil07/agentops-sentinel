# Enterprise Digital Worker: Agentic Incident Operations Engineer

## Project goal

Build a portfolio-grade, enterprise-style agentic AI application that
investigates simulated software/service incidents by combining
retrieval-augmented generation (RAG), controlled tool use, multi-step
workflow orchestration, structured outputs, evaluation, observability,
and human approval gates.

This project targets the AMD Junior Agentic AI Software Development
Engineer role. It demonstrates Python engineering, LLM integration,
context engineering, RAG, agent orchestration, APIs, reliability,
testing, deployment, and measurable business outcomes.

## What it is

A digital worker for a fictional company. Given an incident ticket,
it: 1. Classifies the incident and extracts required fields. 2.
Retrieves relevant runbooks and service documentation. 3. Queries a
simulated incident/log/metrics database through typed tools. 4. Forms
evidence-backed hypotheses. 5. Runs only safe, read-only diagnostics
automatically. 6. Proposes remediation steps with risk and evidence. 7.
Requires explicit human approval before any simulated state-changing
action. 8. Produces a traceable incident report and evaluation record.

## What it is not

-   Not an unrestricted autonomous agent.
-   Not connected to real corporate systems.
-   Not allowed to run arbitrary shell commands or execute arbitrary
    SQL.
-   Not allowed to claim a fix was applied unless a tool result proves
    it.
-   Not a benchmark of a specific LLM provider unless measured results
    are recorded.

## Success criteria

-   A new developer can run the service locally using the README.
-   The core workflow works with a deterministic mock LLM/provider, so
    tests do not require paid API access.
-   Provider integration is configurable and secrets stay in environment
    variables.
-   Every tool call is typed, validated, logged, and bounded by
    timeout/retry policy.
-   RAG responses cite retrieved source IDs and abstain when evidence is
    insufficient.
-   Unsafe actions require human approval.
-   Automated tests cover normal, failure, timeout, injection, and
    low-evidence cases.
-   Evaluation results include task completion, groundedness/citation
    validity, tool selection, latency, and token/cost metrics where
    available.
-   Benchmark claims are generated from actual runs, never fabricated.

## Recommended stack

-   Python 3.12+
-   FastAPI + Pydantic
-   LangGraph for explicit stateful workflow orchestration
-   PostgreSQL for application records; SQLite may be used for an easy
    local MVP
-   Chroma or pgvector for vector retrieval; begin with Chroma for local
    setup
-   Provider adapter interface for OpenAI-compatible, Azure OpenAI,
    Anthropic, or Gemini integrations
-   pytest, Ruff, mypy (or pyright), httpx
-   OpenTelemetry-compatible structured logging/tracing where feasible
-   Docker Compose
-   GitHub Actions
-   Streamlit or a minimal React UI only after the backend and tests
    work

## Portfolio positioning

The value is not the word "agent." The value is the controlled workflow,
reproducible evaluation, safe tool execution, clear failure handling,
and evidence that it solves a realistic operations task.
