# DEMO-006 search index lag

Search responses slowed after one replica stopped consuming index updates. Metrics showed index
lag while request errors stayed low. Restarting a consumer was simulated only after approval and
the result was verified against index freshness. This record does not concern extraction hosts.