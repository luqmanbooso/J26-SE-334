---
type: repository
path: tests/test_c2_c3_c4_integration.py
depends_on: [[AdbBridge]], [[OracleService]], [[BiometricSimulator]], [[SynthesisService]]
used_by: [[ADR-0001-four-component-separation]]
updated: 2026-10-17
---
# IntegrationTestSuite

End-to-end integration test suite validating inter-component contracts: C2 stress tap dispatch, C3 offline vision oracle defect verdict generation, and C4 self-healing locator synthesizer.
