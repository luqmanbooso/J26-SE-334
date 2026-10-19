---
type: adr
status: accepted
updated: 2026-10-17
---
# ADR-0004: Normalized C3 verdict envelope for C4 self-healing

Decision: Standardize output of Component 3 as a normalized `C3Verdict` envelope written atomically to `results/verdicts/verdict_<screen_id>_<ts>.json`. Component 4 reads this verdict directly or via [[GET-api-oracle-verdicts]] to trigger S-BERT locator repair and Appium script healing.
Affects [[OracleService]], [[VerdictLedgerStore]], [[SynthesisService]], [[OracleSchemas]].
