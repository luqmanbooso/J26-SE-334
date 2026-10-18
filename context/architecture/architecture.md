---
type: moc
domain: architecture
updated: 2026-10-17
---
# Architecture

## Core System Overview
HEART (Human Behavior-Aware Robustness Testing) framework integrates four primary components around an Android testing loop:
- C1: [[PerturbationOrchestrator|Environmental Perturbation Engine]] (`env testing/`)
- C2: [[BiometricSimulator|Human Stress Interaction Engine]] (`biometry/`)
- C3: [[OracleService|Localized Multimodal Vision-Semantic Oracle]] (`vision_oracle/`)
- C4: [[SynthesisService|Self-Healing Telemetry & Regression Synthesizer]] (`component4/`)
- Common: [[AdbBridge|Unified ADB Bridge]] (`common/`)

## Architectural Decisions (ADRs)
- [[ADR-0001-four-component-separation|ADR-0001: Four-component decoupled subsystem architecture]]
- [[ADR-0002-zero-cloud-egress|ADR-0002: Zero cloud egress and on-device VLM execution]]
- [[ADR-0003-unified-adb-bridge|ADR-0003: Centralized ADB device management via common.adb]]
- [[ADR-0004-normalized-c3-verdict-ledger|ADR-0004: Normalized C3 verdict envelope for C4 self-healing]]
