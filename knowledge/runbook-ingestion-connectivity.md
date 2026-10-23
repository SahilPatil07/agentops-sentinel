# Document ingestion dependency connectivity

Use this runbook when uploads complete but extraction returns HTTP 502 or connection errors.

1. Compare the configured extraction host with the most recent deployment.
2. Query extraction connection errors and the ingestion 5xx ratio for the same window.
3. Confirm the intended host with the service owner before proposing a configuration change.
4. Verify dependency connectivity and declining errors after any approved simulation.

An extraction-host change plus an unreachable matching host supports a configuration-related
connectivity hypothesis. This correlation is not proof by itself. Do not execute a change from
this document; state-changing operations require a separate current approval and rollback plan.