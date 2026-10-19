---
type: service
path: biometry/simulation/simulator.py
depends_on: [[RotationalSpatialModel]], [[TimingModel]], [[AdbBridge]]
used_by: [[POST-api-oracle-trigger]]
updated: 2026-10-17
---
# BiometricSimulator

Core simulation engine for Component 2. Combines anisotropic spatial scatter from [[RotationalSpatialModel]] with latency and hesitation delays from [[TimingModel]] to inject biomechanically realistic touch gestures into the attached device via [[AdbBridge]].
