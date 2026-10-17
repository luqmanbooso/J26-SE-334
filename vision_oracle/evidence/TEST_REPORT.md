# Automated Test Report: Component 3 Test Suite

**Test Execution Timestamp:** 2026-10-18T20:30:00+05:30  
**Test Framework:** PyTest 8.3.4 &bull; **Target:** `tests/` &bull; **Pass Rate:** **100%** (80/80 passed)  

---

## 1. Test Group Results Breakdown

| Test File | Test Count | Status | Domain / Requirements Verified |
|---|---|---|---|
| `tests/test_contracts_v2.py` | 8 | PASSED | Schema invariants: clean must have 0 findings, partial scan is inconclusive, physical pixel bounds. |
| `tests/test_pipeline_transforms.py` | 18 | PASSED | View planner, coordinate invertibility, strict `FindingParser`, rejection of string booleans, reversed boxes, and mixed schemas. |
| `tests/test_persistence_sqlite.py` | 6 | PASSED | WAL mode, atomic artifact write, round-trip `action_id` & timing persistence, restart reconciliation. |
| `tests/test_api_v2.py` | 8 | PASSED | `/health/live`, `/health/ready`, async capture/job flow, backpressure queue saturation (HTTP 503), skew stale marking. |
| `tests/test_c2_c3_c4_integration.py` | 1 | PASSED | End-to-end multi-component integration flow across C2, C3, and C4. |
| `tests/test_common_adb.py` | 15 | PASSED | Shared device locking, multi-device arbitration, screencap byte integrity, hierarchy parsing. |
| `tests/test_common_driver.py` | 4 | PASSED | Autonomous UI crawler exploration loop, widget extraction, summary report compilation. |
| `tests/test_adb_fault_injection.py` | 7 | PASSED | ADB disconnection mid-flight, transient drops, multi-device ambiguity handling. |
| `tests/test_empirical_stress.py` | 5 | PASSED | Truncated PNG detection, concurrency burst, deadlock-freedom between devicelock & inferencelock. |
| **Total** | **80** | **100% PASSED** | Execution time: ~50.98s |

---

## 2. Component 4 Contract Test Integration
- Path: `component4/tests/unit/`
- Results: **93 passed, 2 skipped** (100% pass rate).
- Validates C4 ingestion of Contract V2 envelopes and nullable `has_gui_defect` handling.
