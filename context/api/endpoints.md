---
type: moc
domain: api
updated: 2026-10-17
---
# API Endpoints

## Common & Health
- [[GET-api-status|GET /api/status]] — retrieve engine health, hardware telemetry, attached devices

## Component 3: Vision-Semantic Oracle
- [[POST-api-oracle-evaluate|POST /api/oracle/evaluate]] — synchronous screenshot and hierarchy evaluation
- [[POST-api-oracle-evaluate-device|POST /api/oracle/evaluate_device]] — direct live screen capture and evaluation via ADB
- [[POST-api-oracle-trigger|POST /api/oracle/trigger]] — non-blocking async trigger from Component 2 runner
- [[POST-api-oracle-sequence|POST /api/oracle/sequence]] — temporal multi-frame sequence freeze evaluation
- [[GET-api-oracle-verdicts|GET /api/oracle/verdicts]] — query audit verdict ledger and individual records

## Component 1: Environmental Perturbation
- [[POST-api-perturbation-apply|POST /api/perturbation/apply]] — apply CPU, RAM, disk, network, and thermal stress
- [[POST-api-perturbation-reset|POST /api/perturbation/reset]] — reset all stressors to nominal baseline
- [[POST-api-perturbation-attribution|POST /api/perturbation/attribution]] — correlate failures against perturbation logs
