---
type: repository
path: biometry/models/spatial.py
depends_on: [[BiometrySchemas]]
used_by: [[BiometricSimulator]]
updated: 2026-10-17
---
# RotationalSpatialModel

Biomechanical touch error model. Samples coordinate offsets from two independent Gaussians aligned to movement approach angle $\theta$, expanding variance proportionally with cognitive stress state to emulate realistic thumb slip and motor tremors.
