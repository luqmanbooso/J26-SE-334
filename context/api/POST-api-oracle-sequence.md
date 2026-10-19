---
type: endpoint
method: POST
route: /api/oracle/sequence
status: done
path: vision_oracle/api/routes_sequence.py
depends_on: [[FreezeDetector]], [[OracleService]]
used_by: []
updated: 2026-10-17
---
# POST /api/oracle/sequence

Temporal multi-frame sequence evaluation (FR3). Takes consecutive screenshots and hierarchy states across elapsed time delta, executing perceptual difference hashing (dHash) and DOM stability checks to detect UI freezes.
