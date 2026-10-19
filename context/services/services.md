---
type: moc
domain: services
updated: 2026-10-17
---
# Services & Orchestration

## Component 3: Vision-Semantic Oracle
- [[OracleService|OracleService]] — singleton coordinator managing VLM inference, AST triage, caching, and verdict dispatch
- [[TriggerQueueService|TriggerQueueService]] — non-blocking background task worker for Component 2 triggers

## Component 1: Environmental Perturbation
- [[PerturbationOrchestrator|PerturbationOrchestrator]] — system orchestrator applying and managing hardware & network chaos profiles
- [[AttributionEngine|AttributionEngine]] — root-cause engine correlating test failures against environmental stress

## Component 2: Human Stress Interaction
- [[BiometricSimulator|BiometricSimulator]] — generator composing spatial Gaussian scatter and timing models into distorted touch events

## Component 4: Self-Healing Telemetry
- [[SynthesisService|SynthesisService]] — test synthesis coordinator driving S-BERT locator repair and Appium script healing
- [[SessionizationService|SessionizationService]] — event stream aggregator grouping actions into coherent test user flows
- [[IngestionService|IngestionService]] — telemetry loader parsing external crash and session logs (Crashlytics, Sentry)
