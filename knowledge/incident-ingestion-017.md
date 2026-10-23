# DEMO-017 extraction host incident

Document ingestion uploads completed, then extraction returned HTTP 502. Logs showed the
configured extraction host was unreachable. A deployment comparison found that the host changed
immediately before the error ratio increased. Reviewers confirmed the configured hostname was not
the intended dependency. The incident supports checking an extraction-host change when the same
signals appear together. This is a synthetic prior incident, not a live production record.