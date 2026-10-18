---
type: moc
domain: repositories
updated: 2026-10-17
---
# Repositories & Hardware Engines

## Device & Bridge Layer
- [[AdbBridge|AdbBridge]] — centralized Android Debug Bridge wrapper for screenshots, XML hierarchy dumps, and shell taps

## Vision & Analysis Engines (C3)
- [[LocalVisionOracleEngine|LocalVisionOracleEngine]] — offline Qwen2-VL 4-bit AWQ model loader, inference loop, and AST triage
- [[FreezeDetector|FreezeDetector]] — perceptual difference hashing (dHash) and DOM tree freeze comparator
- [[HierarchyPruner|HierarchyPruner]] — UIAutomator XML cleaner, offscreen node filter, and token optimizer

## Biomechanical Models (C2)
- [[RotationalSpatialModel|RotationalSpatialModel]] — Rotational Dual Gaussian touch scatter model
- [[TimingModel|TimingModel]] — inter-action latency and cognitive hesitation model

## Chaos & Synthesis Engines (C1 & C4)
- [[StressorsRepository|StressorsRepository]] — low-level CPU, RAM, network, disk, and thermal chaos injectors
- [[AppiumGenerator|AppiumGenerator]] — Sentence-BERT locator remapper and Appium Python code synthesizer

## Test Suites & Verification
- [[IntegrationTestSuite|IntegrationTestSuite]] — inter-component C2/C3/C4 integration test harness
