# Evaluation and Test Plan

## 1. Evaluation philosophy

An agent demo without evaluation is a magic trick with a README.
Evaluate behavior on a fixed dataset, report each metric separately, and
keep raw results plus configuration.

## 2. Dataset format

Each JSONL case should contain: - case_id - input incident - expected
relevant source IDs - expected allowed tool names - forbidden tool
names/actions - expected outcome category (diagnose, ask_for_info,
abstain, propose_action) - expected key facts or rubric - risk tags

Do not place hidden answer keys in runtime prompts.

## 3. Required cases

1.  Clear known incident: enough evidence to identify likely cause.
2.  Ambiguous incident: agent asks for missing details.
3.  Low evidence: agent abstains rather than inventing a cause.
4.  Conflicting evidence: report conflict and uncertainty.
5.  Tool timeout: run ends in degraded status with explicit failure.
6.  Provider outage: clear error path and no false success.
7.  Malformed LLM JSON: schema validation and bounded retry.
8.  Prompt injection in retrieved runbook: ignore instructions embedded
    in document content.
9.  Malicious incident description asking for secrets or arbitrary shell
    execution.
10. Unsafe remediation: must require approval.
11. Rejected remediation: action must not execute.
12. Stale approval after plan changes: reject.
13. Duplicate tool call loop: terminate within configured budget.
14. Oversized tool output: truncate safely and record truncation.
15. No matching documents: provide transparent limitation.
16. Source citation mismatch: fail validation or flag the report.

## 4. Unit tests

-   request and response schema validation
-   chunking and metadata preservation
-   citation validation
-   tool input validation
-   permission policy
-   approval/version matching
-   retry and timeout policy
-   trace redaction
-   provider adapter contract
-   run state transitions

## 5. Integration tests

-   API creates incident and run
-   mock LLM workflow completes end to end
-   retrieval sources appear in report
-   tool failure appears in trace
-   approval is required before simulated write action
-   provider unavailable returns a controlled error
-   database persistence survives application restart

## 6. Metrics

-   task outcome accuracy against case rubric
-   tool-selection precision/recall
-   valid citation rate
-   evidence coverage
-   schema-valid output rate
-   unsafe-action block rate
-   completion rate
-   abstention correctness on insufficient-evidence cases
-   median and p95 latency
-   provider/tool failure rates
-   token/cost estimate when available

## 7. CI expectations

Every pull request: - format/lint - type check - unit tests -
deterministic integration tests - safety tests - dependency/security
checks where feasible - build Docker image

Live provider tests are opt-in and must not be required for CI. Never
commit real API credentials.

## 8. Reporting

Write `reports/evaluation_<timestamp>.json` and a human-readable
Markdown summary. Include commit SHA, dataset version, provider/model,
configuration, run count, and environment. Label mock-provider results
as mock-provider results.
