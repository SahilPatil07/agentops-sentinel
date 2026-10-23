# Search API latency triage

Correlate search latency percentiles with index freshness, shard health, and request volume. Check
whether stale replicas are serving queries before proposing a reindex. Keep search evidence scoped
to the search-api service and do not reuse it as evidence for document ingestion.