# DEMO-011 notification queue backlog

A synthetic notification-worker backlog followed a downstream mail-provider slowdown. Queue depth
and message age increased while producers remained healthy. The incident was resolved in the
simulator after a bounded drain plan was approved. This is unrelated to document ingestion.