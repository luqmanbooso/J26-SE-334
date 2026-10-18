---
type: repository
path: vision_oracle/local_vision_oracle/freeze_detector.py
depends_on: []
used_by: [[OracleService]], [[POST-api-oracle-sequence]]
updated: 2026-10-17
---
# FreezeDetector

Implements temporal multi-frame UI freeze detection (FR3). Computes difference hashing (dHash hamming distance $\le 2$) and UIAutomator XML node identity hashes across consecutive frames to identify non-responsive GUI freezes without app crashes.
