---
type: component
path: vision_oracle/inspect_live_device.py
depends_on: [[AdbBridge]], [[POST-api-oracle-evaluate-device]]
used_by: []
updated: 2026-10-17
---
# InspectLiveDeviceCLI

Standalone debugging CLI. Connects directly to attached physical Android handset or emulator, pulls active screen state, sends to oracle server, and prints localized defect classifications in the terminal.
